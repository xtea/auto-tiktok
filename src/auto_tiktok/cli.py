"""Typer-based CLI for auto-tiktok."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from platformdirs import user_config_dir
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from auto_tiktok import __version__
from auto_tiktok.cookies import (
    NoTikTokCookiesError,
    count_tiktok_entries,
    filter_tiktok_cookies,
    has_sessionid,
)

app = typer.Typer(
    name="auto-tiktok",
    help="Publish videos to TikTok via Chrome automation + exported cookies.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)

CONFIG_DIR = Path(user_config_dir("auto-tiktok"))
DEFAULT_COOKIES = CONFIG_DIR / "cookies.txt"
LEGACY_COOKIES = Path.home() / "Downloads" / "cookies.txt"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"auto-tiktok {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable debug logging.")
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _resolve_cookies(explicit: Path | None) -> Path:
    """Pick the cookies file to use: explicit > config dir > ~/Downloads."""
    if explicit is not None:
        return explicit
    if DEFAULT_COOKIES.exists():
        return DEFAULT_COOKIES
    if LEGACY_COOKIES.exists():
        return LEGACY_COOKIES
    return DEFAULT_COOKIES


@app.command()
def publish(
    video: Annotated[
        Path,
        typer.Option(
            "--video",
            help="Path to the video file (mp4) to upload.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    caption: Annotated[
        str | None,
        typer.Option("--caption", help="Caption text (may include hashtags)."),
    ] = None,
    caption_file: Annotated[
        Path | None,
        typer.Option(
            "--caption-file",
            help="Read caption from a file (alternative to --caption).",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    cookies: Annotated[
        Path | None,
        typer.Option(
            "--cookies",
            help=(
                "Path to Netscape cookies.txt. Defaults to the config-dir "
                "cookies file, falling back to ~/Downloads/cookies.txt."
            ),
        ),
    ] = None,
    headless: Annotated[
        bool,
        typer.Option(
            "--headless/--no-headless",
            help="Run Chromium headless. Default: headful.",
        ),
    ] = False,
    schedule: Annotated[
        int,
        typer.Option(
            "--schedule",
            help=(
                "Schedule post N minutes in the future (20–14400). "
                "0 means post immediately."
            ),
            min=0,
            max=14400,
        ),
    ] = 0,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print plan and exit without uploading."),
    ] = False,
) -> None:
    """Publish a single video to TikTok."""
    if caption is None and caption_file is None:
        err_console.print("[red]error:[/red] provide --caption or --caption-file")
        raise typer.Exit(code=2)
    if caption is not None and caption_file is not None:
        err_console.print(
            "[red]error:[/red] --caption and --caption-file are mutually exclusive"
        )
        raise typer.Exit(code=2)

    description = caption if caption is not None else caption_file.read_text().strip()

    cookies_path = _resolve_cookies(cookies)
    if not cookies_path.exists():
        err_console.print(
            f"[red]error:[/red] cookies file not found: {cookies_path}\n"
            f"Run [bold]auto-tiktok import-cookies <path>[/bold] first."
        )
        raise typer.Exit(code=3)

    size_mb = video.stat().st_size / (1024 * 1024)
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Video", f"{video}  ({size_mb:.1f} MB)")
    summary.add_row(
        "Caption",
        description[:100] + ("…" if len(description) > 100 else ""),
    )
    summary.add_row("Cookies", str(cookies_path))
    summary.add_row("Headless", str(headless))
    if schedule:
        summary.add_row("Schedule", f"{schedule} min from now")
    console.print(Panel(summary, title="auto-tiktok publish", border_style="cyan"))

    if dry_run:
        console.print("[yellow]dry-run[/yellow] — not uploading.")
        return

    # Import here so --dry-run and --help don't require tiktok-uploader.
    from auto_tiktok.publisher import (
        TikTokUploaderMissingError,
        publish_video,
    )

    schedule_seconds = schedule * 60
    try:
        publish_video(
            video_path=video,
            description=description,
            cookies_path=cookies_path,
            headless=headless,
            schedule_seconds=schedule_seconds,
        )
    except NoTikTokCookiesError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=4) from exc
    except TikTokUploaderMissingError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=5) from exc
    except FileNotFoundError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=3) from exc

    console.print("[green]:heavy_check_mark:  Upload complete.[/green]")


@app.command("import-cookies")
def import_cookies(
    source: Annotated[
        Path,
        typer.Argument(
            help="Path to the Netscape-format cookies.txt exported from your browser.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    dest: Annotated[
        Path | None,
        typer.Option("--dest", help=f"Override destination (default: {DEFAULT_COOKIES})."),
    ] = None,
) -> None:
    """Filter a cookies.txt to TikTok-only entries and save to the config dir."""
    target = dest or DEFAULT_COOKIES
    try:
        written = filter_tiktok_cookies(source, dest=target)
    except NoTikTokCookiesError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=4) from exc

    try:
        os.chmod(written, 0o600)
    except OSError:
        pass

    count = count_tiktok_entries(written)
    console.print(
        f"[green]:heavy_check_mark:[/green] Imported {count} TikTok cookie entries → "
        f"[bold]{written}[/bold] (chmod 600)"
    )
    if not has_sessionid(written):
        console.print(
            "[yellow]warning:[/yellow] no sessionid cookie found — you may not be "
            "authenticated."
        )


@app.command("install-browser")
def install_browser(
    browser: Annotated[
        str,
        typer.Option(
            "--browser",
            help="Which Playwright browser to install. Default: chromium.",
        ),
    ] = "chromium",
) -> None:
    """Download the Playwright browser binary required for uploading."""
    console.print(f"Running [bold]playwright install {browser}[/bold]…")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", browser],
            check=False,
        )
    except FileNotFoundError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=5) from exc

    if result.returncode != 0:
        err_console.print(
            f"[red]error:[/red] playwright install exited {result.returncode}"
        )
        raise typer.Exit(code=result.returncode)

    console.print(f"[green]:heavy_check_mark:[/green] {browser} installed.")


@app.command()
def doctor() -> None:
    """Check that auto-tiktok has everything it needs to publish."""
    table = Table(title="auto-tiktok doctor", show_lines=False)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    # Python version
    py_ok = sys.version_info >= (3, 11)
    table.add_row(
        "Python >= 3.11",
        "[green]OK[/green]" if py_ok else "[red]FAIL[/red]",
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )

    # tiktok-uploader
    try:
        import tiktok_uploader  # noqa: F401

        table.add_row("tiktok-uploader installed", "[green]OK[/green]", "")
        tu_ok = True
    except ImportError:
        table.add_row(
            "tiktok-uploader installed",
            "[red]FAIL[/red]",
            "uv pip install tiktok-uploader",
        )
        tu_ok = False

    # Playwright module
    try:
        import playwright  # noqa: F401

        table.add_row("playwright installed", "[green]OK[/green]", "")
        pw_ok = True
    except ImportError:
        table.add_row("playwright installed", "[red]FAIL[/red]", "uv pip install playwright")
        pw_ok = False

    # Playwright Chromium binary
    pw_bin_ok = False
    pw_bin_detail = ""
    if pw_ok:
        ms_play = Path.home() / "Library" / "Caches" / "ms-playwright"
        linux_cache = Path.home() / ".cache" / "ms-playwright"
        win_cache = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        candidate_roots = [ms_play, linux_cache, win_cache]
        found = False
        for root in candidate_roots:
            if root.exists() and any(p.name.startswith("chromium") for p in root.iterdir()):
                found = True
                pw_bin_detail = str(root)
                break
        pw_bin_ok = found
        table.add_row(
            "playwright chromium binary",
            "[green]OK[/green]" if found else "[yellow]MAYBE[/yellow]",
            pw_bin_detail or "run: playwright install chromium",
        )

    # Default cookies file
    cookies_path = _resolve_cookies(None)
    if cookies_path.exists():
        n = count_tiktok_entries(cookies_path)
        sid = has_sessionid(cookies_path)
        if n > 0 and sid:
            table.add_row(
                "cookies (tiktok)",
                "[green]OK[/green]",
                f"{cookies_path} — {n} entries, sessionid present",
            )
        elif n > 0:
            table.add_row(
                "cookies (tiktok)",
                "[yellow]WARN[/yellow]",
                f"{cookies_path} — {n} entries but no sessionid",
            )
        else:
            table.add_row(
                "cookies (tiktok)",
                "[red]FAIL[/red]",
                f"{cookies_path} — no TikTok entries",
            )
    else:
        table.add_row(
            "cookies (tiktok)",
            "[red]FAIL[/red]",
            f"not found at {cookies_path} — run import-cookies",
        )

    # Which chrome/chromium (informational)
    chrome = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium")
    table.add_row(
        "system chrome (informational)",
        "[green]found[/green]" if chrome else "[yellow]not found[/yellow]",
        chrome or "playwright bundles its own chromium",
    )

    console.print(table)

    all_ok = py_ok and tu_ok and pw_ok and pw_bin_ok and cookies_path.exists()
    if not all_ok:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
