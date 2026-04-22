# auto-tiktok

A lean Python CLI that publishes videos to TikTok by driving a real Chrome browser with your exported session cookies. No official API, no OAuth dance — just paste your cookies and post.

Inspired by [xtea/auto-instagram](https://github.com/xtea/auto-instagram). Built on top of the excellent [`tiktok-uploader`](https://pypi.org/project/tiktok-uploader/) package.

## Why

TikTok's official Content Posting API requires business verification, app review, and a hoop-jumping approval process. If you just want to automate publishing to your own account from your own machine, browser automation with session cookies is dramatically simpler.

## Install

Requires Python 3.11+.

### Quick install (recommended)

```bash
# via uv (installs globally, isolated)
uv tool install auto-tiktok
auto-tiktok install-browser

# or via pipx
pipx install auto-tiktok
auto-tiktok install-browser

# or plain pip
pip install auto-tiktok
auto-tiktok install-browser
```

The `install-browser` step downloads the Chromium binary Playwright needs (~150 MB). You only run it once.

### One-shot run without installing

```bash
uvx auto-tiktok publish --video my.mp4 --caption "..."
```

### From source

```bash
git clone https://github.com/xtea/auto-tiktok
cd auto-tiktok
uv sync
uv run auto-tiktok install-browser
```

## Export your TikTok cookies

1. Install a cookie-export browser extension. Recommended:
   - [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) (Chrome) — exports Netscape `.txt`
   - [Cookie-Editor](https://cookie-editor.com/) (all browsers) — exports JSON
2. Log into [tiktok.com](https://www.tiktok.com) in your browser.
3. Open the extension on the TikTok tab and export cookies. Either **Netscape `.txt`** or **JSON** format works — auto-tiktok auto-detects.
4. Import them into auto-tiktok:

```bash
auto-tiktok import-cookies ~/Downloads/cookies.txt
```

This filters the file down to TikTok-only entries and saves it to `~/.config/auto-tiktok/cookies.txt` (or the equivalent on your platform) with `chmod 600`.

## Usage

### Publish a video

```bash
auto-tiktok publish \
  --video ./my-video.mp4 \
  --caption "behind the scenes #tutorial #indiehacker"
```

The caption can include hashtags directly. Compose it however you want — auto-tiktok passes it through verbatim.

For long captions, read from a file instead:

```bash
auto-tiktok publish --video ./my-video.mp4 --caption-file ./caption.txt
```

### Dry run

Preview what will be posted without launching Chromium:

```bash
auto-tiktok publish --video ./my-video.mp4 --caption "test" --dry-run
```

### Schedule a post

TikTok supports scheduling 20 minutes to 10 days in the future:

```bash
auto-tiktok publish --video ./my-video.mp4 --caption "drop at noon" --schedule 60
```

### Use a custom cookies file

```bash
auto-tiktok publish --video ./my-video.mp4 --caption "..." --cookies /path/to/cookies.txt
```

### Run headless

```bash
auto-tiktok publish --video ./my-video.mp4 --caption "..." --headless
```

Note: headful (default) tends to trip fewer anti-bot heuristics.

### Health check

```bash
auto-tiktok doctor
```

Reports whether `tiktok-uploader` is installed, Playwright Chromium is available, and your cookies file is present and non-empty.

## Troubleshooting

- **"No TikTok cookies found"** — your export doesn't include the `.tiktok.com` domain. Make sure you're on a tiktok.com tab when exporting.
- **Upload hangs at the caption box** — TikTok is showing a modal. auto-tiktok tries to dismiss them automatically on macOS, but new variants appear; run without `--headless` so you can see and click through.
- **2FA / login challenges** — cookies expire. Re-export them from your browser and re-run `import-cookies`.
- **Chromium not found** — run `playwright install chromium`.
- **Published URL not shown** — `tiktok-uploader` doesn't reliably return the final TikTok URL. Check your profile.

## Security

- Your `sessionid` cookie is a full account credential. **Treat it like a password.**
- Never commit `cookies.txt` to source control (the bundled `.gitignore` blocks it).
- If you suspect a leak, go to `Settings → Security & permissions → Manage sessions` on TikTok and log out all sessions to invalidate the cookie.
- This tool makes no network calls outside Playwright's browser automation.

## How it works

1. Filters your `cookies.txt` to TikTok-only entries and writes a temp file.
2. Applies two macOS-compat monkey patches to `tiktok-uploader`:
   - Swaps `Ctrl+A` → `Cmd+A` in the caption clear step.
   - Wraps internal `_set_description` / `_set_interactivity` with a modal-dismissal pass.
3. Calls `tiktok_uploader.upload.upload_video()` which launches Chromium via Playwright, injects cookies, navigates to the upload page, fills the caption, and clicks Post.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src/ tests/
```

## Status

Alpha. Works for the author's use case on macOS with Chromium. Windows and Linux should work but are less tested. TikTok breaks selectors periodically — if you hit issues, open an issue or PR.

## License

MIT. See [LICENSE](./LICENSE).

## Credits

- [xtea/auto-instagram](https://github.com/xtea/auto-instagram) for the architectural blueprint.
- [`tiktok-uploader`](https://github.com/wkaisertexas/tiktok-uploader) for the underlying browser automation.
