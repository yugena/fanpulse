"""Tiny stdlib HTTP helper (no third-party deps, so fetchers run on stock Python 3.9+)."""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request


def tls() -> ssl.SSLContext:
    """python.org builds on macOS ship without CA certificates; use certifi's bundle when present."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def json_request(url: str, body: dict | None = None, headers: dict | None = None, timeout: float = 120) -> dict:
    """GET (or POST when body is given) returning JSON; backs off on HTTP 429."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=tls()) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(float(e.headers.get("Retry-After", 10)))
    raise RuntimeError("unreachable")
