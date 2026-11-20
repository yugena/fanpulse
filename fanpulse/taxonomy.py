"""Game-agnostic language cues. Game-specific themes live in games/<game>/game.toml."""
from __future__ import annotations

import re

BUG_CUES = [r"\bbug(s|gy)?\b", r"glitch", r"crash", r"broken", r"stuck", r"soft ?lock", r"doesn'?t work"]
NEG = [r"annoying", r"hate", r"terrible", r"awful", r"unfair", r"broken", r"frustrat", r"ridiculous",
       r"trash", r"worst", r"ruin", r"cheap", r"rage", r"unplayable", r"so bad"]
POS = [r"love", r"amazing", r"great", r"perfect", r"awesome", r"incredible", r"beautiful", r"best"]

# Which way players want the theme's quantity to move. Checked in order; a post votes once.
# "more time between waves" means LESS pressure, so the specific phrases come first.
DECREASE = [r"(?<!not )(?<!n't )too (hard|difficult|many|much|fast|quick|strong|tanky|brutal|op)\b", r"overwhelm", r"impossible",
            r"unfair", r"can'?t keep up", r"\bnerf", r"tone (it )?down", r"\b(less|fewer)\b", r"more time",
            r"breather", r"spike", r"punishing", r"\bbrutal\b", r"steamroll", r"no time to"]
INCREASE = [r"(?<!not )(?<!n't )too (easy|few|slow|weak)\b", r"not enough", r"no challenge", r"\bharder\b",
            r"\bbuff", r"crank (it )?up", r"step it up", r"\bincrease", r"more (challeng|difficult|pressure)",
            r"\b(want|need|add|wish|give (us|me)|would love)\b[^.]{0,25}\bmore\b"]  # "more" only inside a request


def compile_themes(themes: dict) -> dict[str, list[re.Pattern]]:
    return {tid: [re.compile(p, re.I) for p in t["patterns"]] for tid, t in themes.items()}
