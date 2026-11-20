# From player feedback to code: Enemy waves difficulty

**What players asked for:** 110 want less, 34 want more, 584 unclear → **LESS** (weighted agreement 97%).
**Target:** -23.7% on `threat_late` (size scaled by how strongly players agree).

**Search:** 80 candidate numbers tested by running the game's own code; 19 measurably moved `threat_late`.

## Proposed change

- `core/src/mindustry/game/Waves.java:301`: `30` → `45` in `float shieldStart = 30, shieldsPerWave = 20 + difficulty*30f;`

Measured by running the patched game code:

| Metric | Before | After | Change |
|---|---|---|---|
| units | 585.8 | 585.8 | +0.0% |
| threat_early | 64,197.1 | 64,197.1 | +0.0% |
| threat_mid | 186,159.6 | 178,221.1 | -4.3% |
| threat_late | 457,788.3 | 368,386.6 | -19.5% |
| threat | 708,145.0 | 610,804.8 | -13.7% |
| boss_spike | 1.9 | 2.0 | +6.1% |
| boss_warned | 0.0 | 0.0 | — |

```diff
--- a/core/src/mindustry/game/Waves.java
+++ b/core/src/mindustry/game/Waves.java
@@ -298,7 +298,7 @@
         //max reasonable wave, after which everything gets boring
         int cap = 150;
 
-        float shieldStart = 30, shieldsPerWave = 20 + difficulty*30f;
+        float shieldStart = 45, shieldsPerWave = 20 + difficulty*30f;
         float[] scaling = {1, 2f, 3f, 4f, 5f};
 
         Intc createProgression = start -> {
```

## All levers that measurably moved it (ranked by effect per % of change)

✗ = would push a guarded measure (units, threat_early, threat_mid, threat_late, threat) against what players asked for.

| Location | Code | Tested | threat_late | Other effects | Safe |
|---|---|---|---|---|---|
| `Waves.java:301` | `float shieldStart = 30, shieldsPerWave = 20 + difficulty*30f;` | `30` ×1.2667 | -12.7% | threat_mid -3.9%, threat -9.2%, boss_spike +3.9% | ✓ |
| `Waves.java:436` | `int shift = Math.max((int)(difficulty * 14 - 5), 0);` | `14` ×1.2857 | +11.9% | units +3.3%, threat_early +16.6%, threat_mid +7.5%, threat +11.2%, boss_spike -0.8% | ✓ |
| `Waves.java:311` | `int next = rand.random(8, 16) + (int)Mathf.lerp(5f, 0f, difficulty) + ` | `16` ×1.25 | -8.7% | units +9.2%, threat_early -1.9%, threat_mid +16.8%, threat -1.4%, boss_spike -12.3% | ✗ units, threat_mid |
| `Waves.java:342` | `if(curTier < 3 \|\| (rand.chance(0.05) && difficulty > 0.8)){` | `3` ×1.3333 | +9.3% | units +3.8%, threat_early +1.1%, threat_mid +5.9%, threat +7.7%, boss_spike -4.1% | ✓ |
| `Waves.java:301` | `float shieldStart = 30, shieldsPerWave = 20 + difficulty*30f;` | `20` ×1.25 | +5.8% | threat_early +6.2%, threat_mid +6.1%, threat +5.9%, boss_spike -2.2% | ✓ |
| `Waves.java:436` | `int shift = Math.max((int)(difficulty * 14 - 5), 0);` | `5` ×1.2 | -4.2% | units -1.4%, threat_early -6.6%, threat_mid -2.2%, threat -3.9%, boss_spike +1.7% | ✓ |
| `Waves.java:301` | `float shieldStart = 30, shieldsPerWave = 20 + difficulty*30f;` | `30f` ×1.25 | +5.0% | threat_early +5.5%, threat_mid +5.2%, threat +5.1%, boss_spike -2.0% | ✓ |
| `Waves.java:323` | `unitScaling = (difficulty < 0.4f ? rand.random(2.5f, 5f) : rand.random` | `4f` ×1.25 | -3.8% | units -4.6%, threat_early -7.2%, threat_mid -4.7%, threat -4.3%, boss_spike +1.1% | ✓ |
| `Waves.java:323` | `unitScaling = (difficulty < 0.4f ? rand.random(2.5f, 5f) : rand.random` | `1f` ×1.25 | -3.7% | units -2.5%, threat_early -2.4%, threat_mid -2.5%, threat -3.3%, boss_spike +1.3% | ✓ |
| `Waves.java:311` | `int next = rand.random(8, 16) + (int)Mathf.lerp(5f, 0f, difficulty) + ` | `4` ×1.25 | +3.5% | units +7.4%, threat_early -2.3%, threat_mid +8.2%, threat +4.2%, boss_spike -8.6% | ✗ threat_early |
