# Soft checkpoints, loadout snapshots & skip-after-fails

**Code:** `code/mission_checkpoints.h/.cpp` · **Type:** QoL · **Ships as:** code patch; interval/threshold are tunables

## Diagnosis
Complaints cluster around missions where a **long, low-challenge segment** (a drive, a cutscene, a walk-and-talk) sits before a **high-failure segment**. Each failure re-charges the player the boring part. That's a pacing problem, not a difficulty problem.

**To confirm:** the per-checkpoint `mission_fail` counter plus "time since checkpoint at failure". The walls show up as checkpoints with many fails *and* long replay time.

## Fix
- **Soft checkpoints:** when a stage runs longer than the tunable interval (150 s by default), insert a checkpoint at the next *safe* moment: not in combat, not airborne, on the nav mesh, not in a cutscene.
- **Snapshot, don't refill:** a checkpoint stores the loadout the player *had*, so retrying restores it exactly. No ammo farming, and no punishment.
- **Skip offer:** after N failures (3 by default) on the same checkpoint, offer to skip the travel portion.
- Soft checkpoints can be switched off per mission (`missions.soft_checkpoints`) for set-pieces where a checkpoint would break the scripting.

## Success metrics
- Median replay time per failure drops by >50% on the top-10 "wall" missions.
- Mission abandonment rate (quit to free-roam after failing) goes down.
- Guardrail: overall mission completion time doesn't fall so far that missions feel trivial.

## Risks
Some mission scripts assume a linear state. A snapshot taken mid-stage must restore script variables as well as player state. Before enabling soft checkpoints on a mission, audit it for missing "restore hooks" (whitelist approach).

## Test plan
Unit tests (combat blocks checkpoints; restore keeps exact ammo; skip offered on the 3rd fail). Automated fail-injection: kill the player at random times across every mission and assert they respawn at the latest safe checkpoint with a valid script state.
