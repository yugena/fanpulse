"""Feature requests -> drafted code change -> verified against acceptance checks.

  spec   games/<game>/features/<id>.toml: what players asked for, real evidence, acceptance checks
  draft  the LLM reads the spec plus the most relevant source files and returns exact find/replace edits
  verify apply the edits to copies, compile and run the game's probe, evaluate every check vs the baseline

Checks (all must pass):
  {metric, at_least | at_most}               absolute value after the change
  {metric, change_at_least | change_at_most} relative change vs baseline (e.g. -0.15 = at least 15% lower)
  {metric, within}                           guardrail: relative change stays inside +/- value
"""
from __future__ import annotations

import difflib
import json
import tomllib
from pathlib import Path

from . import llm
from collections import Counter

from .codeindex import expand, rank_files, tokens
from .config import resolve
from .tracer import probe_cmd, probe_files


class EditError(ValueError):
    pass


def load_spec(path: str) -> dict:
    spec = tomllib.loads(resolve(path).read_text())
    spec.setdefault("checks", [])
    return spec


def locate(spec: dict, cfg: dict, top: int = 2) -> list[str]:
    """Spec's `files` if given, else the files that best match the title (weight 2) plus the words used most
    across the request and the players' own quotes (weight 1): same approach as tracer.words_for."""
    if spec.get("files"):
        return spec["files"]
    repo = resolve(cfg["trace"]["repo"])
    freq = Counter(t for t in tokens(" ".join([spec["request"], *spec.get("evidence", [])])) if len(t) > 3)
    words = {**{w: 1.0 for w, _ in freq.most_common(8)}, **{w: 2.0 for w in spec["title"].split()}}
    ranked, _ = rank_files(repo, cfg["trace"]["sources"], expand(words))
    return [str(f.relative_to(repo)) for _, f in ranked[:top]]


DRAFT_SYSTEM = """You are a senior gameplay programmer implementing a player-requested feature in an existing
codebase. Make the smallest change that delivers the request, in the codebase's existing style. Keep every
other behaviour identical: same random-number call order, same values, same public API. Add a one-line
comment explaining the new behaviour. The change must satisfy the acceptance checks.
Respond with JSON only: {"summary": "<2 sentences>", "edits": [{"file": "<path>", "find": "<exact text>",
"replace": "<new text>"}]}. Each `find` must appear EXACTLY ONCE in that file, copied character for character."""


def draft(spec: dict, cfg: dict, previous: dict | None = None) -> dict:
    repo = resolve(cfg["trace"]["repo"])
    files = locate(spec, cfg)
    parts = [f"Request: {spec['request']}", "What players said:", *[f"- {q}" for q in spec.get("evidence", [])],
             f"Acceptance checks (measured by running the game): {json.dumps(spec['checks'])}",
             spec.get("notes", "")]
    if previous:
        parts.append(f"Your previous attempt fell short (failed checks and/or players it didn't help):\n"
                     f"{json.dumps(previous)[:6000]}\nFix it.")
    parts += [f"=== {f} ===\n{(repo / f).read_text()}" for f in files]
    out = llm.ask(DRAFT_SYSTEM, "\n\n".join(parts), max_tokens=32000)
    return {"author": llm.MODEL, "files_read": files, **out}


def apply_edits(repo: Path, edits: list[dict]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for e in edits:
        text = texts.get(e["file"]) or (repo / e["file"]).read_text()
        if (n := text.count(e["find"])) != 1:
            raise EditError(f"edit for {e['file']} matches {n} places (needs exactly 1): {e['find'][:80]!r}")
        texts[e["file"]] = text.replace(e["find"], e["replace"])
    return texts


def _check(c: dict, before: dict, after: dict) -> tuple[bool, str]:
    m = c["metric"]
    v, rel = after[m], (after[m] - before[m]) / before[m] if before[m] else float("inf")
    if "at_least" in c:
        return v >= c["at_least"], f"{m} = {v:.3g} (need ≥ {c['at_least']})"
    if "at_most" in c:
        return v <= c["at_most"], f"{m} = {v:.3g} (need ≤ {c['at_most']})"
    if "change_at_most" in c:
        return rel <= c["change_at_most"], f"{m} {rel:+.1%} (need ≤ {c['change_at_most']:+.0%})"
    if "change_at_least" in c:
        return rel >= c["change_at_least"], f"{m} {rel:+.1%} (need ≥ {c['change_at_least']:+.0%})"
    return abs(rel) <= c["within"], f"{m} {rel:+.1%} (must stay within ±{c['within']:.0%})"


def verify(spec: dict, cfg: dict, proposal: dict) -> dict:
    repo = resolve(cfg["trace"]["repo"])
    try:
        texts = apply_edits(repo, proposal["edits"])
    except (EditError, KeyError, FileNotFoundError) as e:
        return {"passed": False, "error": f"edits don't apply: {e}"}
    runs = probe_files(probe_cmd(cfg), {"base": {}, "draft": texts})
    before, after = runs["base"], runs["draft"]
    if "error" in after:
        return {"passed": False, "error": f"game code didn't compile or run: {after['error']}"}
    checks = [{"check": c, "passed": ok, "detail": d} for c in spec["checks"] for ok, d in [_check(c, before, after)]]
    diff = "".join("".join(difflib.unified_diff((repo / f).read_text().splitlines(True), t.splitlines(True), f"a/{f}", f"b/{f}"))
                   for f, t in sorted(texts.items()))
    return {"passed": all(c["passed"] for c in checks), "checks": checks, "before": before, "after": after, "diff": diff}


def to_markdown(spec: dict, proposal: dict, result: dict) -> str:
    md = [f"# Feature: {spec['title']}", "", f"**Request:** {spec['request']}", "",
          f"**Player evidence:** {spec.get('demand', '')}", ""]
    md += [f"> {q}" for q in spec.get("evidence", [])[:4]] + [""]
    md += [f"**Draft by:** {proposal.get('author', '?')}. {proposal.get('summary', '')}", "",
           f"## Verification: {'✅ PASSED' if result['passed'] else '❌ FAILED'}", ""]
    if result.get("error"):
        return "\n".join(md + [f"_{result['error']}_", ""])
    md += [f"- {'✓' if c['passed'] else '✗'} {c['detail']}" for c in result["checks"]]
    md += ["", "| Metric | Before | After | Change |", "|---|---|---|---|"]
    b, a = result["before"], result["after"]
    md += [f"| {k} | {b[k]:,.3f} | {a[k]:,.3f} | {(a[k] - b[k]) / b[k]:+.1%} |" if b[k] else f"| {k} | {b[k]:,.3f} | {a[k]:,.3f} | new |"
           for k in b]
    return "\n".join(md + ["", "```diff", result["diff"].rstrip(), "```", ""])
