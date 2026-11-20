"""Discord via the official Bot REST API.

Rules that matter:
  * The bot can only read servers it has been INVITED to (e.g. your own community server,
    or a fan server whose admins agreed). Reading other servers with a user token
    ("self-bot") violates Discord's ToS — this module never does that.
  * Enable the privileged MESSAGE CONTENT intent in the Developer Portal.
Env: DISCORD_BOT_TOKEN
"""
from __future__ import annotations

import os
import time
from datetime import datetime

import httpx

from ..models import Post
from . import anon

API = "https://discord.com/api/v10"


def _get(client: httpx.Client, url: str, params: dict) -> list:
    while True:
        r = client.get(url, params=params)
        if r.status_code == 429:  # respect rate limits
            time.sleep(float(r.json().get("retry_after", 1.0)))
            continue
        r.raise_for_status()
        return r.json()


def collect(cfg: dict) -> list[Post]:
    token = os.environ["DISCORD_BOT_TOKEN"]
    channel_ids: list[str] = cfg.get("channel_ids", [])  # e.g. #feedback, #bug-reports, #suggestions
    max_per_channel = int(cfg.get("max_messages_per_channel", 1000))
    out: list[Post] = []

    with httpx.Client(headers={"Authorization": f"Bot {token}"}, timeout=20) as client:
        for ch in channel_ids:
            before = None
            fetched = 0
            while fetched < max_per_channel:
                params = {"limit": 100}
                if before:
                    params["before"] = before
                batch = _get(client, f"{API}/channels/{ch}/messages", params)
                if not batch:
                    break
                for m in batch:
                    if m.get("author", {}).get("bot") or not m.get("content"):
                        continue
                    reactions = sum(r.get("count", 0) for r in m.get("reactions", []))
                    out.append(Post(
                        platform="discord", id=m["id"], author=anon("discord", m["author"]["id"]),
                        text=m["content"],
                        created_at=datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")),
                        likes=reactions,
                        replies=int(m.get("thread", {}).get("message_count", 0)),
                        url=f"https://discord.com/channels/{m.get('guild_id', '@me')}/{ch}/{m['id']}",
                        source=f"discord:{ch}",
                    ))
                fetched += len(batch)
                before = batch[-1]["id"]
    return out
