"""Collectors. Each one uses the platform's OFFICIAL API only — no scraping, no user tokens.

Every collector exposes `collect(cfg: dict) -> list[Post]` and must:
  * anonymize authors (hash) before anything is stored,
  * respect the platform's rate limits and terms,
  * fail soft (log + return []) so one dead source never kills a scan.
"""
from __future__ import annotations

import hashlib
import importlib
import logging

log = logging.getLogger("fanpulse.collectors")


def anon(platform: str, handle: str | None) -> str:
    """One-way hash so we can count unique voices without keeping usernames."""
    raw = f"{platform}:{handle or 'unknown'}".encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def run_all(cfg: dict) -> list:
    # Imported only when enabled, so a disabled source's dependencies (praw, httpx) needn't be installed.
    modules = {"steam": "steam", "reddit": "reddit", "discord": "discord_api", "meta": "meta_graph", "file": "file"}
    posts = []
    for name, module in modules.items():
        section = cfg.get(name, {})
        if not section.get("enabled", False):
            continue
        try:
            got = importlib.import_module(f".{module}", __package__).collect(section)
            log.info("%s: %d posts", name, len(got))
            posts.extend(got)
        except Exception as exc:  # fail soft
            log.warning("%s collector failed: %s", name, exc)
    return posts
