# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-22

### Added
- Initial release.
- `publish` command: upload a video to TikTok using exported Netscape-format session cookies.
- `import-cookies` command: copy and filter a `cookies.txt` into the platform config directory.
- `doctor` command: verify tiktok-uploader install, Playwright Chromium binaries, and cookie validity.
- macOS compatibility patches for `tiktok-uploader` (Cmd+A text selection, modal dismissal).
- Dry-run mode for previewing uploads without launching the browser.
- JSON cookie export support (Cookie-Editor / EditThisCookie format) in addition to Netscape `cookies.txt`.
