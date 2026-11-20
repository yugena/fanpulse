"""Find the numbers in a codebase that might control what players are talking about.

Two steps, both cheap and language-agnostic (Java / C++ / C# / Python sources):
  1. rank files by TF-IDF overlap with the theme's vocabulary (identifiers are split on camelCase/_),
  2. inside the top files, list numeric literals in code, scored by how much theme vocabulary sits
     on or just above their line (field docs, the variable name, nearby comments).
This only proposes candidates. Whether a number actually matters is decided by the probe (tracer.py).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Bridges player words to the words programmers use for the same thing. Game-agnostic on purpose;
# an LLM can extend it per theme (see tracer.expand_terms).
VOCAB = {
    "enemy": ["enemy", "spawn", "unit", "wave", "hostile", "attack"],
    "wave": ["wave", "spawn", "group", "scaling"],
    "hard": ["difficulty", "scaling", "health", "shield", "damage", "amount", "max"],
    "easy": ["difficulty", "scaling", "health", "shield", "damage", "amount"],
    "cop": ["police", "cop", "wanted", "dispatch", "spawn", "pursuit"],
    "boss": ["boss", "guardian", "tier"],
    "fast": ["speed", "spacing", "time", "interval", "delay", "timer"],
    "many": ["amount", "count", "max", "spawn", "scaling", "density"],
    "tank": ["health", "armor", "shield"],
}
_TOKEN = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])")
_NUM = re.compile(r"(?<![\w.$])(\d+\.\d+|\d+\.(?!\w)|\.\d+|\d+)([fFdDlL]?)(?![\w.])")
_STRING = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_SKIP = re.compile(r"^\s*(import|package|#include|@|//|\*|/\*)")
_STOP = {"too", "the", "and", "want", "make", "game", "get", "it", "is", "so", "way", "just", "really"}


@dataclass
class Site:
    file: str          # path relative to the repo root
    line: int          # 1-based
    start: int         # column span of the literal (without suffix)
    end: int
    literal: str
    suffix: str
    code: str
    context: str       # doc/comments/name words found near the literal
    score: float = 0.0


def _stem(t: str) -> str:
    t = t.lower()
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    return t[:-1] if t.endswith("s") and not t.endswith("ss") else t


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text) if len(t) > 1]


def expand(words: dict[str, float]) -> dict[str, float]:
    """Player words (with weights) plus their programmer synonyms at half weight."""
    out: dict[str, float] = {}
    for word, w in words.items():
        for t in tokens(word):
            if t in _STOP:
                continue
            out[t] = max(out.get(t, 0), w)
            for syn in VOCAB.get(t, []):
                out[_stem(syn)] = max(out.get(_stem(syn), 0), w / 2)
    return out


def rank_files(repo: Path, globs: list[str], terms: dict[str, float]) -> tuple[list[tuple[float, Path]], dict[str, float]]:
    """Returns ranked files and each term's weight (theme weight x IDF) for scoring lines."""
    files = [f for g in globs for f in repo.glob(g) if f.is_file()]
    counts = {f: Counter(tokens(f.read_text(errors="ignore"))) for f in files}
    n = len(files)
    weight = {t: w * math.log((n + 1) / (1 + sum(1 for c in counts.values() if t in c))) for t, w in terms.items()}
    scored = [(sum(math.log1p(c[t]) * weight[t] for t in terms), f) for f, c in counts.items()]
    return sorted((s, f) for s, f in scored if s > 0)[::-1], weight


def sites(repo: Path, file: Path, idf: dict[str, float], file_score: float) -> list[Site]:
    lines = file.read_text(errors="ignore").splitlines()
    out = []
    for i, raw in enumerate(lines):
        if _SKIP.match(raw):
            continue
        code = raw.split("//")[0]
        masked = _STRING.sub(lambda m: " " * len(m.group()), code)
        found = list(_NUM.finditer(masked))
        if not found:
            continue
        own = {t for t in tokens(code) if t in idf}
        near = {t for t in tokens(" ".join(lines[max(0, i - 3):i])) if t in idf} - own
        relevance = 2 * sum(idf[t] for t in own) + sum(idf[t] for t in near)
        if not relevance:
            continue
        for m in found:
            if float(m.group(1)) == 0:  # scaling zero changes nothing
                continue
            out.append(Site(file=str(file.relative_to(repo)), line=i + 1, start=m.start(1), end=m.end(1),
                            literal=m.group(1), suffix=m.group(2), code=raw.strip(),
                            context=" ".join(sorted(own | near)), score=file_score * relevance))
    return out


def candidates(repo: Path, globs: list[str], words: dict[str, float], *, max_files: int = 4, max_sites: int = 60) -> list[Site]:
    ranked, weight = rank_files(repo, globs, expand(words))
    per_file = max(10, max_sites // 2)  # keep room for levers outside the top file
    found = [s for score, f in ranked[:max_files]
             for s in sorted(sites(repo, f, weight, score), key=lambda s: s.score, reverse=True)[:per_file]]
    return sorted(found, key=lambda s: s.score, reverse=True)[:max_sites]
