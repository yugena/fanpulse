"""Turn one ranked need into the change that best answers the players who raised it.

  route   which kind of work answers it: tune numbers, new code (feature), new art, or design only.
          Only metrics the probe really measures count; a need nothing can measure is flagged, not faked.
  spec    acceptance checks written from the players' own words against the measured baseline,
          plus the game's guardrails so a fix for one group can't quietly hurt everyone else
  build   tune -> the numeric tracer; feature -> draft, then compile and run the game
  judge   every player's quote is checked against the change: yes / partly / no / different.
          yes or partly must cite a line the change actually adds, or it counts as no. "different" means
          the player asked for something else (a merge mistake) and is left out of the denominator.
  repair  failed checks plus the players still not addressed go back into the next draft; best round wins.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import feature, llm, tracer
from .analyze import intent
from .models import Cluster, Post

ROUTE_SYSTEM = """You plan work on a player need for the game {game}. Pick ONE track:
  tune    - only existing numbers need to change (more/less, faster/slower). Possible for areas: {tune}
  feature - new or changed game behaviour (code)
  art     - mainly needs new visuals (sprites, effects)
  design  - UI, tutorial, store, platform or social issues: nothing in the measurable list can show it
Measurable by running the game: {metrics}
Respond as JSON: {{"track":"...","direction":-1|1 (tune only: -1 less/easier, 1 more/harder),
"metrics":["<names from the measurable list that would show the need is met>"],"also_art":true|false,
"why":"<one sentence>","missing_measure":"<if nothing listed can show it, what would>"}}"""

SPEC_SYSTEM = """Write acceptance checks for a change to {game} that answers a player need. Use ONLY these metrics
(name: meaning, current value): {metrics}. Check forms: {{"metric":m,"at_least":v}}, {{"metric":m,"at_most":v}},
{{"metric":m,"change_at_least":r}}, {{"metric":m,"change_at_most":r}} (r relative, -0.15 = 15% lower).
Set each threshold from what the players actually describe: how much, how often, which part of the game.
Respond as JSON: {{"id":"<snake_case>","title":"<short>","request":"<the change, 1-2 sentences>",
"checks":[...],"notes":"<where in the code it likely lives, if you know>"}}"""

JUDGE_SYSTEM = """A change was made to {game} to answer the player need "{need}".
The change (unified diff):
{diff}
Measured by running the game (before -> after): {measured}
For each player quote, decide whether THIS change addresses what THAT player complained about or asked for:
  yes       - it fixes their specific complaint
  partly    - it helps but leaves part of their complaint
  no        - their complaint is about this need, but the change doesn't fix it for them
  different - they are asking for something else entirely
