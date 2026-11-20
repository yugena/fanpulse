"""python -m pytest -q   (or: python tests/test_pipeline.py)
FANPULSE_IT=1 also runs the end-to-end Mindustry trace (needs games/mindustry/setup.sh, ~1 min)."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fanpulse import config, tracer  # noqa: E402
from fanpulse.analyze import cluster_posts, direction, intent, match_theme  # noqa: E402
from fanpulse.codeindex import Site  # noqa: E402
from fanpulse.collectors import steam  # noqa: E402
from fanpulse.models import Cluster, Post  # noqa: E402
from fanpulse.taxonomy import compile_themes  # noqa: E402

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)
GTA = config.load()["themes"]


def P(text, author="a", likes=1, plat="reddit", hours=1):
    return Post(platform=plat, id=f"{author}{text[:5]}{plat}", author=author, text=text,
                created_at=NOW - timedelta(hours=hours), likes=likes)


def test_theme_matching():
    c = compile_themes(GTA)
    assert match_theme("cops spawned right behind me again", c) == "police_wanted"
    assert match_theme("had to redo the whole mission, add checkpoints", c) == "mission_checkpoints"
    assert match_theme("my physical copy had no download code", c) == "store_codes"
    assert match_theme("Vice City looks unreal", c) is None


def test_one_loud_user_cannot_win():
    spam = [P(f"cops are unfair #{i}", author="spammer", likes=5) for i in range(30)]
    crowd = [P("add more checkpoints please", author=f"u{i}", likes=5) for i in range(8)]
    assert cluster_posts(spam + crowd, GTA, use_llm=False, now=NOW)[0].theme_id == "mission_checkpoints"


def test_cross_platform_and_recency():
    a = [P("add photo mode", author=f"a{i}", plat=p) for i, p in enumerate(["reddit", "discord", "instagram"])]
    b = [P("hud is cluttered, let me hide the hud", author=f"b{i}") for i in range(3)]
    old = [P("weapon wheel is slow", author=f"c{i}", hours=24 * 10) for i in range(3)]
    ranked = [c.theme_id for c in cluster_posts(a + b + old, GTA, use_llm=False, now=NOW)]
    assert ranked.index("photo_mode") < ranked.index("hud_minimap") < ranked.index("weapon_wheel")


def test_direction_reads_plain_language():
    cases = {"I want more cops": 1, "too many cops, tone it down": -1, "need more time between waves": -1,
             "waves are too easy": 1, "enemy waves are brutal around wave 30": -1, "the boss looks cool": 0,
             "please make it harder": 1, "can't keep up with the enemies": -1}
    assert {t: direction(t) for t in cases} == cases


def test_intent_one_vote_per_player():
    posts = [P("too many enemies", author="loud") for _ in range(20)] + \
            [P("waves too easy", author=f"q{i}") for i in range(3)]
    it = intent(Cluster("w", "w", "balance", posts), now=NOW)
    assert it["direction"] == 1 and it["players_less"] == 1 and it["players_more"] == 3


def test_confidence_gate_blocks_weak_or_split_requests():
    cfg = {"themes": {"w": {"title": "w", "trace": {"metric": "m"}}}, "trace": {"repo": ".", "sources": [], "probe": []}}
    c = Cluster("w", "w", "balance", [])
    split = {"direction": 1, "agreement": 0.88, "headcount_agreement": 0.54, "players_less": 42, "players_more": 36}
    few = {"direction": -1, "agreement": 1.0, "headcount_agreement": 1.0, "players_less": 5, "players_more": 0}
    for it in (split, few):
        r = tracer.trace(c, it, cfg)
        assert not r.change and r.note.startswith("Not confident")


def test_edits_on_one_line_and_integer_steps(tmp_path):
    (tmp_path / "W.java").write_text("float a = 20 + d*30f;\n")
    s20 = Site("W.java", 1, 10, 12, "20", "", "", "")
    s30 = Site("W.java", 1, 17, 19, "30", "f", "", "")
    assert tracer.apply(tmp_path, [(s20, "14"), (s30, "45f")])["W.java"][1] == "float a = 14 + d*45f;\n"
    assert tracer.scaled(Site("W.java", 1, 0, 1, "1", "", "", ""), 1.25) == "2"     # ints always move
    assert tracer.scaled(s30, 0.5) == "15.0f" and tracer.scaled(s20, 1.25) == "25"


def test_focus_picks_the_window_players_name():
    tcfg = {"metric": "threat", "focus": {"pattern": r"wave (\d+)", "windows": [[20, "early"], [40, "mid"], [9999, "late"]]}}
    c = Cluster("w", "w", "balance", [P("too hard around wave 30"), P("too hard by wave 35"), P("too easy at wave 5")])
    assert tracer.focus_metric(c, {"direction": -1}, tcfg) == "mid"


def test_llm_directions_batches_and_ignores_bad_rows(monkeypatch):
    from fanpulse import llm
    replies = iter([{"labels": [{"i": 0, "d": -1}, {"i": 1, "d": 7}, {"i": 9, "d": 1}]}, {"labels": [{"i": 0, "d": 1}]}])
    monkeypatch.setattr(llm, "chat", lambda *a, **k: json.dumps(next(replies)))
    assert llm.directions(["a", "b", "c"], "waves", batch=2) == [-1, 0, 1]

    calls = []

    def flaky(*a, **k):  # empty reply first, then succeeds with a bigger budget
        calls.append(k.get("max_tokens"))
        if len(calls) == 1:
            raise llm.EmptyReply("finish_reason=length")
        return json.dumps({"labels": [{"i": 0, "d": 1}]})
    monkeypatch.setattr(llm, "chat", flaky)
    assert llm.directions(["a"], "waves") == [1] and calls == [16000, 32000]


def test_needs_drop_fake_quotes_merge_wording_and_count_players_once(monkeypatch, tmp_path):
    from fanpulse import llm, needs
    cfg = {"game": "G", "needs": {"themes": {"waves": "enemy waves", "ui": "controls"}}}
    posts = [P("Bosses come with no warning. Please add a heads-up.", author="a", likes=5),
             P("I wish boss waves were announced first", author="b"),
             P("Really, I wish boss waves were announced", author="b", hours=2),   # same player again
             P("Controls are fine. Great game.", author="c")]
    for p in posts:
        p.source = "steam:1:negative"

    def fake(system, user, **k):
        items = json.loads(user)
        if "Group needs" in system:  # merge: two wordings of one change
            return json.dumps({"groups": [{"need": "warn before boss waves", "members": list(range(len(items)))}]})
        rows = []
        for it in items:
            t = it["text"]
            if "warning" in t:
                rows.append({"i": it["i"], "theme": "waves", "need": "boss warning", "kind": "request", "quote": "Please add a heads-up"})
            elif "announced" in t:
                rows.append({"i": it["i"], "theme": "waves", "need": "announce boss waves", "kind": "request", "quote": "boss waves were announced"})
            else:  # invented quote: must be dropped, not counted
                rows.append({"i": it["i"], "theme": "ui", "need": "undo button", "kind": "request", "quote": "I need an undo button"})
        return json.dumps({"needs": rows})
    monkeypatch.setattr(llm, "chat", fake)

    cache = tmp_path / "x.json"
    ex = needs.extract(posts, cfg, cache)
    assert json.loads(cache.read_text()) == ex                              # checkpointed
    monkeypatch.setattr(llm, "chat", lambda *a, **k: 1 / 0)
    assert needs.extract(posts, cfg, cache) == ex                           # resumes without re-asking
    monkeypatch.setattr(llm, "chat", fake)
    r = needs.rank(posts, ex, cfg)
    assert r["quotes_not_in_review"] == 1 and len(r["needs"]) == 1
    top = r["needs"][0]
    assert top["need"] == "warn before boss waves" and top["players"] == 2 and top["helpful"] == 6
    assert "Please add a heads-up" in needs.to_markdown(r)


def test_iterate_routes_honestly_and_judge_needs_real_diff_lines(monkeypatch):
    from fanpulse import iterate, llm
    cfg = {"game": "G", "iterate": {"metrics": {"boss_warned": "x", "threat": "y"}, "tune": {"waves": "enemy_waves"}}}
    need = {"need": "n", "theme": "ui", "players": 3, "quit": 0, "helpful": 0,
            "evidence": [{"post": str(i), "quote": q} for i, q in enumerate(["a", "b", "c", "d"])]}
    reply = {}
    monkeypatch.setattr(llm, "chat", lambda *a, **k: json.dumps(reply))
    reply.update(track="tune", direction=-1, metrics=["threat"])
    assert iterate.route(need, cfg)["track"] == "feature"          # no tuner levers for this area
    reply.update(track="feature", metrics=["fun_score"])
    r = iterate.route(need, cfg)
    assert r["track"] == "design" and r["unmeasurable"]            # nothing real can measure it

    diff = "--- a/W.java\n+++ b/W.java\n-int x = 1;\n+heraldBefore(boss);\n"
    reply.clear()
    reply["players"] = [{"i": 0, "verdict": "yes", "line": "heraldBefore(boss);"},
                        {"i": 1, "verdict": "yes", "line": "spawnEverythingTwice();"},   # invented
                        {"i": 2, "verdict": "partly", "line": "heraldBefore(boss);"},
                        {"i": 3, "verdict": "different"}]
    j = iterate.judge(need, cfg, diff, {"threat": 1}, {"threat": 1})
    assert [p["verdict"] for p in j["players"]] == ["yes", "no", "partly", "different"]
    assert j["about_this_need"] == 3 and j["coverage"] == 0.5


def test_steam_collector_pages_until_empty():
    pages = [{"response": {"cursor": "AoJ1", "reviews": [
                {"recommendationid": "1", "review": "waves too hard", "timestamp_created": 1763500000,
                 "votes_up": 4, "comment_count": 1, "voted_up": False, "author": {"steamid": "765"}}]}},
             {"response": {"cursor": "AoJ2", "reviews": []}}]
    seen = []

    def fetch(url):
        seen.append(json.loads(parse_qs(urlparse(url).query)["input_json"][0]))
        return pages[len(seen) - 1]

    posts = steam.collect({"appid": 1127400}, fetch=fetch)
    assert [p.text for p in posts] == ["waves too hard"] and posts[0].likes == 4 and posts[0].author != "765"
    assert seen[0]["cursor"] == "*" and seen[1]["cursor"] == "AoJ1" and seen[0]["filter"] == 1


def test_feature_edits_must_match_exactly_once(tmp_path):
    from fanpulse import feature
    (tmp_path / "W.java").write_text("a = 1;\nb = 1;\n")
    assert feature.apply_edits(tmp_path, [{"file": "W.java", "find": "a = 1;", "replace": "a = 2;"}])["W.java"] == "a = 2;\nb = 1;\n"
    for bad in ("= 1;", "c = 1;"):  # ambiguous, missing
        try:
            feature.apply_edits(tmp_path, [{"file": "W.java", "find": bad, "replace": "x"}])
            raise AssertionError("should have refused")
        except feature.EditError:
            pass


def test_feature_checks():
    from fanpulse.feature import _check
    before, after = {"warned": 0.0, "spike": 2.0, "threat": 100.0}, {"warned": 0.9, "spike": 1.6, "threat": 103.0}
    assert _check({"metric": "warned", "at_least": 0.8}, before, after)[0]
    assert _check({"metric": "spike", "change_at_most": -0.15}, before, after)[0]          # -20%
    assert not _check({"metric": "spike", "change_at_most": -0.25}, before, after)[0]
    assert _check({"metric": "threat", "within": 0.05}, before, after)[0]
    assert not _check({"metric": "threat", "within": 0.02}, before, after)[0]


def test_art_conform_uses_only_game_colours_and_is_symmetric():
    from PIL import Image, ImageDraw
    from fanpulse import art
    g = {"metal_ramp": ["#4a4b53", "#6e7080", "#989aa4", "#b0bac0"], "ramp_share": [0.1, 0.3, 0.3, 0.3],
         "accent_families": [{"colors": ["#ffa665", "#d06b53"], "units": ["dagger"]}]}
    src = Image.new("RGB", (200, 200), "white")  # lopsided grey blob with an off-palette orange dot
    ImageDraw.Draw(src).ellipse((40, 30, 150, 170), fill=(120, 125, 140))
    ImageDraw.Draw(src).ellipse((90, 90, 120, 120), fill=(250, 140, 60))
    sprite, steps = art.conform(src, g, {"family": "dagger", "size": [64, 64]})
    allowed = {tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in g["metal_ramp"] + g["accent_families"][0]["colors"]}
    m = art.measure(sprite)
    assert sprite.size == (64, 64) and set(m["palette"]) <= allowed and m["symmetry"] == 1.0 and m["semi_alpha"] == 0
    assert any("background" in s for s in steps)


def test_end_to_end_mindustry_trace():
    if not os.environ.get("FANPULSE_IT"):
        return
    from fanpulse import pipeline
    cfg = config.load("games/mindustry/game.toml")
    r = pipeline.trace(pipeline.scan(cfg), cfg)
    assert r.intent["direction"] == -1 and r.change and abs(r.change["hit"] - r.target) <= tracer.TOLERANCE * abs(r.target)
    from fanpulse import feature
    spec = feature.load_spec("games/mindustry/features/boss_warning.toml")
    assert feature.locate(spec, cfg)[0] == "core/src/mindustry/game/Waves.java"
    res = feature.verify(spec, cfg, json.loads(Path("games/mindustry/features/boss_warning.reference_draft.json").read_text()))
    assert res["after"]["boss_warned"] == 1.0 and res["after"]["threat_early"] == res["before"]["threat_early"]
    from fanpulse import art
    from PIL import Image
    g = art.calibrate(art.guide(cfg))
    accepted, total = map(int, g["reviewer_accepts_game_sprites"].split("/"))
    assert accepted / total >= 0.8  # the reviewer must accept the game's own art
    spec = art.load_spec("games/mindustry/art/herald.toml")
    verdict = {v: all(c["passed"] for c in art.review(art.measure(art.conform(Image.open(f"games/mindustry/art/generated/{f}"), g, spec)[0]), g))
               for v, f in (("v1", "herald_canva_raw.png"), ("v2", "herald_canva_raw_v2.png"))}
    assert verdict == {"v1": False, "v2": True}  # first draft's tiny accent is caught; the revision passes


if __name__ == "__main__":
    import tempfile
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            if fn.__code__.co_argcount == 0:
                fn()
            elif "monkeypatch" not in fn.__code__.co_varnames:
                fn(Path(tempfile.mkdtemp()))
            print("ok", name)
