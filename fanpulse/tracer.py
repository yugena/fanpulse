"""Player theme -> verified code change.

  candidate numbers (codeindex) -> run the game's own code with each one nudged +25% (probe)
  -> keep those that measurably move the theme's metric without side effects players didn't ask for
  -> solve the strongest lever's value for the change size players asked for, stacking up to 3 levers
  -> re-run to verify -> unified diff.

The probe is a game-provided command: `<probe...> <variant_dir|-> ...` printing one JSON line per
variant ({"variant": ..., "metrics": {...}} or {"variant": ..., "error": ...}). Each variant dir
holds patched copies of source files at their repo-relative paths. Nothing touches the real repo.
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .analyze import direction
from .codeindex import Site, candidates, tokens
from .config import ROOT, resolve
from .models import Cluster

NUDGE = 0.25           # probe each candidate at +25%
NOISE = 0.005          # effects under 0.5% count as "no measurable effect"
MAX_EDIT = (0.5, 2.0)  # never more than halve or double a designer's number
TOLERANCE = 0.2        # within 20% of the target change counts as hitting it
MAX_LEVERS = 3

Edit = tuple[Site, str]  # (where, new literal)


@dataclass
class Lever:
    site: Site
    factor: float             # actual new/old ratio tested (small integers can't move by exactly 25%)
    effect: dict[str, float]  # relative change per metric at that factor

    def elasticity(self, metric: str) -> float:
        return self.effect[metric] / (self.factor - 1)

    def side_effects(self, metric: str, guard: list[str] | None = None) -> list[str]:
        """Guarded metrics this lever would push the OTHER way while it moves `metric` the way players asked."""
        return [k for k, v in self.effect.items()
                if k != metric and (guard is None or k in guard) and abs(v) >= NOISE and v * self.effect[metric] < 0]


def opposed(after: dict, base: dict, metric: str, guard: list[str] | None) -> list[str]:
    """Same rule, checked on a final measured change (effects can turn non-linear beyond the +25% nudge)."""
    d = {k: (after[k] - base[k]) / base[k] for k in base if base[k]}
    return [k for k, v in d.items() if k != metric and (guard is None or k in guard) and abs(v) >= NOISE and v * d[metric] < 0]


@dataclass
class TraceResult:
    theme_id: str
    intent: dict
    metric: str
    target: float
    searched: int = 0
    measurable: int = 0
    levers: list[Lever] = field(default_factory=list)
    change: dict = field(default_factory=dict)   # edits, before, after, hit, diff
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- editing numbers in source
def _is_int(site: Site) -> bool:
    return "." not in site.literal and site.suffix in ("", "l", "L")


def scaled(site: Site, factor: float) -> str | None:
    old = float(site.literal)
    new = old * factor
    if _is_int(site):
        new = round(new)
        if new == old:  # integers need at least one step to move
            new = old + (1 if factor > 1 else -1)
        return None if new <= 0 < old else str(int(new))
    text = f"{new:.4f}".rstrip("0")
    return (text + "0" if text.endswith(".") else text) + site.suffix


def apply(repo: Path, edits: list[Edit]) -> dict[str, tuple[str, str]]:
    """file -> (original text, patched text). Edits on one line apply right-to-left so columns stay valid."""
    out = {}
    for file in {s.file for s, _ in edits}:
        old = (repo / file).read_text()
        lines = old.splitlines(keepends=True)
        for s, new in sorted((e for e in edits if e[0].file == file), key=lambda e: (e[0].line, e[0].start), reverse=True):
            ln = lines[s.line - 1]
            lines[s.line - 1] = ln[:s.start] + new + ln[s.end + len(s.suffix):]
        out[file] = (old, "".join(lines))
    return out


def probe(cmd: list[str], repo: Path, variants: dict[str, list[Edit]]) -> dict[str, dict]:
    """name -> edits ([] = baseline). Returns name -> metrics, or {'error': ...}."""
    return probe_files(cmd, {n: {f: t for f, (_, t) in apply(repo, e).items()} for n, e in variants.items()})


def probe_files(cmd: list[str], variants: dict[str, dict[str, str]]) -> dict[str, dict]:
    """name -> {repo-relative file: full patched text} ({} = baseline). Returns name -> metrics or {'error': ...}."""
    with tempfile.TemporaryDirectory(prefix="fanpulse-") as tmp:
        names = {}
        for name, files in variants.items():
            d = Path(tmp) / name
            for file, text in files.items():
                (d / file).parent.mkdir(parents=True, exist_ok=True)
                (d / file).write_text(text)
            names[str(d) if files else "-"] = name
        res = subprocess.run(cmd + list(names), cwd=ROOT, capture_output=True, text=True, timeout=1800)
    out = {}
    for line in res.stdout.splitlines():
        if line.startswith("{"):
            row = json.loads(line)
            out[names[row["variant"]]] = row.get("metrics") or {"error": row.get("error", "unknown")}
    if not out:
        raise RuntimeError(f"probe produced no results: {res.stderr[-500:]}")
    return out


def probe_cmd(cfg: dict) -> list[str]:
    return [str(resolve(a)) if a.startswith(("games/", "vendor/")) else a for a in cfg["trace"]["probe"]]


# ---------------------------------------------------------------- reading what players want
def words_for(cluster: Cluster, title: str, others: list[Cluster], top: int = 6) -> dict[str, float]:
    """The theme title (weight 2) plus the words players use distinctively for this theme (weight 1):
    share of this theme's posts using the word minus its share in every other theme."""
    def share(posts):
        df = Counter(t for p in posts for t in set(tokens(p.text)) if len(t) > 3)
        return {t: n / max(len(posts), 1) for t, n in df.items()}
    inside, outside = share(cluster.posts), share([p for c in others for p in c.posts])
    lift = sorted(inside, key=lambda t: inside[t] - outside.get(t, 0), reverse=True)[:top]
    return {**{w: 1.0 for w in lift}, **{w: 2.0 for w in title.split()}}


