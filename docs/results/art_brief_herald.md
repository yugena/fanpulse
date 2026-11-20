# Art brief: Herald: boss-warning scout

**What it is:** A new tier-2 ground mech in the dagger line that walks a few waves ahead of a boss. It carries a signal beacon so players learn to read it as 'a boss is coming'.
**Why:** 19 Steam reviews say bosses arrive without warning. The boss_warning feature spawns heralds before big bosses; a distinct sprite makes that warning readable at a glance.

## Must match the game's art (measured from 58 unit sprites)
- **View:** top-down, unit faces up, drawn as flat pixel art; no perspective, no gradients, no texture noise.
- **Palette:** metal ramp #4a4b53 #6e7080 #989aa4 #b0bac0 plus the dagger family accent #ffa665 #d06b53. 5–6 colours total.
- **Edges:** hard pixel edges, no anti-aliasing or soft shadows (game sprites have 0% semi-transparent pixels).
- **Symmetry:** perfectly mirror-symmetric left to right.
- **Lighting:** lighter plates toward the front (top) of the unit.
- **Outline:** none in the source art; the game draws a 3 px #565666 outline at load time.
- **Size:** 64×64 px, matching its tier (references: dagger 48×48, mace 64×64, fortress 100×80, nova 56×56, pulsar 68×58).
- **Shapes:** chunky flat facets about 4.14–11.12 px wide; no 1-pixel lines or fine engraving.
- **Accent:** a bold central core covering 6%–31% of the unit.
- **Silhouette:** compact armoured body with wide shoulder plates and a tall signal-beacon mast at the front, clearly different from the mace
- **Convention:** mech legs are separate sprites drawn underneath, so do not draw legs or feet on the body

## Family it belongs to
Same accent family as: flare, bryde, zenith, minke, mace, horizon, fortress, eclipse.
