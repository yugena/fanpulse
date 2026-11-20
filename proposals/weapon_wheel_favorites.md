# Tap-to-swap, favourites & wheel slow-mo option

**Code:** `code/weapon_wheel_favorites.h/.cpp` · **Type:** QoL · **Ships as:** code patch

## Diagnosis
In a firefight, the cost of switching weapons is: open wheel → find weapon → close wheel. Most swaps are actually between the *same two* weapons. A one-tap path for that case removes most of the friction.

## Fix
- **Tap = swap to previous weapon; hold = open wheel.** The tap/hold threshold (0.18 s) is tunable.
- **Up to 4 favourites,** cycled with the d-pad without opening the wheel.
- **Accessibility option:** stronger slow-mo while the wheel is open, in single player only. It never affects multiplayer.

## Engineering note
The first draft had an aliasing bug: `Equip(previous_)` passed a reference to the member that `Equip` then overwrites, so the quick swap re-equipped the *same* weapon. The unit test caught it, and `Equip` now takes its argument by value. This is the kind of bug that slips through playtests because it only shows up on a specific input sequence.

## Success metrics
- Median time from "weapon change intent" to "weapon drawn" in combat goes down.
- Quick-swap adoption rate.
- Theme share in FanPulse goes down.

## Test plan
Unit tests for the tap/hold state machine, favourite limits and wrap-around cycling. Input-latency capture on all controllers. Accessibility review of the slow-mo option.
