"""Core TikTok upload wrapper.

Exposes a single synchronous function: :func:`publish_video`.

This module deliberately does *not* import ``tiktok_uploader`` at module load
time so that ``auto-tiktok doctor`` can still report a missing install
gracefully instead of exploding during CLI bootstrap.
"""

from __future__ import annotations

import logging
from pathlib import Path

from auto_tiktok.cookies import filter_tiktok_cookies
from auto_tiktok.patches import apply_tiktok_uploader_patches

log = logging.getLogger(__name__)


class TikTokUploaderMissingError(RuntimeError):
    """Raised when the `tiktok-uploader` package is not installed."""


def publish_video(
    video_path: Path,
    description: str,
    cookies_path: Path,
    *,
    headless: bool = False,
    schedule_seconds: int = 0,
) -> None:
    """Upload a single video to TikTok.

    Args:
        video_path: Path to the mp4 to upload.
        description: Full caption (may include hashtags). Passed through
            verbatim to TikTok.
        cookies_path: Path to a Netscape-format cookies.txt with at least one
            ``.tiktok.com`` entry. Will be filtered to TikTok-only before use.
        headless: Run Chromium in headless mode. Defaults to False — headful
            tends to trip fewer anti-bot heuristics.
        schedule_seconds: If > 0, schedule the post this many seconds in the
            future. Must be between 1200 (20 min) and 864000 (10 days) per
            TikTok's own UI rules.

    Raises:
        TikTokUploaderMissingError: if `tiktok-uploader` is not installed.
        FileNotFoundError: if `video_path` or `cookies_path` is missing.
        ValueError: if `schedule_seconds` is outside TikTok's allowed range.
    """
    video_path = Path(video_path)
    cookies_path = Path(cookies_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not cookies_path.exists():
        raise FileNotFoundError(f"Cookies file not found: {cookies_path}")

    if schedule_seconds and not 1200 <= schedule_seconds <= 864000:
        raise ValueError(
            "schedule_seconds must be 0 or between 1200 (20 min) and "
            "864000 (10 days)."
        )

    apply_tiktok_uploader_patches()

    try:
        from tiktok_uploader.upload import upload_video as _upload_video
    except ImportError as exc:
        raise TikTokUploaderMissingError(
            "tiktok-uploader is not installed. "
            "Run: uv pip install tiktok-uploader && playwright install chromium"
        ) from exc

    filtered_cookies = filter_tiktok_cookies(cookies_path)

    size_mb = video_path.stat().st_size / (1024 * 1024)
    log.info(
        "Publishing %s (%.1f MB) with caption: %s",
        video_path.name,
        size_mb,
        description[:80] + ("…" if len(description) > 80 else ""),
    )

    _upload_video(
        filename=str(video_path),
        description=description,
        cookies=str(filtered_cookies),
        headless=headless,
        schedule=schedule_seconds,
    )
    log.info("Upload complete: %s", video_path.name)
