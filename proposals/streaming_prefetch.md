# Velocity-aware streaming priority (pop-in & frame drops at speed)

**Code:** `code/streaming_prefetch.h/.cpp` · **Type:** performance · **Ships as:** code patch

## Diagnosis
Pop-in that **scales with speed** almost always means streaming priority is distance-based. At 60 m/s, the building 300 m dead ahead matters more than the one 130 m behind you, but distance sorting picks the wrong one. The frame drops usually come from the fallback: a synchronous wait on an asset that was needed *now*.

**To confirm:** capture I/O traces on the "highway at night" and "helicopter over downtown" benchmarks, and log each pop-in event's (distance, angle to velocity, time from request to resident).

## Fix
- **Priority = time-until-needed** along the predicted path: closing speed toward the asset, with low urgency for anything behind or beside the player.
- **Hard per-frame I/O budget**, so streaming never causes a frame spike.
- **Degrade, don't stall:** if high LOD doesn't fit the budget, schedule low LOD now and re-request high LOD next frame.
- Telemetry: `degraded_to_low` (fine) vs `popin_risk` (asset needed now with no budget left = real visible pop-in).

## Success metrics
- `popin_risk` events per minute at >40 m/s drop by >70% on the benchmarks.
- 1% low frame time on the flight benchmark improves, with no regression on foot.
- Theme share in FanPulse falls on the next scan.

## Risks
- Prediction is wrong on sharp turns. Mitigation: a short lookahead (4 s) and a "turn speed" term for assets beside or behind the player.
- Memory pressure from prefetching assets that are never used. Track the evict-before-use rate.

## Test plan
Unit test (asset far ahead outranks a near asset behind; low-LOD fallback stays within budget), plus nightly automated benchmark runs on base console hardware with the metrics above as gates.
