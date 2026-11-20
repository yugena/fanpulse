"""Posts saved as JSON (e.g. by `python -m fanpulse.collectors.steam --out ...`, or the demo sets).

Config: path, synthetic (bool). Demo sets are SYNTHETIC: they're flagged all the way through to the
report and must never be presented as real player posts.
"""
from __future__ import annotations

import json

from ..config import resolve
from ..models import Post


def collect(cfg: dict) -> list[Post]:
    posts = [Post.from_dict(r) for r in json.loads(resolve(cfg["path"]).read_text())]
    for p in posts:
        p.synthetic = bool(cfg.get("synthetic", False))
    return posts
