"""Regenerates data/demo_posts.json — SYNTHETIC posts for offline demos and tests.

These are invented sentences written to look like typical launch-week feedback for an
open-world game. They are not real quotes and every row is flagged synthetic=True.
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(19)
NOW = datetime(2026, 11, 19, 23, 0, tzinfo=timezone.utc)
PLATFORMS = [("reddit", "r/GTA6"), ("reddit", "r/GTAVI"), ("discord", "discord:feedback"),
             ("instagram", "#gta6"), ("facebook", "fb:fanpage")]

TEMPLATES = {
    "police_wanted": (60, [
        "Cops literally spawn right behind me the second I lose them, 2 stars feels like 5",
        "Wanted level is so unfair, police spawned in front of me in an alley I was hiding in",
        "Please fix police spawning in line of sight, can't escape stars at all",
        "SWAT appear out of nowhere every time. Annoying",
        "helicopter finds me instantly even under a bridge. why can't I hide",
        "Love the game but the cops are ridiculous, they teleport next to you",
    ]),
    "mission_checkpoints": (45, [
        "Failed the mission at the very end and had to redo the whole drive. Add more checkpoints please",
        "Checkpoints are so far apart, I replayed the entire 10 min intro 4 times",
        "Restart mission should keep my ammo and the checkpoint, so frustrating",
        "Mission fail = replaying the whole cutscene + drive. Needs mid checkpoints",
    ]),
    "streaming_performance": (40, [
        "Massive frame drops driving fast on the highway, textures pop in late",
        "Performance mode still stutters when flying over the city",
        "Texture pop-in at high speed is really noticeable on base PS5",
        "fps drops near the beach at night, lag spikes when spinning the camera",
    ]),
    "vehicle_handling": (35, [
        "Driving feels floaty compared to IV, cars slide like they're on ice",
        "Bikes handle terrible, steering is way too sensitive",
        "Handling is too heavy for sports cars, wish there was a slider",
        "Traction on wet roads is ridiculous, every car drifts",
    ]),
    "weapon_wheel": (30, [
        "Weapon wheel is so slow to open in a firefight, please add favourite weapons",
        "Need a quick swap button for last weapon like RDR2 had",
        "Inventory limits are fine but the weapon swap animation takes forever",
    ]),
    "photo_mode": (25, [
        "Please add a photo mode, this map is too beautiful not to have one",
        "Photo mode with free cam would be amazing for Vice City sunsets",
    ]),
    "store_codes": (20, [
        "My physical copy came with no download code, just a grey strip I can't scratch",
        "Code was already redeemed on my disc-less physical edition, support closed my ticket",
    ]),
    "hud_minimap": (15, [
        "Let us hide the HUD completely and zoom the minimap",
        "GPS waypoint line is hard to see at night",
    ]),
    "_noise": (30, [
        "Jason and Lucia's chemistry is incredible",
        "Anyone else just driving around listening to the radio lol",
        "Vice City looks unreal at sunset",
        "What's the best car so far?",
    ]),
}

rows, n = [], 0
for theme, (count, texts) in TEMPLATES.items():
    for i in range(count):
        plat, src = random.choice(PLATFORMS)
        heavy = random.random() < 0.08  # a few viral posts
        rows.append({
            "platform": plat, "id": f"demo-{n}", "author": f"demo-user-{random.randint(1, 220)}",
            "text": random.choice(texts), "source": src, "url": "",
            "created_at": (NOW - timedelta(hours=random.uniform(0, 72))).isoformat(),
            "likes": int(random.paretovariate(1.4) * (400 if heavy else 12)),
            "replies": int(random.paretovariate(1.6) * (60 if heavy else 3)),
            "synthetic": True,
        })
        n += 1

Path(__file__).with_name("demo_posts.json").write_text(json.dumps(rows, indent=1))
print(f"wrote {len(rows)} synthetic posts")
