"""Specific player needs, in their own words, ranked by how many different players share them.

1. select   – negative reviews plus any review that asks for something (rules; cheap, high recall)
2. extract  – Muse lists each specific need with the exact sentence that shows it (checkpointed, resumable)
3. verify   – a need whose quote isn't really in the review is dropped and counted as a hallucination
4. merge    – Muse groups differently worded needs inside each theme into one plain-language need
5. rank     – one vote per player per need; ties broken by quit/refund mentions, then helpful votes
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import llm
from .models import Post

REQUEST = re.compile(r"\b(i wish|wish (there|it|they|you)|please (add|make|fix|bring)|would be (nice|great|cool|better)|"
                     r"should (add|be|have|let|make)|needs? (a|an|more|to|better)|would love|add (a|an|more|some)|"
                     r"hope (they|the dev)|why can'?t|let us|bring back|remove the|if only)\b", re.I)

EXTRACT_SYSTEM = """You read Steam reviews of the game {game} and list what each player NEEDS changed or added.
A need is one specific, actionable change in plain words ("warning before boss waves", "undo for building"),
not a mood ("game is bad"). Skip praise, chatter and vague complaints. At most 3 needs per review.
For each need give:
  theme: one of {themes}, or "new:<short_snake_case>" if none fits
  need:  the change, 3-10 words, phrased as what the player wants
  kind:  "request" (asks for something) | "complaint" (says what is wrong) | "bug"
  quit:  true only if the review says this made them stop playing, refund or uninstall
  quote: the shortest sentence or clause from the review that shows this need, copied EXACTLY
