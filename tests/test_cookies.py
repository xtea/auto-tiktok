from pathlib import Path

import pytest

from auto_tiktok.cookies import (
    NoTikTokCookiesError,
    count_tiktok_entries,
    filter_tiktok_cookies,
    has_sessionid,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample_cookies.txt"
EMPTY = FIXTURES / "no_tiktok_cookies.txt"
SAMPLE_JSON = FIXTURES / "sample_cookies.json"


def test_filter_keeps_only_tiktok_entries(tmp_path: Path) -> None:
    out = tmp_path / "filtered.txt"
    result = filter_tiktok_cookies(SAMPLE, dest=out)

    assert result == out
    text = out.read_text()
    assert "FAKE_SESSION_ABC123" in text
    assert "FAKE_WEBID_999" in text
    assert "FAKE_CSRF_XYZ" in text
    assert "SHOULD_BE_FILTERED_OUT" not in text
    assert "ALSO_FILTERED" not in text


def test_filter_raises_when_no_tiktok_entries(tmp_path: Path) -> None:
    out = tmp_path / "filtered.txt"
    with pytest.raises(NoTikTokCookiesError):
        filter_tiktok_cookies(EMPTY, dest=out)


def test_filter_raises_when_source_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        filter_tiktok_cookies(tmp_path / "nope.txt")


def test_filter_to_tempfile_when_no_dest(tmp_path: Path) -> None:
    result = filter_tiktok_cookies(SAMPLE)
    try:
        assert result.exists()
        assert "FAKE_SESSION_ABC123" in result.read_text()
    finally:
        result.unlink(missing_ok=True)


def test_count_tiktok_entries_on_sample() -> None:
    assert count_tiktok_entries(SAMPLE) == 3


def test_count_tiktok_entries_missing_file(tmp_path: Path) -> None:
    assert count_tiktok_entries(tmp_path / "nope.txt") == 0


def test_has_sessionid_true() -> None:
    assert has_sessionid(SAMPLE) is True


def test_has_sessionid_false() -> None:
    assert has_sessionid(EMPTY) is False


def test_filter_json_cookies(tmp_path: Path) -> None:
    out = tmp_path / "filtered.txt"
    result = filter_tiktok_cookies(SAMPLE_JSON, dest=out)

    text = result.read_text()
    assert text.startswith("# Netscape HTTP Cookie File")
    assert "FAKE_SESSION_JSON_ABC" in text
    assert "FAKE_WEBID_JSON_999" in text
    assert "SHOULD_BE_FILTERED_OUT_JSON" not in text
    assert count_tiktok_entries(result) == 2
    assert has_sessionid(result) is True


def test_filter_json_raises_on_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    with pytest.raises(ValueError):
        filter_tiktok_cookies(bad, dest=tmp_path / "out.txt")


def test_filter_skips_comment_lines(tmp_path: Path) -> None:
    commented = tmp_path / "commented.txt"
    commented.write_text(
        "# this line mentions tiktok but should be ignored\n"
        ".tiktok.com\tTRUE\t/\tTRUE\t1893456000\tsessionid\tREAL\n"
    )
    out = filter_tiktok_cookies(commented, dest=tmp_path / "out.txt")
    assert "REAL" in out.read_text()
    assert count_tiktok_entries(out) == 1
