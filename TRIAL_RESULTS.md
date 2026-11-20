# Mindustry trial: real Steam reviews → verified code change (Nov 19, 2026)

**Data:** 10,952 English Steam reviews of Mindustry (app 1127400) from players with 1+ hour of playtime, Sept 2019 to Nov 2026, via `IUserReviewsService/GetAppReviews`. 96% positive. Reviewer IDs are hashed before saving.

## Result
728 reviews talk about enemy waves. Muse Spark read which way each one asks the game to move:

- **110 players want waves easier, 34 want them harder, 584 make no request**: 76% of those asking want easier.
- "Easier" has outnumbered "harder" in every year since 2020 (for example, 2022 was 17 to 2), so this isn't a recency effect.
- The players who named a wave number mostly said 42–53, so the tool targeted **late waves**. Only 7 reviews named a number, so that's thin evidence.

**Proposed change**, one edit, verified by running Mindustry's real wave generator (v160.8):

```diff
-        float shieldStart = 30, shieldsPerWave = 20 + difficulty*30f;
+        float shieldStart = 45, shieldsPerWave = 20 + difficulty*30f;
```
Enemy shields start at wave 45 instead of 30.

| Waves | Change |
|---|---|
| Early (1–20) | 0% |
| Mid (21–40) | −4.3% |
| Late (41–60) | **−19.5%** (target −23.7%) |
| Unit count | 0% |
| Boss spike | +6.1% (reported, not guarded; see below) |

The diff applies cleanly to a fresh v160.8 checkout and reproduces these numbers.

## How reliable is the reading of direction?
I read and labelled 160 random wave-related reviews: 80 used to tune the keyword rules, 80 held out.

| Held-out 80 reviews | Keyword rules | Muse Spark |
|---|---|---|
| Real requests found | 0 of 10 | **10 of 10** |
| Flagged requests that were right | 0 of 5 | 10 of 15 |
| Overall agreement with my labels | 65/80 | 75/80 |

Across all 160, Muse **never reversed a direction**. Its mistakes were 9 reviews where it read a request that wasn't there and 3 it missed; never "easier" read as "harder". The keyword rules alone had read "players want *harder* waves" from noise. The confidence gate (30+ clear requests, 60%+ agreement both weighted and by headcount) blocked that. With Muse's readings, the gate passed.

## Honest limits
- **What the probe measures:** enemy pressure from `Waves.generate`, which builds the waves for procedurally generated sectors. Hand-made campaign maps define their own waves, and a full playthrough isn't simulated.
- **What players actually named:** when I read the "easier" reviews, they often blamed specific systems: campaign invasions of captured sectors, boss/guardian spikes, and too little time before early waves. Those live in other code and need their own probes before the tool can change them.
- **The labels:** the 160 hand labels are mine (Claude), not a game designer's; `data/real/enemy_waves_labels.json`.
- **Model choice:** Muse is a reasoning model; one run took about 35 minutes for 728 reviews.

## Files
- `data/real/mindustry_steam_reviews.json`: the reviews
- `data/real/muse_direction_labels.json`: Muse's readings
- `data/real/enemy_waves_labels.json`: hand labels
- `out/mindustry/trace_enemy_waves.{md,html,diff,json}`: the trace

Reproduce:
```bash
python -m fanpulse.cli trace --config games/mindustry/game.toml --posts data/real/mindustry_steam_reviews.json --labels data/real/muse_direction_labels.json
```

---

# Feature requests → drafted code → verified: "warn me before the boss"

Beyond "easier / harder", players ask for **new behaviour**. In the real reviews, **19 complain that bosses arrive with no warning** ("a sudden HUGE boss after several easy waves"), and one asks for exactly the fix: *"add a mini boss here and there, that preps you for the big boss … a simpler version of the boss."*

**The problem, measured in the unmodified game:** a big-boss wave carries **1.88×** the threat of the five waves before it, and **0%** of big bosses have any warning.

