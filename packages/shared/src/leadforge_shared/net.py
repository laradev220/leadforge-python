"""Outbound URL safety checks (SSRF)."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}


async def validate_public_https_url(url: str) -> str:
    """Return the URL when it is a public HTTPS target, else raise ValueError.

    Resolves the hostname and rejects loopback, private, link-local, multicast
    and reserved addresses to reduce SSRF risk. Call again at delivery time.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise ValueError("Webhook URLs must use https")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local"):
        raise ValueError("Webhook host is not allowed")
    port = parsed.port or 443
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("Webhook host could not be resolved") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("Webhook target resolves to a private address")
    return url
