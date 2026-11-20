# Police spawn fairness & a real "search" phase

**Code:** `code/police_spawn_fairness.h/.cpp` · **Type:** balance · **Ships as:** code patch + live tunables

## Diagnosis
"Cops spawned right behind me" and "I can't lose my stars" are usually two separate bugs that players experience as one.

1. **Spawn selection checks distance but not perception.** A node 90 m away can be inside the camera frustum, or dead ahead on the road the player is about to drive down. To the player, that unit appeared out of nowhere.
2. **Pursuers have perfect knowledge.** If units keep pathing to the player's live position after line of sight is broken, then hiding doesn't do anything and the evade loop feels rigged.

**To confirm before changing anything:** replay telemetry for (spawn position, camera transform, player velocity) at every dispatch spawn. Measure the % spawned inside the frustum while unoccluded, and the % spawned on the forward path within 6 s of reach time. I'd expect both to be high in dense downtown areas.

## Fix
- **Hard rejections:** inside the minimum bubble, visible and unoccluded, or a "teleport roadblock" on the forward path within the minimum reaction time.
- **Soft scoring:** prefer the ideal distance band, roads that lead *toward* the player (units arrive driving in), and flanks over dead-behind.
- **Never force a bad spawn.** If no candidate passes, retry next frame. A "starved" counter tells us when the rules are too strict for an area.
- **Search model:** once line of sight breaks, AI hunts a growing cone around the last-known position, extrapolated only briefly. Staying outside the search area for `base + perStar × stars` seconds clears the wanted level.

## Live-ops & rollout
Every threshold is a server tunable, so after the code patch ships, designers can re-balance per wanted level without another platform certification. Roll out behind a flag to a % of players, then compare cohorts.

## Success metrics
- In-frustum spawns: ~0%.
- Median time-to-escape at 2★/3★ is within the design target, and not near-zero (the game shouldn't become too easy).
- Share of fan posts in this theme drops week over week (FanPulse re-scan).
- Guardrail: the "starved" rate is below 2% of dispatch attempts.

## Risks
- Downtown may run short of legal nodes → dispatch is starved → the game feels too easy. Mitigate with per-zone min-distance tunables and the starved metric.
- Players may "learn" the search cone and exploit it. Growth rate and helicopter search are tunable per star.

## Test plan
Unit tests in `tests.cpp`, plus an automated bot run: drive a fixed route at 1–5★ ×100 seeds and assert zero unoccluded in-frustum spawns. Then a playtest focused on how it feels at 4–5★.