**How the pipeline works:**
1. A **feature spec** (`games/mindustry/features/boss_warning.toml`) records the request, the player evidence, and the definition of done as measurable checks.
2. The tool **locates the code**. From the title and the players' own words it ranks `Waves.java` first (the first version picked the unit files; fixed).
3. The **LLM drafts** exact find/replace edits.
4. The tool **compiles and runs** Mindustry's real wave generator and evaluates every check.
5. **Failures go back to the model** for a repair round.

**Acceptance checks (fixed before any draft):**
- at least 80% of big bosses warned
- boss spike down at least 15%
- early game within ±2%
- overall difficulty within ±10%

**Reference draft** (written by Claude as a senior-engineer baseline; Muse's draft is verified the same way):

| Round | Design | Warned | Boss spike | Overall threat | Result |
|---|---|---|---|---|---|
| 1 | 1 herald, 2 tiers below the boss, 3 waves before | 100% | −1.2% | +0.2% | ✗ |
| 2 | 1 herald, 1 tier below | 100% | −6.0% | +1.1% | ✗ |
| 3 | 2 heralds (4 and 2 waves before) | 100% | −10.5% | +2.1% | ✗ |
| 4 | 3 heralds (4, 3, 2 waves before) | 100% | **−14.2%** | +3.2% | ✗ (by 0.8 pts) |

Round 4, refactored into one shared helper (28 added lines, identical measurements), delivers the warning players asked for on every big boss and leaves the early game untouched. It falls just short of the 15% spike target.

**I did not lower the bar after seeing results.** The trade-off is a design call for a human: accept round 4, approve a stronger herald, or confirm that the warning, not the spike size, was the real goal.


---

# Tuning + feature together
Easier regular waves make bosses feel *relatively* spikier, because the boss stays the same while the waves before it weaken. That's why the code trace guards units and threat, reports the boss spike, and leaves it to the boss-warning feature. Measured together in the real game:

| | Late waves | Boss spike | Bosses warned | Early game |
|---|---|---|---|---|
| Tuning (shields from wave 45) | −19.5% | +6.1% | 0% | 0% |
| Feature (mini-boss heralds) | +2.9% | −14.2% | 100% | 0% |
| **Both** | **−16.6%** | **−10.3%** | **100%** | **0%** |

**Lesson found during the build:** the guardrail first checked side effects only at the small +25% test nudge. One lever looked safe there but raised the boss spike 9.6% at its full edit. Guardrails are now re-checked on every final measured change.

---

# New content needs art: style guide → brief → generator → review
**Style guide, measured, not written:** from 58 Mindustry unit sprites, plus the outline rules read from the code.
- Exactly 5 colours per sprite; four shared metal greys (`#4a4b53 #6e7080 #989aa4 #b0bac0`); one accent family per unit line, found automatically (orange attack, green support, purple spider-type, yellow core drones).
- Hard edges (0% soft pixels); perfect left–right symmetry; lighter toward the front.
- Chunky facets 4–11 px; accent covers 6–31% of the unit.
- No outline in source art; the game adds a 3 px `#565666` outline at load time.

**Reviewer calibrated on real art:** each range covers the 2.5th–97.5th percentile of real sprites, so the reviewer accepts **48/58 of Mindustry's own unit sprites** while still catching real flaws. A tighter range rejected half the game's own art; a looser one let a flawed draft through.

**The Herald** (new tier-2 scout that heralds boss waves; ties to the feature above). Brief → Canva (free) → conform → review:

| | As generated | Game-ready (after conform) |
|---|---|---|
| Draft 1 | thin 1-px detail, tiny core, legs drawn on | ❌ accent covers 5% (game 6–31%): a design flaw the conform step can't fix |
| Draft 2 (brief revised from the review) | bold core, no legs | ✅ all 8 checks |

**Conform** (makes generator output game-ready):
- Cut the background out and scale to the tier's size.
- Tone-map the greys to the game's ramp proportions and snap accents to the family colours.
- Hard alpha; a whole-colour majority vote merges thin lines into facets.
- Mirror-symmetrize.

**Still a human's call:** silhouette readability at game zoom, whether it reads as "a boss is coming", and a hand clean-up of stray edge pixels. A sprite this close is concept/prototype art ready for an artist's pass, not final art.
