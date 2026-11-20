"""Regenerates data/mindustry_demo_reviews.json: SYNTHETIC, everyday-language reviews for the offline trial.

Written to look like casual Steam/Reddit/Discord feedback, including messy cases the tool must get
right ("need more time between waves" = wants LESS pressure). Every row is flagged synthetic=True.
For the real test, collect live Steam reviews (games/mindustry/game.toml -> [steam] enabled = true).
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(7)
NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)

THEMES = {  # theme: (count, [phrasings])
    "waves_less": (120, [
        "Fun game but the waves get way too hard way too fast, I got overrun on sector 3",
        "enemy waves are brutal around wave 30, my defenses just melt",
        "I love building factories but I need more time between waves to actually build",
        "the shielded enemies are impossible to kill once you're past wave 25",
        "great game, just tone down the waves a little for new players",
        "Got wiped by a boss wave out of nowhere. Way too punishing",
        "the difficulty spike on the later waves made me quit. too many enemies",
        "waves come too fast and the enemies are too tanky",
        "can't keep up with the enemy waves on mobile, flying units destroy everything",
        "10/10 factory game, 3/10 wave balance. Steamrolled every single time",
    ]),
    "waves_more": (25, [
        "waves are too easy once you have a couple of turrets, no challenge at all",
        "please make the enemy waves harder, I'm bored by wave 50",
        "honestly the enemies are too weak, crank it up",
    ]),
    "waves_unclear": (30, [
        "the boss waves look so cool",
        "anyone know which turret is best against flying units?",
        "waves on erekir are a totally different vibe",
    ]),
    "campaign": (55, [
        "the campaign is confusing, I had no idea what to do after the first sector",
        "tech tree research is such a grind",
        "tutorial doesn't explain enough, got lost fast",
    ]),
    "performance": (45, [
        "huge lag once my factory gets big, fps tanks",
        "phone overheats and battery drains in like 20 minutes",
        "game freezes for a second every few minutes on late game saves",
    ]),
    "logistics": (40, [
        "placing conveyors on mobile with touch controls is so fiddly",
        "routers are confusing and belts go the wrong way when I drag",
    ]),
    "multiplayer": (20, [
        "multiplayer with friends is amazing but servers are hard to find",
        "please add easier co-op hosting",
    ]),
    "noise": (60, [
        "best $10 I've spent, the soundtrack is incredible",
        "Like Factorio but chill. Recommended",
        "Open source and still this polished? Amazing",
        "Hours vanish. Send help",
    ]),
}
PLATFORMS = ["steam"] * 7 + ["reddit", "reddit", "discord"]

rows, n = [], 0
for theme, (count, texts) in THEMES.items():
    for _ in range(count):
        rows.append({"platform": random.choice(PLATFORMS), "id": f"md-{n}", "author": f"player-{random.randint(1, 900)}",
                     "text": random.choice(texts), "source": theme, "url": "",
                     "created_at": (NOW - timedelta(days=random.uniform(0, 60))).isoformat(),
                     "likes": int(random.paretovariate(1.5) * 3), "replies": int(random.paretovariate(2.0)),
                     "synthetic": True})
        n += 1

Path(__file__).with_name("mindustry_demo_reviews.json").write_text(json.dumps(rows, indent=1))
print(f"wrote {len(rows)} synthetic reviews")
