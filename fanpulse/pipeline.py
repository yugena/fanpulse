"""The functions the CLI and the Muse connector both call."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import collectors, llm, tracer
from .analyze import cluster_posts, intent
from .config import ROOT
from .models import Cluster, Post
from .report import build_html, build_markdown
from .taxonomy import compile_themes



def out_dir(cfg: dict) -> Path:
    """Each game gets its own output folder so scans and traces never mix."""
    d = ROOT / "out" / re.sub(r"\W+", "_", cfg.get("game", "game").lower()).strip("_")
    d.mkdir(parents=True, exist_ok=True)
    return d


def anchor(posts: list[Post]) -> datetime:
    """Demo data is a fixed snapshot: measure recency from its newest post so results never drift."""
    if posts and all(p.synthetic for p in posts):
        return max(p.created_at for p in posts)
    return datetime.now(timezone.utc)


def scan(cfg: dict) -> list[Cluster]:
    posts = collectors.run_all(cfg)
    a = cfg.get("analysis", {})
    clusters = cluster_posts(posts, cfg["themes"], use_llm=a.get("use_llm", True),
                             half_life_h=a.get("half_life_hours", 48), now=anchor(posts))
    (out_dir(cfg) / "last_scan.json").write_text(json.dumps({"game": cfg.get("game", ""), "clusters": [
        {"theme_id": c.theme_id, "title": c.title, "kind": c.kind, "score": c.score, "sentiment": c.sentiment,
         "platforms": c.platforms, "posts": [p.to_dict() for p in c.posts]} for c in clusters]}))
    return clusters


def load_cached(cfg: dict) -> list[Cluster]:
    return [Cluster(**{**d, "posts": [Post.from_dict(p) for p in d["posts"]]})
            for d in json.loads((out_dir(cfg) / "last_scan.json").read_text())["clusters"]]


def write_reports(clusters: list[Cluster], cfg: dict) -> tuple[Path, Path]:
    a = cfg.get("analysis", {})
    md = build_markdown(clusters, cfg["themes"], game=cfg.get("game", "Game"), top_n=a.get("top_n", 8),
                        allow_llm=a.get("use_llm", True))
    out = out_dir(cfg)
    (out / "report.md").write_text(md)
    (out / "report.html").write_text(build_html(md, f"FanPulse: {cfg.get('game', 'Game')}"))
    return out / "report.md", out / "report.html"


def traceable(clusters: list[Cluster], cfg: dict, theme_id: str | None = None) -> Cluster:
    """The given theme, or the highest-ranked theme that has a probe configured."""
    ok = [c for c in clusters if "trace" in cfg["themes"].get(c.theme_id, {})]
    pick = next((c for c in ok if c.theme_id == theme_id), None) if theme_id else (ok or [None])[0]
    if pick is None:
        raise SystemExit(f"No traceable theme {'named ' + theme_id if theme_id else 'in this scan'}; "
                         "add a [themes.<id>.trace] section and a probe.")
    return pick


def label(clusters: list[Cluster], cfg: dict, theme_id: str | None = None) -> Path:
    """Have the LLM read which way each player wants the theme to move; saves post id -> -1/0/1."""
    pick = traceable(clusters, cfg, theme_id)
    topic = cfg["themes"][pick.theme_id]["trace"].get("topic", pick.title)
    path = out_dir(cfg) / f"intent_labels_{pick.theme_id}.json"
    path.write_text(json.dumps(dict(zip((p.id for p in pick.posts), llm.directions([p.text for p in pick.posts], topic)))))
    return path


def trace(clusters: list[Cluster], cfg: dict, theme_id: str | None = None, labels: dict | None = None) -> tracer.TraceResult:
    pick = traceable(clusters, cfg, theme_id)
    a = cfg.get("analysis", {})
    scope = compile_themes({pick.theme_id: cfg["themes"][pick.theme_id]})[pick.theme_id]
    it = intent(pick, now=anchor(pick.posts), half_life_h=a.get("half_life_hours", 48), scope=scope, labels=labels)
    result = tracer.trace(pick, it, cfg, [c for c in clusters if c is not pick], labels)
    synthetic, out = any(p.synthetic for p in pick.posts), out_dir(cfg)
    md = tracer.to_markdown(result, pick.title, synthetic, cfg["themes"][pick.theme_id]["trace"].get("guardrails"))
    (out / f"trace_{pick.theme_id}.md").write_text(md)
    (out / f"trace_{pick.theme_id}.html").write_text(build_html(md, f"FanPulse trace: {pick.title}"))
    (out / f"trace_{pick.theme_id}.json").write_text(json.dumps(result.to_dict(), indent=1, default=str))
    if result.change:
        (out / f"trace_{pick.theme_id}.diff").write_text(result.change["diff"])
    return result
