# Handling Assist layer + slider (don't rewrite the physics)

**Code:** `code/vehicle_handling_tunables.h/.cpp` · **Type:** balance/accessibility · **Ships as:** code patch + settings option + tunables

## Diagnosis
Handling feedback is polarized: one group calls it floaty and slidey, another loves the weight. Changing the core simulation would trade one angry group for the other. Look for the specific causes behind each complaint:
- "Bikes too twitchy" → steering lock doesn't fall off with speed.
- "Like ice in the rain" → the wet grip loss is too large for the average player.
- "Slides out of nowhere" → there's no yaw damping before the player can react.

## Fix
An **assist layer** that sits between input and the existing sim:
1. **Speed-sensitive steering lock** (per vehicle class).
2. **Proportional yaw damping** when measured yaw exceeds what the steering asks for. It's enough to catch a slide, not enough to feel like being on rails.
3. **Wet grip floor.**

One **"Handling Assist" slider** blends from 0 (raw sim, the current game) to 1. The **default value is a server tunable**: if launch data says 0.5 is wrong, we move it without a patch. Players who have touched the slider keep their setting.

## Success metrics
- Crash rate per km and "driving" theme share both decline.
- Slider usage distribution: if 80% of players move it the same way, change the default.
- Guardrail: no change in race-mission completion times for players at slider 0.

## Risks
- Gives an advantage in competitive online modes: force the slider to 0 or a fixed value in ranked playlists.
- Physics determinism in multiplayer: the assist runs on the owning client before the input is sent, so replication is unchanged.

## Test plan
Unit tests (bike steering lock reduced only with assist; wet grip floor; default switches when the tunable is updated live). Plus a handling-rig playtest with blind A/B between slider values.
