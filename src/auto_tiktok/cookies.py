"""Netscape cookie-file handling for TikTok."""

from __future__ import annotations

import tempfile
from pathlib import Path


class NoTikTokCookiesError(RuntimeError):
    """Raised when a cookies.txt contains no `.tiktok.com` entries."""


def filter_tiktok_cookies(source: Path, dest: Path | None = None) -> Path:
    """Filter a Netscape-format cookies.txt to TikTok-only entries.

    Args:
        source: Path to a full cookies.txt (may contain cookies for many domains).
        dest: Optional output path. If None, writes to a unique tempfile.

    Returns:
        Path to the filtered file, containing only lines whose domain column
        mentions "tiktok".

    Raises:
        FileNotFoundError: if `source` does not exist.
        NoTikTokCookiesError: if `source` contains zero TikTok entries.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Cookies file not found: {source}")

    lines = source.read_text().splitlines()
    filtered = ["# Netscape HTTP Cookie File"]
    for line in lines:
        if "tiktok" in line.lower() and not line.lstrip().startswith("#"):
            filtered.append(line)

    if len(filtered) <= 1:
        raise NoTikTokCookiesError(
            f"No TikTok cookies found in {source}. "
            "Make sure you exported cookies while on a tiktok.com tab."
        )

    if dest is None:
        tmp = tempfile.NamedTemporaryFile(
            prefix="auto_tiktok_cookies_",
            suffix=".txt",
            delete=False,
        )
        dest = Path(tmp.name)
        tmp.close()
    else:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

    dest.write_text("\n".join(filtered) + "\n")
    return dest


def count_tiktok_entries(cookies_path: Path) -> int:
    """Return the number of tiktok-domain cookie lines in a file (0 if missing)."""
    cookies_path = Path(cookies_path)
    if not cookies_path.exists():
        return 0
    return sum(
        1
        for line in cookies_path.read_text().splitlines()
        if "tiktok" in line.lower() and not line.lstrip().startswith("#")
    )


def has_sessionid(cookies_path: Path) -> bool:
    """Return True if cookies_path contains a sessionid cookie for tiktok."""
    cookies_path = Path(cookies_path)
    if not cookies_path.exists():
        return False
    for line in cookies_path.read_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        if "tiktok" in line.lower() and "sessionid" in line:
            return True
    return False
