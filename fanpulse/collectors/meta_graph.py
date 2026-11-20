"""Instagram + Facebook via Meta's official Graph API.

What the API allows (and what it doesn't):
  * Instagram hashtag search: needs an Instagram Professional (Business/Creator) account
    linked to a Facebook Page, plus the `instagram_basic` permission and the
    "Instagram Public Content Access" feature. Returns public media CAPTIONS + like/comment
    counts for a hashtag. Limit: 30 unique hashtags per rolling 7 days per account.
    Comments on other people's media are NOT available.
  * Facebook: posts + comments on Pages you manage (pages_read_engagement, pages_read_user_content).
    Public pages you don't manage need the "Page Public Content Access" feature (app review).
  * There is no general "search all of Facebook/Instagram" API, and scraping violates Meta's terms.
Env: META_ACCESS_TOKEN, IG_USER_ID
"""
from __future__ import annotations

import os
from datetime import datetime

import httpx

from ..models import Post
from . import anon


def _graph(version: str) -> str:
    return f"https://graph.facebook.com/{version}"


def _ts(s: str) -> datetime:
    # Graph returns e.g. 2026-11-19T18:22:01+0000
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def _instagram(client: httpx.Client, g: str, cfg: dict) -> list[Post]:
    ig_user = os.environ["IG_USER_ID"]
    out = []
    for tag in cfg.get("instagram_hashtags", ["gta6", "gtavi"]):
        found = client.get(f"{g}/ig_hashtag_search", params={"user_id": ig_user, "q": tag}).json()
        if not found.get("data"):
            continue
        tag_id = found["data"][0]["id"]
        for edge in ("top_media", "recent_media"):
            media = client.get(f"{g}/{tag_id}/{edge}", params={
                "user_id": ig_user,
                "fields": "id,caption,like_count,comments_count,timestamp,permalink",
                "limit": 50,
            }).json()
            for m in media.get("data", []):
                if not m.get("caption"):
                    continue
                out.append(Post(
                    platform="instagram", id=m["id"],
                    author=anon("instagram", m["id"]),  # hashtag API doesn't expose usernames
                    text=m["caption"], created_at=_ts(m["timestamp"]),
                    likes=int(m.get("like_count", 0)), replies=int(m.get("comments_count", 0)),
                    url=m.get("permalink", ""), source=f"#{tag}",
                ))
    return out


def _facebook(client: httpx.Client, g: str, cfg: dict) -> list[Post]:
    out = []
    for page_id in cfg.get("facebook_page_ids", []):
        posts = client.get(f"{g}/{page_id}/posts", params={
            "fields": "id,message,created_time,permalink_url,"
                      "reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)",
            "limit": 25,
        }).json()
        for p in posts.get("data", []):
            # The fan feedback is mostly in the comments, not the page's own post.
            comments = client.get(f"{g}/{p['id']}/comments", params={
                "fields": "id,message,created_time,like_count,comment_count,from",
                "order": "reverse_chronological", "limit": 100,
            }).json()
            for c in comments.get("data", []):
                if not c.get("message"):
                    continue
                out.append(Post(
                    platform="facebook", id=c["id"],
                    author=anon("facebook", (c.get("from") or {}).get("id")),
                    text=c["message"], created_at=_ts(c["created_time"]),
                    likes=int(c.get("like_count", 0)), replies=int(c.get("comment_count", 0)),
                    url=p.get("permalink_url", ""), source=f"fb:{page_id}",
                ))
    return out


def collect(cfg: dict) -> list[Post]:
    g = _graph(cfg.get("graph_version", "v24.0"))  # bump to the current Graph API version
    with httpx.Client(params={"access_token": os.environ["META_ACCESS_TOKEN"]}, timeout=20) as c:
        out = []
        if cfg.get("instagram", True):
            out += _instagram(c, g, cfg)
        if cfg.get("facebook", True):
            out += _facebook(c, g, cfg)
        return out