For yes/partly, `line` must be copied exactly from a + line of the diff that does it.
Respond as JSON: {{"players":[{{"i":<index>,"verdict":"...","line":"...","why":"<short>"}}]}}"""

CHECK_KEYS = {"at_least", "at_most", "change_at_least", "change_at_most", "within"}
VERDICTS = ("yes", "partly", "no", "different")


def _added(diff: str) -> str:
    return "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))


def route(need: dict, cfg: dict) -> dict:
    it = cfg["iterate"]
    r = llm.ask(ROUTE_SYSTEM.format(game=cfg.get("game", ""), tune=", ".join(it.get("tune", {})) or "none",
                                    metrics=json.dumps(it["metrics"])),
                json.dumps({"need": need["need"], "area": need["theme"], "players": need["players"],
                            "quotes": [e["quote"] for e in need["evidence"][:12]]}))
    r["metrics"] = [m for m in r.get("metrics", []) if m in it["metrics"]]
    if r.get("track") == "tune" and (need["theme"] not in it.get("tune", {}) or r.get("direction") not in (-1, 1)):
        r["track"] = "feature"  # the tuner only has levers for configured areas
    if r.get("track") in ("tune", "feature") and not r["metrics"]:
        r["track"], r["unmeasurable"] = "design", True  # never claim a fix nothing can measure
    if r.get("track") not in ("tune", "feature", "art", "design"):
        r["track"] = "design"
    return r


def spec_for(need: dict, cfg: dict, baseline: dict) -> dict:
    it = cfg["iterate"]
    metrics = {m: f"{d} (now {baseline.get(m, '?')})" for m, d in it["metrics"].items()}
    s = llm.ask(SPEC_SYSTEM.format(game=cfg.get("game", ""), metrics=json.dumps(metrics)),
                json.dumps({"need": need["need"], "players": need["players"],
                            "quotes": [e["quote"] for e in need["evidence"][:15]]}))
    checks = [c for c in s.get("checks", []) if c.get("metric") in it["metrics"]
              and len(CHECK_KEYS & c.keys()) == 1 and all(isinstance(c[k], (int, float)) for k in CHECK_KEYS & c.keys())]
    checked = {c["metric"] for c in checks}
    checks += [g for g in it.get("guardrails", []) if g["metric"] not in checked]
    return {"id": s.get("id") or "need", "title": s.get("title") or need["need"], "request": s.get("request") or need["need"],
            "demand": f"{need['players']} players ({need['quit']} say it made them quit).",
            "evidence": [e["quote"] for e in need["evidence"][:8]], "notes": s.get("notes", ""), "checks": checks}


def judge(need: dict, cfg: dict, diff: str, before: dict, after: dict, limit: int = 60) -> dict:
    """Per-player verdicts. Coverage = (yes + half of partly) / players this need is really about."""
    measured = {m: [before[m], after[m]] for m in before if m in after}
    system = JUDGE_SYSTEM.format(game=cfg.get("game", ""), need=need["need"], diff=diff[:12000], measured=json.dumps(measured))
    ev = need["evidence"][:limit]
    added = _added(diff)
    rows = []
    for e, got in zip(ev, llm.per_item(system, [e["quote"] for e in ev], "players", batch=15)):
        g = got[0] if got else {}
        v = g.get("verdict") if g.get("verdict") in VERDICTS else "no"
        line = str(g.get("line", "")).strip()
        unsupported = v in ("yes", "partly") and not (line and line in added)
        rows.append({"post": e["post"], "quote": e["quote"], "verdict": "no" if unsupported else v,
                     "why": g.get("why", "") + (" [claimed fix not found in the diff]" if unsupported else "")})
    about = [r for r in rows if r["verdict"] != "different"]
    score = sum({"yes": 1, "partly": 0.5}.get(r["verdict"], 0) for r in about) / max(len(about), 1)
    return {"coverage": round(score, 3), "judged": len(rows), "about_this_need": len(about),
            "counts": {v: sum(r["verdict"] == v for r in rows) for v in VERDICTS}, "players": rows}


def _tune(need: dict, rt: dict, cfg: dict, by_id: dict[str, Post]) -> dict:
    theme = cfg["iterate"]["tune"][need["theme"]]
    posts = [by_id[e["post"]] for e in need["evidence"] if e["post"] in by_id]
    labels = {p.id: rt["direction"] for p in posts}
    c = Cluster(theme_id=theme, title=need["need"], kind="balance", posts=posts)
    now = max((p.created_at for p in posts), default=datetime.now(timezone.utc))
    r = tracer.trace(c, intent(c, now=now, half_life_h=cfg.get("analysis", {}).get("half_life_hours", 48), labels=labels),
                     cfg, [], labels)
    if not r.change:
        return {"passed": False, "error": r.note or "no lever moved the metric", "trace": r.to_dict()}
    return {"passed": True, "diff": r.change["diff"], "before": r.change["before"], "after": r.change["after"],
            "trace": r.to_dict()}


def run(need: dict, cfg: dict, posts: list[Post]) -> dict:
    it, by_id = cfg["iterate"], {p.id: p for p in posts}
    rt = route(need, cfg)
    out = {"need": need, "route": rt, "rounds": []}
    if rt["track"] in ("art", "design"):
        return out  # a brief for people, not code; report says what would make it measurable
    if rt["track"] == "tune":
        res = _tune(need, rt, cfg, by_id)
        if "diff" in res:
            res["coverage"] = judge(need, cfg, res["diff"], res["before"], res["after"])
        out["rounds"].append(res)
        out["best"] = 0
        return out

    baseline = tracer.probe_files(tracer.probe_cmd(cfg), {"base": {}})["base"]
    spec = out["spec"] = spec_for(need, cfg, baseline)
    target, previous, best = it.get("coverage_target", 0.7), None, None
    for n in range(it.get("max_rounds", 3)):
        draft = feature.draft(spec, cfg, previous)
        if any(x["draft"].get("edits") == draft.get("edits") for x in out["rounds"]):
            break  # the model repeated an earlier attempt: another run of it adds nothing
        res = feature.verify(spec, cfg, draft)
        res["draft"] = draft
        if "diff" in res:
            res["coverage"] = judge(need, cfg, res["diff"], res["before"], res["after"])
        out["rounds"].append(res)
        cov = res.get("coverage", {}).get("coverage", 0)
        if best is None or (res["passed"], cov) > (out["rounds"][best]["passed"], out["rounds"][best].get("coverage", {}).get("coverage", 0)):
            best = n
        if res["passed"] and cov >= target:
            break
        previous = {"edits": draft.get("edits"), "error": res.get("error"),
                    "failed_checks": [c["detail"] for c in res.get("checks", []) if not c["passed"]],
                    "players_not_addressed": [{"quote": p["quote"], "why": p["why"]}
                                              for p in res.get("coverage", {}).get("players", []) if p["verdict"] in ("no", "partly")][:12]}
    out["best"] = best
    return out


def to_markdown(r: dict, cfg: dict) -> str:
    need, rt = r["need"], r["route"]
    md = [f"# Need: {need['need']}", "",
          f"**{need['players']} players** ({need['quit']} say it made them quit, {need['helpful']} helpful votes). "
          f"Area: {need['theme']}.", "", *[f"> {e['quote']}" for e in need["evidence"][:4]], "",
          f"**Track:** {rt['track']}. {rt.get('why', '')}"]
    if rt.get("unmeasurable") or rt["track"] in ("art", "design"):
        md += ["", f"_Not code-verifiable with the current probe. What would measure it: "
                   f"{rt.get('missing_measure') or 'n/a'}._" + (" Needs new art: run `fanpulse art`." if rt["track"] == "art" or rt.get("also_art") else "")]
        return "\n".join(md) + "\n"
    if "spec" in r:
        md += ["", "**Acceptance checks (from the players' words + guardrails):**",
               *[f"- `{json.dumps(c)}`" for c in r["spec"]["checks"]]]
    md += ["", "| Round | Checks | Players addressed | yes / partly / no / different |", "|---|---|---|---|"]
    for i, x in enumerate(r["rounds"], 1):
        c = x.get("coverage", {})
        k = c.get("counts", {})
        md.append(f"| {i}{' ★' if i - 1 == r.get('best') else ''} | {'pass' if x['passed'] else 'fail: ' + (x.get('error') or ', '.join(ch['detail'] for ch in x.get('checks', []) if not ch['passed']))[:120]} "
                  f"| {c.get('coverage', 0):.0%} | {' / '.join(str(k.get(v, 0)) for v in VERDICTS)} |")
    if (j := next((x["coverage"] for x in r["rounds"] if "coverage" in x), None)) and j["judged"] < need["players"]:
        md += ["", f"_Judged the {j['judged']} most-endorsed of {need['players']} players._"]
    if r.get("best") is not None and (b := r["rounds"][r["best"]]).get("diff"):
        left = [p for p in b.get("coverage", {}).get("players", []) if p["verdict"] in ("no", "partly")]
        other = [p for p in b.get("coverage", {}).get("players", []) if p["verdict"] == "different"]
        if left:
            md += ["", "## Still not addressed", *[f"- \"{' '.join(p['quote'].split())[:160]}\" ({p['why']})" for p in left[:8]]]
        if other:
            md += ["", f"## Asking for something else ({len(other)}: likely a separate need)",
                   *[f"- \"{' '.join(p['quote'].split())[:160]}\"" for p in other[:5]]]
        md += ["", "```diff", b["diff"].rstrip(), "```"]
    return "\n".join(md) + "\n"
