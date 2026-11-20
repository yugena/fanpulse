"""Steam user reviews via IUserReviewsService/GetAppReviews (replaced /appreviews in Oct 2026).

No API key needed (a publisher key only raises the rate limit). Pages with a cursor using the
Recent sort, which is the one that ends with an empty page. Standard library only, so it also runs
as a standalone fetcher on any machine with Python 3.9+:
    python3 -m fanpulse.collectors.steam --appid 1127400 --out reviews.json
Config: appid, max_reviews=5000, languages=["english"], review_type=0 (0 all / 1 positive / 2 negative),
  min_playtime_hours, date_start/date_end (unix seconds), key (optional, or env STEAM_PUBLISHER_KEY)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from typing import Callable

from ..models import Post
from ..net import json_request
from . import anon

URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
RECENT, ALL_PURCHASES = 1, 1


def collect(cfg: dict, fetch: Callable[[str], dict] = json_request) -> list[Post]:
    query = {"appid": int(cfg["appid"]), "filter": RECENT, "purchase_type": ALL_PURCHASES, "num_per_page": 100,
             "languages": cfg.get("languages", ["english"]), "review_type": int(cfg.get("review_type", 0))}
    if "min_playtime_hours" in cfg:
        query["playtime_min_hours"] = int(cfg["min_playtime_hours"])
    if "date_start" in cfg and "date_end" in cfg:
        query.update(date_range_start=int(cfg["date_start"]), date_range_end=int(cfg["date_end"]))
    key = cfg.get("key") or os.environ.get("STEAM_PUBLISHER_KEY")
    limit, cursor, out = int(cfg.get("max_reviews", 5000)), "*", []

    while len(out) < limit:
        params = {"input_json": json.dumps({**query, "cursor": cursor}), **({"key": key} if key else {})}
        raw = fetch(f"{URL}?{urllib.parse.urlencode(params)}")
        body = raw.get("response", raw)  # Web API wraps results in "response"
        page = body.get("reviews", [])
        out += [_post(rv, query["appid"]) for rv in page if rv.get("review")]
        if not page or not body.get("cursor") or body["cursor"] == cursor:
            break
        cursor = body["cursor"]
        print(f"\r  {len(out):,} reviews", end="", file=sys.stderr)
    print(file=sys.stderr)
    return out[:limit]


def _post(rv: dict, appid: int) -> Post:
    return Post(platform="steam", id=str(rv["recommendationid"]),
                author=anon("steam", str(rv.get("author", {}).get("steamid"))), text=rv["review"],
                created_at=datetime.fromtimestamp(int(rv["timestamp_created"]), tz=timezone.utc),
                likes=int(rv.get("votes_up", 0)), replies=int(rv.get("comment_count", 0)),
                source=f"steam:{appid}:{'positive' if rv.get('voted_up') else 'negative'}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Save a game's Steam reviews as FanPulse posts (authors anonymized).")
    ap.add_argument("--appid", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=20000)
    ap.add_argument("--min-playtime-hours", type=int, default=1)
    a = ap.parse_args()
    posts = collect({"appid": a.appid, "max_reviews": a.max, "min_playtime_hours": a.min_playtime_hours})
    with open(a.out, "w") as f:
        json.dump([p.to_dict() for p in posts], f)
    print(f"saved {len(posts):,} reviews to {a.out}")
