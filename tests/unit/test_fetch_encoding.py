"""Fetch-encoding regression tests.

`br` used to be advertised without a brotli decoder installed, so httpx
returned compressed bytes as text and every extractor saw zero emails/links.
"""

from __future__ import annotations

import gzip
from types import SimpleNamespace

import httpx
from leadforge_scraper_core import base as base_mod
from leadforge_scraper_core import website as website_mod
from leadforge_scraper_core.base import ACCEPT_ENCODING, _do_fetch

BODY = (
    "<html><body>" + ("padding " * 100) + " contact@acme.test 0332 9307688</body></html>"
).encode()


def test_accept_encoding_is_decodable() -> None:
    # httpx only decodes gzip/deflate without optional dependencies.
    assert "br" not in [part.strip() for part in ACCEPT_ENCODING.split(",")]
    assert "br" not in [part.strip() for part in website_mod.ACCEPT_ENCODING.split(",")]


async def test_do_fetch_decodes_gzip_body(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "br" not in request.headers.get("accept-encoding", "")
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            content=gzip.compress(BODY),
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def factory(**kwargs):
        kwargs.pop("proxy", None)
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(base_mod.httpx, "AsyncClient", factory)

    html = await _do_fetch(
        "https://example.test",
        use_playwright=False,
        timeout=5.0,
        ua="test-agent",
        proxy=None,
        settings=SimpleNamespace(playwright_headless=True),
        log=None,
    )

    assert html is not None
    assert "contact@acme.test" in html
