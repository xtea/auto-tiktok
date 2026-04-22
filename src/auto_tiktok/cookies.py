"""Cookie handling for TikTok — supports both Netscape and JSON exports."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


class NoTikTokCookiesError(RuntimeError):
    """Raised when a cookies file contains no `.tiktok.com` entries."""


def _is_json_cookies(text: str) -> bool:
    """Detect Cookie-Editor style JSON export (array of cookie objects)."""
    stripped = text.lstrip()
    return stripped.startswith("[") or stripped.startswith("{")


def _cookie_obj_to_netscape_line(c: dict[str, Any]) -> str | None:
    """Convert one Cookie-Editor/EditThisCookie JSON cookie to a Netscape line.

    Returns None if the object is missing required fields.
    """
    name = c.get("name")
    value = c.get("value")
    domain = c.get("domain")
    if not name or value is None or not domain:
        return None

    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
    path = c.get("path") or "/"
    secure = "TRUE" if c.get("secure") else "FALSE"

    expiry = c.get("expirationDate")
    if expiry is None:
        expiry = 0
    expiry_int = int(float(expiry))

    return "\t".join(
        [domain, include_subdomains, path, secure, str(expiry_int), name, str(value)]
    )


def _json_to_netscape_lines(text: str) -> list[str]:
    """Parse a JSON cookie export and emit Netscape-format lines for tiktok."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON cookie file: {exc}") from exc

    if isinstance(data, dict) and "cookies" in data:
        data = data["cookies"]

    if not isinstance(data, list):
        raise ValueError("JSON cookie file must be an array of cookie objects.")

    lines: list[str] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        domain = str(entry.get("domain") or "")
        if "tiktok" not in domain.lower():
            continue
        line = _cookie_obj_to_netscape_line(entry)
        if line:
            lines.append(line)
    return lines


def _netscape_to_filtered_lines(text: str) -> list[str]:
    """Extract tiktok-domain lines from a Netscape-format cookies.txt."""
    out: list[str] = []
    for line in text.splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        if "tiktok" in line.lower():
            out.append(line)
    return out


def filter_tiktok_cookies(source: Path, dest: Path | None = None) -> Path:
    """Filter a cookies file to TikTok-only entries in Netscape format.

    Accepts either:
      - Netscape-format cookies.txt (from "Get cookies.txt LOCALLY" extension)
      - JSON cookie export (from Cookie-Editor / EditThisCookie)

    Args:
        source: Path to the source cookies file.
        dest: Optional output path. If None, writes to a unique tempfile.

    Returns:
        Path to the filtered Netscape-format file.

    Raises:
        FileNotFoundError: if `source` does not exist.
        NoTikTokCookiesError: if `source` contains zero TikTok entries.
        ValueError: if `source` is malformed JSON.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Cookies file not found: {source}")

    text = source.read_text()

    if _is_json_cookies(text):
        tiktok_lines = _json_to_netscape_lines(text)
    else:
        tiktok_lines = _netscape_to_filtered_lines(text)

    if not tiktok_lines:
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

    output = ["# Netscape HTTP Cookie File", *tiktok_lines]
    dest.write_text("\n".join(output) + "\n")
    return dest


def count_tiktok_entries(cookies_path: Path) -> int:
    """Return the number of tiktok-domain cookie lines in a Netscape file (0 if missing)."""
    cookies_path = Path(cookies_path)
    if not cookies_path.exists():
        return 0
    return sum(
        1
        for line in cookies_path.read_text().splitlines()
        if line and not line.lstrip().startswith("#") and "tiktok" in line.lower()
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
