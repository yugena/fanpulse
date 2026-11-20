"""Reddit via the official Data API (OAuth, read-only "script" app).

Setup: https://www.reddit.com/prefs/apps -> create "script" app.
Env: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
Free tier is for non-commercial use; a commercial deployment needs Reddit's data agreement.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from ..models import Post
from . import anon


def collect(cfg: dict) -> list[Post]:
    import praw  # official-API wrapper; handles OAuth + rate limiting

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "fanpulse/0.1 (research)"),
        ratelimit_seconds=60,
    )
    reddit.read_only = True

    subs = "+".join(cfg.get("subreddits", ["GTA6", "GTAVI", "GTA"]))
    queries = cfg.get("queries", ["bug", "please add", "wish", "fix", "annoying", "patch"])
    limit = int(cfg.get("limit_per_query", 100))
    comments_per_post = int(cfg.get("comments_per_post", 20))
    time_filter = cfg.get("time_filter", "week")

    seen: set[str] = set()
    out: list[Post] = []
    sub = reddit.subreddit(subs)

    for q in queries:
        for s in sub.search(q, sort="top", time_filter=time_filter, limit=limit):
            if s.id in seen:
                continue
            seen.add(s.id)
            out.append(Post(
                platform="reddit", id=f"t3_{s.id}", author=anon("reddit", str(s.author)),
                text=f"{s.title}\n{s.selftext or ''}".strip(),
                created_at=datetime.fromtimestamp(s.created_utc, tz=timezone.utc),
                likes=int(s.score), replies=int(s.num_comments),
                url=f"https://reddit.com{s.permalink}", source=f"r/{s.subreddit}",
            ))
            # Top comments often hold the clearest, most-upvoted version of a request.
            s.comment_sort = "top"
            s.comments.replace_more(limit=0)
            for c in s.comments[:comments_per_post]:
                if c.id in seen or not c.body or c.body in ("[deleted]", "[removed]"):
                    continue
                seen.add(c.id)
                out.append(Post(
                    platform="reddit", id=f"t1_{c.id}", author=anon("reddit", str(c.author)),
                    text=c.body, created_at=datetime.fromtimestamp(c.created_utc, tz=timezone.utc),
                    likes=int(c.score), replies=len(c.replies),
                    url=f"https://reddit.com{c.permalink}", source=f"r/{s.subreddit}",
                ))
    return out