def focus_metric(cluster: Cluster, intent: dict, tcfg: dict, labels: dict[str, int] | None = None) -> str:
    """If players say *where* it hurts ("around wave 30"), measure that window instead of the whole run.
    focus = {pattern = 'regex with one number group', windows = [[upper_bound, "metric"], ...]}"""
    f = tcfg.get("focus")
    rx = re.compile(f["pattern"], re.I) if f else None
    wants = (lambda p: labels.get(p.id, 0)) if labels else (lambda p: direction(p.text, [rx]))
    nums = sorted(int(n) for p in cluster.posts if rx and wants(p) == intent["direction"] for n in rx.findall(p.text))
    if not nums:
        return tcfg["metric"]
    return next((m for bound, m in f["windows"] if nums[len(nums) // 2] <= bound), tcfg["metric"])


def target_change(intent: dict, lo: float, hi: float) -> float:
    strength = min(max((intent["agreement"] - 0.5) / 0.5, 0.0), 1.0)
    return intent["direction"] * (lo + (hi - lo) * strength)


# ---------------------------------------------------------------- the trace
def trace(cluster: Cluster, intent: dict, cfg: dict, others: list[Cluster] = (), labels: dict[str, int] | None = None) -> TraceResult:
    theme, gtrace = cfg["themes"][cluster.theme_id], cfg["trace"]
    tcfg, repo = theme["trace"], resolve(gtrace["repo"])
    guard = tcfg.get("guardrails")
    metric = focus_metric(cluster, intent, tcfg, labels)
    cmd = probe_cmd(cfg)
    r = TraceResult(cluster.theme_id, intent, metric,
                    round(target_change(intent, tcfg.get("min_change", 0.05), tcfg.get("max_change", 0.25)), 4))
    # Confidence gate: a few loud or recent posts must never be enough to change the game.
    need, agree = tcfg.get("min_players", 30), tcfg.get("min_agreement", 0.6)
    asked = intent["players_less"] + intent["players_more"]
    if not intent["direction"] or asked < need or min(intent["agreement"], intent["headcount_agreement"]) < agree:
        r.note = (f"Not confident enough to change code: {asked} players made a clear request (need {need}), "
                  f"agreement {intent['agreement']:.0%} weighted / {intent['headcount_agreement']:.0%} by headcount "
                  f"(need {agree:.0%} on both).")
        return r

    sites = candidates(repo, gtrace["sources"], words_for(cluster, theme["title"], list(others)),
                       max_files=gtrace.get("max_files", 4), max_sites=gtrace.get("max_sites", 80))
    trials = {f"s{i}": (s, new) for i, s in enumerate(sites) if (new := scaled(s, 1 + NUDGE))}
    runs = probe(cmd, repo, {"base": [], **{k: [e] for k, e in trials.items()}})
    base, r.searched = runs["base"], len(trials)
    for name, (site, new) in trials.items():
        m = runs.get(name) or {"error": "missing"}
        if "error" in m:
            continue
        effect = {k: round((m[k] - base[k]) / base[k], 4) for k in base if base[k]}
        if abs(effect.get(metric, 0)) >= NOISE:
            r.levers.append(Lever(site, round(float(new.rstrip("fFdDlL")) / float(site.literal), 4), effect))
    r.levers.sort(key=lambda lv: abs(lv.elasticity(metric)), reverse=True)
    r.measurable = len(r.levers)
    if not r.levers:
        r.note = "No candidate number measurably moved the metric; widen the search or the probe."
        return r

    # Guardrails: only levers with no opposing side effects, edits capped, stack levers until on target.
    edits, hit, after = [], 0.0, base
    for lv in [lv for lv in r.levers if not lv.side_effects(metric, guard)][:MAX_LEVERS] or r.levers[:1]:
        if abs(hit - r.target) <= TOLERANCE * abs(r.target):
            break
        step = _solve(cmd, repo, lv, metric, r.target, base, edits, hit)
        if step and abs(step[2] - r.target) < abs(hit - r.target) and not opposed(step[1], base, metric, guard):
            edits, after, hit = edits + [(lv.site, step[0])], step[1], step[2]
    if not edits:
        r.note = "No lever could be moved toward the target within the edit cap."
        return r
    if abs(hit - r.target) > TOLERANCE * abs(r.target):
        r.note = f"Closest safe change reaches {hit:+.1%} of the {r.target:+.1%} target within the edit cap."
    diff = "".join("".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), f"a/{f}", f"b/{f}"))
                   for f, (a, b) in sorted(apply(repo, edits).items()))
    r.change = {"edits": [{"file": s.file, "line": s.line, "code": s.code, "old": s.literal + s.suffix, "new": new}
                          for s, new in edits], "before": base, "after": after, "hit": round(hit, 4), "diff": diff}
    return r


