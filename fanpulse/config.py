"""One TOML per game (games/<game>.toml): sources, analysis settings, themes, optional code tracing.
Relative paths inside a config resolve against the project root."""
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "games" / "gta6.toml"


def load(path: str | None = None) -> dict:
    p = Path(path) if path else DEFAULT
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    cfg = tomllib.loads(p.read_text())
    cfg.setdefault("themes", {})
    return cfg


def resolve(p: str) -> Path:
    q = Path(p).expanduser()
    return q if q.is_absolute() else ROOT / q
