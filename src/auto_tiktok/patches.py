"""Monkey-patches for `tiktok-uploader` to work reliably with current TikTok UI.

Three fixes:

1. ``_clear()`` uses ``Control+A`` to select all text in the caption box. On
   macOS the shortcut is ``Cmd+A`` (``Meta+A`` in Playwright's key syntax), so
   the original behavior silently leaves stale text behind.

2. TikTok's current upload UI overlays a ``react-joyride`` onboarding tour
   that intercepts pointer events on the caption and interactivity controls.
   Before touching those controls we click the tour's primary "Got it" / "Skip"
   button to retire the tour.

3. TikTok periodically shows promotional / consent modals that steal focus.
   We also try to dismiss any visible modal close-button before proceeding.

Patches are idempotent — calling ``apply_tiktok_uploader_patches`` multiple
times is safe.
"""

from __future__ import annotations

import inspect
import logging
import platform

log = logging.getLogger(__name__)

_PATCHED = False


def apply_tiktok_uploader_patches() -> None:
    """Apply compat patches to `tiktok_uploader.upload` in place.

    Patches run on every platform (the joyride + modal patches are not
    macOS-specific). The Cmd+A shortcut fix only runs on Darwin.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from tiktok_uploader import upload as upload_module
    except ImportError:
        log.warning("tiktok-uploader not installed; skipping patches")
        return

    if platform.system() == "Darwin":
        _patch_clear(upload_module)
    _patch_pre_interaction(upload_module)
    _PATCHED = True


def _patch_clear(upload_module) -> None:
    """Replace Control+A with Meta+A in the caption-clear helper."""
    original_clear = getattr(upload_module, "_clear", None)
    if original_clear is None:
        return

    try:
        source = inspect.getsource(original_clear)
    except (OSError, TypeError):
        return

    if "Control+A" not in source and "Control+a" not in source:
        return

    def _clear_patched(page, element=None):
        if element:
            try:
                element.click()
            except Exception:
                pass
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")

    upload_module._clear = _clear_patched
    log.info("Patched _clear() for macOS (Meta+A instead of Control+A)")


def _dismiss_joyride(page) -> bool:
    """Try to close the react-joyride onboarding tour. Returns True if clicked."""
    joyride_selectors = [
        'button[data-test-id="button-primary"]',
        'button[data-action="primary"]',
        '.react-joyride__tooltip button[class*="primary"]',
        '#react-joyride-portal button:last-of-type',
        'button[aria-label="Close"][class*="joyride"]',
        'button[data-test-id="button-skip"]',
    ]
    clicked = False
    for selector in joyride_selectors:
        try:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(400)
                log.info("Dismissed react-joyride via %s", selector)
                clicked = True
        except Exception:
            pass

    # Text-based fallback via Playwright's get_by_role if still present.
    for text in ("Got it", "Got It", "Skip", "OK", "Dismiss", "Finish"):
        try:
            btn = page.get_by_role("button", name=text)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(400)
                log.info("Dismissed tooltip via button text '%s'", text)
                clicked = True
        except Exception:
            pass

    # Last resort: if an overlay still exists, hide it so it can't intercept.
    try:
        overlay = page.query_selector('[class*="react-joyride__overlay"]')
        if overlay and overlay.is_visible():
            page.evaluate(
                "() => { document.querySelectorAll('[class*=\"react-joyride\"]')"
                ".forEach(el => el.remove()); }"
            )
            log.info("Forcibly removed lingering joyride overlay via JS")
            clicked = True
    except Exception:
        pass

    return clicked


def _dismiss_modals(page) -> None:
    """Click any visible modal close button."""
    selectors = [
        '[class*="modal"] [class*="close"]',
        '[class*="dialog"] [class*="close"]',
        '[aria-label="Close"]',
        '[class*="CloseButton"]',
        'button[class*="close"]',
        '[data-e2e="modal-close-button"]',
    ]
    for selector in selectors:
        try:
            close_btn = page.query_selector(selector)
            if close_btn and close_btn.is_visible():
                close_btn.click()
                page.wait_for_timeout(400)
                log.info("Dismissed modal via %s", selector)
        except Exception:
            pass


def _patch_pre_interaction(upload_module) -> None:
    """Wrap `_set_description` and `_set_interactivity` with overlay dismissal."""

    for name in ("_set_description", "_set_interactivity"):
        original = getattr(upload_module, name, None)
        if original is None:
            continue

        def _make_wrapper(orig):
            def _wrapped(*args, **kwargs):
                if args:
                    page = args[0]
                    _dismiss_joyride(page)
                    _dismiss_modals(page)
                return orig(*args, **kwargs)

            return _wrapped

        setattr(upload_module, name, _make_wrapper(original))
        log.info("Patched %s() with joyride + modal dismissal", name)