def _solve(cmd, repo, lever: Lever, metric: str, target: float, base: dict, fixed: list[Edit], start: float):
    """Secant search on one lever's scale factor (on top of `fixed` edits). Returns (literal, metrics, hit)."""
    pts, best = [(1.0, start), (lever.factor, start + lever.effect[metric])], None
    for _ in range(4):
        (f0, e0), (f1, e1) = pts[-2], pts[-1]
        f = min(max(f1 + (target - e1) * (f1 - f0) / (e1 - e0) if e1 != e0 else f1, MAX_EDIT[0]), MAX_EDIT[1])
        new = scaled(lever.site, f)
        if new is None:
            break
        m = probe(cmd, repo, {"v": fixed + [(lever.site, new)]})["v"]
        if "error" in m:
            break
        e = (m[metric] - base[metric]) / base[metric]
        if best is None or abs(e - target) < abs(best[2] - target):
            best = (new, m, e)
        if abs(e - target) <= TOLERANCE * abs(target) or any(abs(f - p) < 1e-6 for p, _ in pts):
            break
        pts.append((f, e))
    return best


# ---------------------------------------------------------------- report
def to_markdown(r: TraceResult, title: str, synthetic: bool, guard: list[str] | None = None) -> str:
    i = r.intent
    want = {-1: "LESS", 1: "MORE", 0: "no clear direction"}[i["direction"]]
    md = [f"# From player feedback to code: {title}", ""]
    if synthetic:
        md += ["> ⚠️ **Demo feedback is synthetic.** The code search, patch and measurements are real.", ""]
    md += [f"**What players asked for:** {i['players_less']} want less, {i['players_more']} want more, "
           f"{i['players_unclear']} unclear → **{want}** (weighted agreement {i['agreement']:.0%}).",
           f"**Target:** {r.target:+.1%} on `{r.metric}` (size scaled by how strongly players agree).", "",
           f"**Search:** {r.searched} candidate numbers tested by running the game's own code; "
           f"{r.measurable} measurably moved `{r.metric}`.", ""]
    if r.note:
        md += [f"_{r.note}_", ""]
    if c := r.change:
        md += ["## Proposed change", ""]
        md += [f"- `{e['file']}:{e['line']}`: `{e['old']}` → `{e['new']}` in `{e['code']}`" for e in c["edits"]]
        md += ["", "Measured by running the patched game code:", "",
               "| Metric | Before | After | Change |", "|---|---|---|---|"]
        md += [f"| {k} | {b:,.1f} | {a:,.1f} | {f'{(a - b) / b:+.1%}' if b else '—'} |"
               for k in c["before"] for b, a in [(c["before"][k], c["after"][k])]]
        md += ["", "```diff", c["diff"].rstrip(), "```", ""]
    md += ["## All levers that measurably moved it (ranked by effect per % of change)", "",
           f"✗ = would push a guarded measure ({', '.join(guard) if guard else 'any'}) against what players asked for.", "",
           f"| Location | Code | Tested | {r.metric} | Other effects | Safe |", "|---|---|---|---|---|---|"]
    for lv in r.levers[:10]:
        s, bad = lv.site, lv.side_effects(r.metric, guard)
        others = ", ".join(f"{k} {v:+.1%}" for k, v in lv.effect.items() if k != r.metric and abs(v) >= NOISE)
        code = re.sub(r"\s+", " ", s.code)[:70].replace("|", "\\|")
        md.append(f"| `{Path(s.file).name}:{s.line}` | `{code}` | `{s.literal}{s.suffix}` ×{lv.factor:g} | "
                  f"{lv.effect[r.metric]:+.1%} | {others or '—'} | {'✗ ' + ', '.join(bad) if bad else '✓'} |")
    return "\n".join(md) + "\n"
