"""Tests for the last-activity date sniffer and worker-side parser.

Covers:
- ISO-8601 parsing (with/without Z suffix)
- Relative-phrase parsing ("3 days ago", "an hour ago")
- Failure modes (None, empty, garbage)
- Meta-tag sniffing for og:updated_time / article:modified_time
- Body-text fallback to relative phrase
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from leadforge_scraper_core.social import _sniff_last_activity
from leadforge_social_worker.main import _parse_last_activity


class TestParseLastActivity:
    def test_iso8601_with_z(self):
        result = _parse_last_activity("2026-06-30T12:00:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 6
        assert result.day == 30
        assert result.tzinfo is not None

    def test_iso8601_with_offset(self):
        result = _parse_last_activity("2026-06-30T12:00:00+05:30")
        assert result is not None
        assert result.utcoffset() is not None

    def test_iso8601_naive_assumes_utc(self):
        result = _parse_last_activity("2026-06-30T12:00:00")
        assert result is not None
        assert result.tzinfo == UTC

    def test_relative_phrase_days(self):
        before = datetime.now(UTC)
        result = _parse_last_activity("3 days ago")
        after = datetime.now(UTC)
        assert result is not None
        # Should be roughly 3 days before "now"
        delta = before - result
        assert timedelta(days=2, hours=23) < delta < timedelta(days=3, hours=1)
        # And not after "after"
        assert result <= after

    def test_relative_phrase_an_hour(self):
        result = _parse_last_activity("an hour ago")
        assert result is not None
        # Roughly 1 hour ago
        delta = datetime.now(UTC) - result
        assert timedelta(minutes=58) < delta < timedelta(hours=1, minutes=2)

    def test_relative_phrase_weeks(self):
        result = _parse_last_activity("2 weeks ago")
        assert result is not None
        delta = datetime.now(UTC) - result
        assert timedelta(days=13) < delta < timedelta(days=15)

    def test_none(self):
        assert _parse_last_activity(None) is None

    def test_empty(self):
        assert _parse_last_activity("") is None
        assert _parse_last_activity("   ") is None

    def test_garbage(self):
        assert _parse_last_activity("not a date at all") is None


class TestSniffLastActivity:
    def test_og_updated_time(self):
        html = """
        <html>
        <head>
          <meta property="og:updated_time" content="2026-06-30T10:00:00Z" />
        </head>
        <body>Last post was 2 days ago</body>
        </html>
        """
        result = _sniff_last_activity(html)
        assert result == "2026-06-30T10:00:00Z"

    def test_article_modified_time(self):
        html = """
        <html>
        <head>
          <meta property="article:modified_time" content="2026-05-01T15:30:00+00:00" />
        </head>
        <body></body>
        </html>
        """
        result = _sniff_last_activity(html)
        assert result == "2026-05-01T15:30:00+00:00"

    def test_relative_phrase_fallback(self):
        html = "<html><body>Posted 5 days ago</body></html>"
        result = _sniff_last_activity(html)
        assert result is not None
        # Should be a parseable ISO-8601 string representing ~5 days ago
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        delta = datetime.now(UTC) - parsed
        assert timedelta(days=4, hours=23) < delta < timedelta(days=5, hours=1)

    def test_empty_html(self):
        assert _sniff_last_activity("") is None
        assert _sniff_last_activity("<html></html>") is None

    def test_invalid_meta_value_skipped(self):
        html = """
        <html>
        <head>
          <meta property="og:updated_time" content="not-a-date" />
        </head>
        <body></body>
        </html>
        """
        assert _sniff_last_activity(html) is None

    def test_meta_preferred_over_body(self):
        html = """
        <html>
        <head>
          <meta property="og:updated_time" content="2026-01-01T00:00:00Z" />
        </head>
        <body>Posted 2 days ago</body>
        </html>
        """
        result = _sniff_last_activity(html)
        # Meta tag wins over body text
        assert result == "2026-01-01T00:00:00Z"
