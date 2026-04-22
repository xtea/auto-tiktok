"""Monkey-patches for `tiktok-uploader` to work reliably on macOS.

Two fixes:

1. ``_clear()`` uses ``Control+A`` to select all text in the caption box. On
   macOS the shortcut is ``Cmd+A`` (``Meta+A`` in Playwright's key syntax), so
   the original behavior silently leaves stale text behind.

2. TikTok often pops up promotional / consent modals that steal focus. Before
   invoking ``_set_description`` and ``_set_interactivity`` we try to dismiss
   any visible modal so the subsequent interaction targets the right element.

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
    """Apply macOS-compat patches to `tiktok_uploader.upload` in place.

    No-op on non-Darwin platforms and on repeat calls.
    """
    global _PATCHED
    if _PATCHED:
        return
    if platform.system() != "Darwin":
        _PATCHED = True
        return

    try:
        from tiktok_uploader import upload as upload_module
    except ImportError:
        log.warning("tiktok-uploader not installed; skipping macOS patches")
        return

    _patch_clear(upload_module)
    _patch_modal_dismissal(upload_module)
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
            element.click()
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")

    upload_module._clear = _clear_patched
    log.info("Patched _clear() for macOS (Meta+A instead of Control+A)")


def _patch_modal_dismissal(upload_module) -> None:
    """Wrap `_set_description` and `_set_interactivity` to dismiss modals first."""

    def _dismiss_modals(page) -> None:
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
                    page.wait_for_timeout(500)
                    log.info("Dismissed modal via %s", selector)
            except Exception:
                pass

    for name in ("_set_description", "_set_interactivity"):
        original = getattr(upload_module, name, None)
        if original is None:
            continue

        def _make_wrapper(orig):
            def _wrapped(*args, **kwargs):
                if args:
                    _dismiss_modals(args[0])
                return orig(*args, **kwargs)

            return _wrapped

        setattr(upload_module, name, _make_wrapper(original))
        log.info("Patched %s() with modal dismissal", name)
