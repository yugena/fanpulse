# Feature: Mini-boss warning before big boss waves

**Request:** Add a mini-boss a few waves before each big boss wave: a weaker guardian of the same unit line, so players can see what is coming and prepare their defenses.

**Player evidence:** 19 of 10,952 Steam reviews complain that bosses arrive without warning or as a sudden spike; one asks for exactly this.

> Maybe add a mini boss here and there, that preps you for the big boss. Make the mini boss a simpler version of the boss, so you know what to prepare for.
> The vawes are kinda basic, with a sudden HUGE boss after several easy waves.
> Having a boss enemy just fly around your chokepoint would have been fine if any prior enemy had done so or there was any warning of it.
> You need to gamble on how much defenses you need to build because you have no idea how strong the bosses are.

**Draft by:** reference draft, hand-written by Claude (4 rounds; acceptance bar unchanged). Each main and alt boss wave is heralded 4, 3 and 2 waves earlier by a guardian from the same unit line, one tier lower, repeating on the boss's schedule. Random calls keep their original order, so all other waves are unchanged.

## Verification: ❌ FAILED

- ✓ boss_warned = 1 (need ≥ 0.8)
- ✗ boss_spike -14.2% (need ≤ -15%)
- ✓ threat_early +0.0% (must stay within ±2%)
- ✓ threat +3.2% (must stay within ±10%)

| Metric | Before | After | Change |
|---|---|---|---|
| units | 585.800 | 590.400 | +0.8% |
| threat_early | 64,197.100 | 64,197.100 | +0.0% |
| threat_mid | 186,159.600 | 195,291.600 | +4.9% |
| threat_late | 457,788.300 | 471,274.500 | +2.9% |
| threat | 708,145.000 | 730,763.200 | +3.2% |
| boss_spike | 1.879 | 1.612 | -14.2% |
| boss_warned | 0.000 | 1.000 | new |

```diff
--- a/core/src/mindustry/game/Waves.java
+++ b/core/src/mindustry/game/Waves.java
@@ -367,8 +367,25 @@
 
         int bossTier = difficulty < 0.6 ? 3 : 4;
 
+        //mini-bosses: weaker guardians of a boss's unit line 4, 3 and 2 waves before it, so players can see it coming
+        Cons2<UnitType[], Integer> heralds = (line, start) -> {
+            for(int lead : new int[]{4, 3, 2}){
+                out.add(new SpawnGroup(line[bossTier - 1]){{
+                    unitAmount = 1;
+                    begin = start - lead;
+                    spacing = bossSpacing;
+                    end = never;
+                    max = 4;
+                    unitScaling = bossSpacing;
+                    shieldScaling = shieldsPerWave;
+                    effect = StatusEffects.boss;
+                }});
+            }
+        };
+
         //main boss progression
-        out.add(new SpawnGroup(Structs.random(rand, species)[bossTier]){{
+        UnitType[] bossLine = Structs.random(rand, species);
+        out.add(new SpawnGroup(bossLine[bossTier]){{
             unitAmount = 1;
             begin = bossWave;
             spacing = bossSpacing;
@@ -379,10 +396,14 @@
             effect = StatusEffects.boss;
         }});
 
-        //alt boss progression
-        out.add(new SpawnGroup(Structs.random(rand, species)[bossTier]){{
+        heralds.get(bossLine, bossWave);
+
+        //alt boss progression (line and start drawn in the original order, so the random sequence is unchanged)
+        UnitType[] altLine = Structs.random(rand, species);
+        int altBegin = bossWave + rand.random(3, 5) * bossSpacing;
+        out.add(new SpawnGroup(altLine[bossTier]){{
             unitAmount = 1;
-            begin = bossWave + rand.random(3, 5) * bossSpacing;
+            begin = altBegin;
             spacing = bossSpacing;
             end = never;
             max = 16;
@@ -390,6 +411,8 @@
             shieldScaling = shieldsPerWave;
             effect = StatusEffects.boss;
         }});
+
+        heralds.get(altLine, altBegin);
 
         int finalBossStart = 120 + rand.random(30);
```
