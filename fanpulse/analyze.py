"""Classify -> cluster -> rank, plus which direction players want each theme to move.

Ranking resists the classic social-listening traps:
  * one loud user posting 20 times      -> each author counts once per theme (their best post)
  * a single viral meme                 -> engagement is log-scaled, not linear
  * one platform's echo chamber         -> bonus for showing up on several platforms
  * last week's outrage                 -> recency decay (configurable half-life)
"""
from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from datetime import datetime, timezone

from . import llm
from .models import Cluster, Post
from .taxonomy import BUG_CUES, DECREASE, INCREASE, NEG, POS, compile_themes

log = logging.getLogger("fanpulse.analyze")
_rx = lambda pats: [re.compile(p, re.I) for p in pats]  # noqa: E731
_NEG, _POS, _BUG, _DEC, _INC = map(_rx, (NEG, POS, BUG_CUES, DECREASE, INCREASE))


def match_theme(text: str, compiled: dict[str, list[re.Pattern]]) -> str | None:
    hits = {tid: sum(1 for p in pats if p.search(text)) for tid, pats in compiled.items()}
    best = max(hits, key=hits.get, default=None)
    return best if best and hits[best] else None


def sentiment(text: str) -> float:
    n = sum(1 for p in _NEG if p.search(text))
    pos = sum(1 for p in _POS if p.search(text))
    return 0.0 if n + pos == 0 else (pos - n) / (pos + n)


_SENTENCE = re.compile(r"(?<=[.!?\n])\s+")


def direction(text: str, scope: list[re.Pattern] | None = None) -> int:
    """-1 = players want less of the theme's quantity, +1 = more, 0 = unclear.
    With `scope` (the theme's patterns), only sentences about the theme count: in long reviews,
    "more"/"less" elsewhere is usually about something else."""
    if scope:
        text = " ".join(s for s in _SENTENCE.split(text) if any(p.search(s) for p in scope))
    if any(p.search(text) for p in _DEC):
        return -1
    return 1 if any(p.search(text) for p in _INC) else 0


def post_weight(p: Post, now: datetime, half_life_h: float) -> float:
    age_h = max(0.0, (now - p.created_at).total_seconds() / 3600)
    return (1 + math.log1p(max(p.likes, 0)) + 0.5 * math.log1p(max(p.replies, 0))) * 0.5 ** (age_h / half_life_h)


def _best_per_author(posts: list[Post], now: datetime, half_life_h: float) -> dict[str, tuple[float, Post]]:
    best: dict[str, tuple[float, Post]] = {}
    for p in posts:
        w = post_weight(p, now, half_life_h)
        if w > best.get(p.author, (0.0, None))[0]:
            best[p.author] = (w, p)
    return best


def intent(c: Cluster, *, now: datetime, half_life_h: float = 48.0, scope: list[re.Pattern] | None = None,
           labels: dict[str, int] | None = None) -> dict:
    """Weighted vote on direction, one vote per player. agreement = share of decided votes.
    `labels` (post id -> -1/0/1, e.g. from the LLM) override the keyword rules where present."""
    votes, players = {-1: 0.0, 0: 0.0, 1: 0.0}, {-1: 0, 0: 0, 1: 0}
    for w, p in _best_per_author(c.posts, now, half_life_h).values():
        d = labels[p.id] if labels and p.id in labels else direction(p.text, scope)
        votes[d] += w
        players[d] += 1
    decided = votes[-1] + votes[1]
    d = (-1 if votes[-1] >= votes[1] else 1) if decided else 0
    heads = players[-1] + players[1]
    return {"direction": d, "agreement": round(votes[d] / decided, 3) if decided else 0.0,
            "headcount_agreement": round(players[d] / heads, 3) if heads else 0.0,
            "players_less": players[-1], "players_more": players[1], "players_unclear": players[0]}


def _dedupe(posts: list[Post]) -> list[Post]:
    seen, out = set(), []
    for p in posts:
        key = (p.author, re.sub(r"\W+", " ", p.text.lower()).strip()[:200])
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def cluster_posts(posts: list[Post], themes: dict, *, use_llm: bool = True, half_life_h: float = 48.0,
                  now: datetime | None = None) -> list[Cluster]:
    now = now or datetime.now(timezone.utc)
    compiled = compile_themes(themes)
    meta = {tid: {"title": t["title"], "kind": t["kind"]} for tid, t in themes.items()}
    buckets: dict[str, list[Post]] = defaultdict(list)
    unmatched: list[Post] = []
    for p in _dedupe(posts):
        tid = match_theme(p.text, compiled)
        (buckets[tid] if tid else unmatched).append(p)

    if use_llm and unmatched and llm.available():
        for start in range(0, len(unmatched), 50):
            chunk = unmatched[start:start + 50]
            try:
                for lab in llm.classify([p.text for p in chunk], list(themes)):
                    i, theme = lab.get("i"), lab.get("theme", "none")
                    if theme == "none" or not isinstance(i, int) or i >= len(chunk):
                        continue
                    buckets[theme].append(chunk[i])
                    meta.setdefault(theme, {"title": lab.get("title") or theme.removeprefix("new:"),
                                            "kind": lab.get("kind", "feature_request")})
            except Exception as exc:
                log.warning("LLM classification skipped: %s", exc)
                break

    clusters = []
    for tid, ps in buckets.items():
        c = Cluster(theme_id=tid, title=meta[tid]["title"], kind=meta[tid]["kind"], posts=ps)
        for p in ps:
            c.platforms[p.platform] = c.platforms.get(p.platform, 0) + 1
        best = _best_per_author(ps, now, half_life_h)
        c.score = sum(w for w, _ in best.values()) * (1 + 0.15 * (len(c.platforms) - 1))
        c.sentiment = sum(sentiment(p.text) for p in ps) / len(ps)
        if c.kind != "ops" and sum(1 for p in ps if any(b.search(p.text) for b in _BUG)) > len(ps) / 2:
            c.kind = "bug"
        clusters.append(c)
    return sorted(clusters, key=lambda c: c.score, reverse=True)
