"""Shared data model: every collector normalizes into `Post`; analysis produces `Cluster`."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Post:
    platform: str            # reddit | discord | instagram | facebook | demo
    id: str
    author: str              # hashed/anonymized handle — never store raw PII
    text: str
    created_at: datetime
    likes: int = 0           # upvotes / reactions / likes
    replies: int = 0         # comment / reply count
    url: str = ""
    source: str = ""         # subreddit, channel, hashtag, page
    synthetic: bool = False  # True for demo data — must never be presented as real

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d

    @staticmethod
    def from_dict(d: dict) -> "Post":
        d = dict(d)
        ts = d["created_at"]
        d["created_at"] = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
        if d["created_at"].tzinfo is None:
            d["created_at"] = d["created_at"].replace(tzinfo=timezone.utc)
        return Post(**d)


@dataclass
class Cluster:
    theme_id: str
    title: str
    kind: str                         # bug | feature_request | qol | balance | performance
    posts: list[Post] = field(default_factory=list)
    score: float = 0.0
    sentiment: float = 0.0            # -1..1, rough
    platforms: dict[str, int] = field(default_factory=dict)

    @property
    def unique_authors(self) -> int:
        return len({p.author for p in self.posts})

    @property
    def total_engagement(self) -> int:
        return sum(p.likes + 2 * p.replies for p in self.posts)

    def top_examples(self, n: int = 3) -> list[Post]:
        return sorted(self.posts, key=lambda p: p.likes + 2 * p.replies, reverse=True)[:n]

    def summary(self) -> dict:
        return {
            "theme_id": self.theme_id,
            "title": self.title,
            "kind": self.kind,
            "score": round(self.score, 2),
            "mentions": len(self.posts),
            "unique_authors": self.unique_authors,
            "engagement": self.total_engagement,
            "sentiment": round(self.sentiment, 2),
            "platforms": self.platforms,
            "examples": [
                {"platform": p.platform, "text": p.text[:280], "likes": p.likes, "url": p.url,
                 "synthetic": p.synthetic}
                for p in self.top_examples()
            ],
        }