Respond as JSON: {{"needs":[{{"i":<review index>,"theme":"...","need":"...","kind":"...","quit":false,"quote":"..."}}]}}"""

MERGE_SYSTEM = """These are player needs for the game {game} in the area "{theme}", each with how many players said it.
Group needs that ask for the SAME change (different wording, same fix). Keep different changes apart even if
related ("faster research" and "cheaper research" are the same; "faster research" and "better tutorial" are not).
Name each group in plain player language, 3-10 words. Every index must appear in exactly one group.
Respond as JSON: {{"groups":[{{"need":"...","members":[<index>, ...]}}]}}"""

CHUNK, MERGE_LIMIT = 50, 120


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip(" .,!?\"'")


def select(posts: list[Post]) -> list[Post]:
    return [p for p in posts if p.source.endswith(":negative") or REQUEST.search(p.text)]


def extract(posts: list[Post], cfg: dict, cache: Path) -> dict[str, list[dict]]:
    """post id -> verified needs. Saved after every chunk so an interrupted run picks up where it stopped."""
    done = json.loads(cache.read_text()) if cache.exists() else {}
    todo = [p for p in posts if p.id not in done]
    themes = cfg["needs"]["themes"]
    system = EXTRACT_SYSTEM.format(game=cfg.get("game", "this game"),
                                   themes=", ".join(f"{k} ({v})" for k, v in themes.items()))
    for s in range(0, len(todo), CHUNK):
        chunk = todo[s:s + CHUNK]
        for p, rows in zip(chunk, llm.per_item(system, [p.text for p in chunk], "needs", clip=3000, done=s, total=len(todo))):
            done[p.id] = [{"theme": str(r.get("theme", "")), "need": str(r.get("need", "")).strip(),
                           "kind": r.get("kind", "complaint"), "quit": r.get("quit") is True,
                           "quote": str(r.get("quote", "")), "verified": bool(r.get("quote")) and _norm(r["quote"]) in _norm(p.text)}
                          for r in rows[:3] if r.get("need")]
        cache.write_text(json.dumps(done))
    return done


def _groups(phrases: list[str], theme: str, game: str) -> list[tuple[str, list[int]]]:
    """(canonical need, member indices). Large themes are merged in chunks, then the chunk names are merged."""
    if len(phrases) <= 1:
        return [(phrases[0], [0])] if phrases else []
    if len(phrases) > MERGE_LIMIT:
        parts = [(n, [s + m for m in ms]) for s in range(0, len(phrases), MERGE_LIMIT)
                 for n, ms in _groups(phrases[s:s + MERGE_LIMIT], theme, game)]
        if len(parts) >= len(phrases):  # nothing merged; stop rather than loop
            return parts
        return [(n, [m for g in ms for m in parts[g][1]]) for n, ms in _groups([n for n, _ in parts], theme, game)]
    reply = llm.ask(MERGE_SYSTEM.format(game=game, theme=theme), json.dumps([{"i": i, "need": t} for i, t in enumerate(phrases)]))
    out, seen = [], set()
    for g in reply.get("groups", []):
        ms = [m for m in g.get("members", []) if isinstance(m, int) and 0 <= m < len(phrases) and m not in seen]
        seen.update(ms)
        if ms:
            out.append((str(g.get("need") or phrases[ms[0]]), ms))
    return out + [(phrases[i], [i]) for i in range(len(phrases)) if i not in seen]  # never lose a need


def rank(posts: list[Post], extracted: dict[str, list[dict]], cfg: dict) -> dict:
    by_id = {p.id: p for p in posts}
    rows = [{**r, "post": pid} for pid, rs in extracted.items() if pid in by_id for r in rs]
    good = [r for r in rows if r["verified"]]
    by_theme: dict[str, list[dict]] = defaultdict(list)
    for r in good:
        by_theme["new" if r["theme"].startswith("new:") or r["theme"] not in cfg["needs"]["themes"] else r["theme"]].append(r)

    needs = []
    for theme, rs in by_theme.items():
        phrases = sorted({r["need"].lower() for r in rs})
        canon = {phrases[m]: name for name, ms in _groups(phrases, theme, cfg.get("game", "")) for m in ms}
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in rs:
            groups[canon[r["need"].lower()]].append(r)
        for name, members in groups.items():
            players: dict[str, dict] = {}
            for r in members:  # one vote per player: keep their most-endorsed review
                p = by_id[r["post"]]
                if p.author not in players or p.likes > by_id[players[p.author]["post"]].likes:
                    players[p.author] = r
            votes = list(players.values())
            votes.sort(key=lambda r: -by_id[r["post"]].likes)
            needs.append({"need": name, "theme": theme, "players": len(votes),
                          "quit": sum(r["quit"] for r in votes),
                          "helpful": sum(by_id[r["post"]].likes for r in votes),
                          "negative": sum(by_id[r["post"]].source.endswith(":negative") for r in votes),
                          "kinds": {k: sum(r["kind"] == k for r in votes) for k in ("request", "complaint", "bug")},
                          "new_theme": sorted({r["theme"] for r in votes if r["theme"].startswith("new:")}),
                          "evidence": [{"post": r["post"], "quote": r["quote"], "helpful": by_id[r["post"]].likes} for r in votes]})
    needs.sort(key=lambda n: (-n["players"], -n["quit"], -n["helpful"]))
    return {"game": cfg.get("game", ""), "reviews_total": len(posts), "reviews_read": len(extracted),
            "reviews_with_needs": len({r["post"] for r in good}),
            "needs_found": len(rows), "quotes_not_in_review": len(rows) - len(good), "needs": needs}


def to_markdown(r: dict, top: int = 25) -> str:
    bad = r["quotes_not_in_review"] / max(r["needs_found"], 1)
    lines = [f"# What {r['game']} players need, ranked",
             f"Muse read {r['reviews_read']:,} of {r['reviews_total']:,} reviews (every negative review and every "
             f"review that asks for something) and found {r['needs_found']:,} specific needs. "
             f"{r['quotes_not_in_review']} ({bad:.1%}) cited a quote that isn't in the review and were dropped. "
             f"Each player counts once per need.", "",
             "| # | Need | Area | Players | Quit over it | Helpful votes | Example (player's words) |",
             "|---|---|---|---|---|---|---|"]
    for i, n in enumerate(r["needs"][:top], 1):
        quote = " ".join(n["evidence"][0]["quote"].split()).replace("|", "/")[:140]
        lines.append(f"| {i} | {n['need']} | {n['theme']} | {n['players']} | {n['quit']} | {n['helpful']} | \"{quote}\" |")
    areas: dict[str, int] = defaultdict(int)
    for n in r["needs"]:
        areas[n["theme"]] += n["players"]
    lines += ["", "## By area (player-needs, a player can raise several)", "",
              *[f"- **{a}**: {c}" for a, c in sorted(areas.items(), key=lambda x: -x[1])]]
    return "\n".join(lines) + "\n"
