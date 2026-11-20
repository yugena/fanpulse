"""Game art -> measured style guide -> designer brief -> conform + review a generated image.

  guide    measure the game's own sprites: palette, colours per sprite, alpha, symmetry, lighting, size by
           tier, accent families; outline rules read from the code. Thresholds come from the art itself.
  brief    a graphic-designer brief for new content (spec: games/<game>/art/<id>.toml) + a generator prompt
  conform  turn any generated image into a game-ready sprite: cut out, crop, scale to the tier's size,
           snap to the game palette, hard alpha, mirror symmetry
  review   score the result with the same measurements as the game's sprites; show it beside real units
"""
from __future__ import annotations

import colorsys
import glob
import json
import re
import statistics as st
import tomllib
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .config import resolve

Color = tuple[int, int, int]


def _pixels(im: Image.Image) -> list:
    """Pixel values; Pillow 12 deprecates getdata() (removed in 14), older Pillow lacks the replacement."""
    return list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())


def _hex(c: Color) -> str:
    return "#%02x%02x%02x" % c


def _sat(c: Color) -> float:
    return colorsys.rgb_to_hsv(*(v / 255 for v in c))[1]


def _lum(c: Color) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def measure(im: Image.Image) -> dict:
    """The same measurements for game sprites and generated candidates."""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    opaque = [(x, y) for y in range(h) for x in range(w) if px[x, y][3] > 0]
    if not opaque:
        return {}
    cols = Counter(px[x, y][:3] for x, y in opaque)
    alpha = im.getchannel("A")
    mirrored = alpha.transpose(Image.FLIP_LEFT_RIGHT)
    sym = sum((a > 0) == (b > 0) for a, b in zip(alpha.tobytes(), mirrored.tobytes())) / (w * h)
    runs, run = [], 0  # horizontal runs of one colour: how chunky the pixel facets are
    for y in range(h):
        prev = None
        for x in range(w):
            c = px[x, y][:3] if px[x, y][3] > 0 else None
            if c is not None and c == prev:
                run += 1
            else:
                if prev is not None:
                    runs.append(run)
                run = 1
            prev = c
        if prev is not None:
            runs.append(run)
    accent_px = sum(n for c, n in cols.items() if _sat(c) > 0.2)
    metal = [(c, n) for c, n in cols.items() if _sat(c) <= 0.2]
    tone = sum(_lum(c) * n for c, n in metal) / max(1, sum(n for _, n in metal))
    top = [_lum(px[x, y][:3]) for x, y in opaque if y < h / 2]
    bottom = [_lum(px[x, y][:3]) for x, y in opaque if y >= h / 2]
    return {"size": [w, h], "colors": len(cols), "semi_alpha": sum(1 for x, y in opaque if px[x, y][3] < 255) / len(opaque),
            "symmetry": sym, "fill": len(opaque) / (w * h), "facet": st.mean(runs), "accent_share": accent_px / len(opaque), "tone": tone,
            "light_top_minus_bottom": (st.mean(top) - st.mean(bottom)) if top and bottom else 0.0,
            "accent": [_hex(c) for c, _ in cols.most_common() if _sat(c) > 0.2][:2],
            "palette": dict(cols.most_common())}


def guide(cfg: dict) -> dict:
    """Style guide measured from every unit body sprite (art.sprites glob in the game config)."""
    a, repo = cfg["art"], resolve(cfg["trace"]["repo"])
    files = [f for f in glob.glob(str(repo / a["sprites"])) if "-" not in Path(f).stem]
    ms = {Path(f).stem: m for f in files if (m := measure(Image.open(f)))}
    total = Counter()
    for m in ms.values():
        total.update(m["palette"])
    metal = [c for c, _ in total.most_common() if _sat(c) <= 0.2][:4]
    families = Counter(tuple(m["accent"]) for m in ms.values() if len(m["accent"]) == 2)
    lo_q, hi_q = a.get("range_quantiles", [0.025, 0.975])  # wide enough that the game's own sprites pass
    pct = lambda k, q: sorted(m[k] for m in ms.values())[round(q * (len(ms) - 1))]  # noqa: E731
    rng = lambda k, nd=3: [round(pct(k, lo_q), nd), round(pct(k, hi_q), nd)]  # noqa: E731
    src = "".join((repo / f).read_text() for f in a["outline_source"])
    outline = {"color": "#" + re.search(a["outline_color_regex"], src).group(1), "radius": int(re.search(a["outline_radius_regex"], src).group(1))}
    return {"sprites_measured": len(ms), "metal_ramp": sorted((_hex(c) for c in metal), key=lambda h: _lum(tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)))),
            "accent_families": [{"colors": list(k), "units": [u for u, m in ms.items() if tuple(m["accent"]) == k]} for k, _ in families.most_common(4)],
            "colors_per_sprite": rng("colors"), "semi_alpha_max": pct("semi_alpha", hi_q),
            "symmetry_min": pct("symmetry", lo_q), "fill": rng("fill"), "facet": rng("facet", 2),
            "accent_share": rng("accent_share"), "tone": rng("tone", 1), "light": rng("light_top_minus_bottom", 1),
            "ramp_share": [round(total[c] / sum(total[m] for m in metal), 3) for c in sorted(metal, key=_lum)],
            "light_top_minus_bottom": round(st.median(m["light_top_minus_bottom"] for m in ms.values()), 1),
            "_measured": ms,
            "outline": outline, "conventions": a.get("conventions", []), "sizes": {u: ms[u]["size"] for u in a.get("size_examples", []) if u in ms}}


def _span(r: list) -> str:
    return f"exactly {r[0]}" if r[0] == r[1] else f"{r[0]}–{r[1]}"


def load_spec(path: str) -> dict:
    return tomllib.loads(resolve(path).read_text())


def brief(g: dict, spec: dict) -> tuple[str, str]:
    """(markdown brief for a designer, compact prompt for an image generator)."""
    fam = next(f for f in g["accent_families"] if spec["family"] in f["units"])
    w, h = spec["size"]
    md = f"""# Art brief: {spec['title']}

**What it is:** {spec['description']}
**Why:** {spec['why']}

## Must match the game's art (measured from {g['sprites_measured']} unit sprites)
- **View:** top-down, unit faces up, drawn as flat pixel art; no perspective, no gradients, no texture noise.
- **Palette:** metal ramp {' '.join(g['metal_ramp'])} plus the {spec['family']} family accent {' '.join(fam['colors'])}. {_span(g['colors_per_sprite'])} colours total.
- **Edges:** hard pixel edges, no anti-aliasing or soft shadows (game sprites have {g['semi_alpha_max']:.0%} semi-transparent pixels).
- **Symmetry:** perfectly mirror-symmetric left to right.
- **Lighting:** lighter plates toward the front (top) of the unit.
- **Outline:** none in the source art; the game draws a {g['outline']['radius']} px {g['outline']['color']} outline at load time.
- **Size:** {w}×{h} px, matching its tier (references: {', '.join(f'{k} {v[0]}×{v[1]}' for k, v in g['sizes'].items())}).
- **Shapes:** chunky flat facets about {g['facet'][0]}–{g['facet'][1]} px wide; no 1-pixel lines or fine engraving.
- **Accent:** a bold central core covering {g['accent_share'][0]:.0%}–{g['accent_share'][1]:.0%} of the unit.
- **Silhouette:** {spec['silhouette']}
""" + "".join(f"- **Convention:** {n}\n" for n in g.get("conventions", [])) + f"""
## Family it belongs to
Same accent family as: {', '.join(fam['units'][:8])}.
"""
    prompt = (f"Top-down pixel art game sprite of {spec['prompt_subject']}, facing up, perfectly left-right symmetric, "
              f"flat colors only: grey metal plates {', '.join(g['metal_ramp'])} with {', '.join(fam['colors'])} glowing accent core, "
              f"large chunky flat facets with no thin lines or fine engraving, a big bold accent core covering about a fifth of the body, "
              f"hard pixel edges, no outline, no gradients, no text, centered on a plain white background, {spec['silhouette']}"
              + "".join(f", {n}" for n in g.get("conventions", [])))
    return md, prompt


def _nearest(c: Color, palette: list[Color]) -> Color:
    return min(palette, key=lambda p: sum((a - b) ** 2 for a, b in zip(c, p)))


def conform(src: Image.Image, g: dict, spec: dict) -> tuple[Image.Image, list[str]]:
    """Generated image -> game-ready sprite. Returns the sprite and what was changed."""
    steps, im = [], src.convert("RGBA")
    bg = im.getpixel((0, 0))[:3]
    if im.getchannel("A").getextrema()[0] == 255:  # opaque: key out the background colour from the corners
        im.putdata([(r, g_, b, 0) if abs(r - bg[0]) + abs(g_ - bg[1]) + abs(b - bg[2]) < 60 else (r, g_, b, a)
                    for r, g_, b, a in _pixels(im)])
        steps.append(f"removed flat background {_hex(bg)}")
    im = im.crop(im.getchannel("A").getbbox())
    w, h = spec["size"]
    k = min(w / im.width, h / im.height)
    small = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.BOX)
    steps.append(f"scaled {src.width}×{src.height} → {small.width}×{small.height} (tier size {w}×{h})")
    fam = next(f for f in g["accent_families"] if spec["family"] in f["units"])
    palette = [tuple(int(x[i:i + 2], 16) for i in (1, 3, 5)) for x in g["metal_ramp"] + fam["colors"]]
    ramp, accents = palette[:len(g["metal_ramp"])], palette[len(g["metal_ramp"]):]
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ox, oy = (w - small.width) // 2, (h - small.height) // 2
    pts = [(x, y, small.getpixel((x, y))[:3]) for y in range(small.height) for x in range(small.width) if small.getpixel((x, y))[3] >= 128]
    metal = sorted((p for p in pts if _sat(p[2]) <= 0.2), key=lambda p: _lum(p[2]))
    edges = [round(sum(g["ramp_share"][:i + 1]) * len(metal)) for i in range(len(ramp))]
    for i, (x, y, _) in enumerate(metal):  # darkest pixels -> darkest tone, in the game's own proportions
        out.putpixel((x + ox, y + oy), (*ramp[next(k for k, e in enumerate(edges) if i < e)], 255))
    for x, y, c in pts:
        if _sat(c) > 0.2:
            out.putpixel((x + ox, y + oy), (*_nearest(c, accents), 255))
    steps += [f"tone-mapped metal to the game's ramp proportions {g['ramp_share']}", "snapped accents to the family colours",
              "hard alpha (no semi-transparent pixels)"]
    out = _merge_thin_lines(out, spec.get("facet_passes", 3))
    steps.append("majority filter: thin lines merged into flat facets (background never bleeds in)")
    left = out.crop((0, 0, w // 2, h))
    out.paste(left.transpose(Image.FLIP_LEFT_RIGHT), (w - w // 2, 0))
    steps.append("mirrored left half → perfectly symmetric")
    return out, steps


def _merge_thin_lines(im: Image.Image, passes: int) -> Image.Image:
    """3x3 majority vote over whole colours (Pillow filters RGB per channel, which would invent colours).
    Transparent pixels get their own index so the background never wins a vote on the sprite."""
    alpha = im.getchannel("A")
    colors = sorted({c[:3] for c in _pixels(im) if c[3]})
    bg = len(colors)
    idx = Image.new("L", im.size)
    idx.putdata([colors.index(c[:3]) if c[3] else bg for c in _pixels(im)])
    for _ in range(passes):
        voted = idx.filter(ImageFilter.ModeFilter(3))
        idx.putdata([o if a == 0 or v == bg else v for v, o, a in zip(_pixels(voted), _pixels(idx), _pixels(alpha))])
    out = Image.new("RGBA", im.size)
    out.putdata([(*colors[i], 255) if a else (0, 0, 0, 0) for i, a in zip(_pixels(idx), _pixels(alpha))])
    return out


def review(m: dict, g: dict) -> list[dict]:
    """Pass/fail against the ranges the game's own sprites fall in."""
    lo, hi = g["colors_per_sprite"]
    checks = [("colours", lo - 1 <= m["colors"] <= hi + 1, f"{m['colors']} colours (game: {lo}–{hi})"),
              ("edges", m["semi_alpha"] <= g["semi_alpha_max"] + 0.01, f"{m['semi_alpha']:.0%} soft-edge pixels (game: {g['semi_alpha_max']:.0%})"),
              ("symmetry", m["symmetry"] >= g["symmetry_min"] - 0.02, f"symmetry {m['symmetry']:.0%} (game ≥ {g['symmetry_min']:.0%})"),
              ("fill", g["fill"][0] - 0.05 <= m["fill"] <= g["fill"][1] + 0.05, f"silhouette fills {m['fill']:.0%} of its box (game {g['fill'][0]:.0%}–{g['fill'][1]:.0%})"),
              ("lighting", g["light"][0] <= m["light_top_minus_bottom"] <= g["light"][1],
               f"front-vs-back brightness {m['light_top_minus_bottom']:+.0f} (game {g['light'][0]:+.0f} to {g['light'][1]:+.0f})"),
              ("tone", g["tone"][0] <= m["tone"] <= g["tone"][1], f"metal brightness {m['tone']:.0f} (game {g['tone'][0]:.0f}–{g['tone'][1]:.0f})"),
              ("facets", g["facet"][0] <= m["facet"] <= g["facet"][1], f"average flat facet {m['facet']:.1f} px wide (game {g['facet'][0]}–{g['facet'][1]})"),
              ("accent", g["accent_share"][0] <= m["accent_share"] <= g["accent_share"][1],
               f"accent covers {m['accent_share']:.0%} of the unit (game {g['accent_share'][0]:.0%}–{g['accent_share'][1]:.0%})")]
    return [{"check": n, "passed": ok, "detail": d} for n, ok, d in checks]


def lineup(cfg: dict, sprite: Image.Image, spec: dict, scale: int = 4) -> Image.Image:
    """The new sprite between real units of the same family, with the game's outline, on a dark floor."""
    g_repo = resolve(cfg["trace"]["repo"])
    names = spec.get("compare_with", [])
    ims = [Image.open(next(iter(glob.glob(str(g_repo / cfg["art"]["sprites"]).replace("*", n))))).convert("RGBA") for n in names]
    ims.insert(len(ims) // 2, sprite)
    col = tuple(int(cfg["_outline"][i:i + 2], 16) for i in (1, 3, 5)) if cfg.get("_outline") else (86, 86, 102)
    pad = 12
    W = sum(i.width + 2 * pad for i in ims) * scale
    H = (max(i.height for i in ims) + 2 * pad) * scale + 20
    sheet, x = Image.new("RGBA", (W, H), (38, 38, 46, 255)), 0
    d = ImageDraw.Draw(sheet)
    for im, label in zip(ims, names[:len(names) // 2] + ["NEW: " + spec["id"]] + names[len(names) // 2:]):
        outlined = Image.new("RGBA", (im.width + 6, im.height + 6), (0, 0, 0, 0))
        a = im.getchannel("A")
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx * dx + dy * dy <= 9:
                    outlined.paste(Image.new("RGBA", im.size, (*col, 255)), (3 + dx, 3 + dy), a)
        outlined.alpha_composite(im, (3, 3))
        big = outlined.resize((outlined.width * scale, outlined.height * scale), Image.NEAREST)
        sheet.alpha_composite(big, (x + (im.width + 2 * pad) * scale // 2 - big.width // 2, (H - 20 - big.height) // 2))
        d.text((x + 6, H - 16), label, fill=(230, 230, 230, 255))
        x += (im.width + 2 * pad) * scale
    return sheet


def calibrate(g: dict) -> dict:
    """The reviewer must accept the game's own art: share of real sprites that pass every check."""
    ms = g.pop("_measured")
    passed = [u for u, m in ms.items() if all(c["passed"] for c in review(m, g))]
    g["reviewer_accepts_game_sprites"] = f"{len(passed)}/{len(ms)}"
    return g


def save_guide(g: dict, path: Path) -> None:
    path.write_text(json.dumps(g, indent=1))


def run(cfg: dict, spec: dict, out: Path, image: str | None = None) -> str:
    """Write guide + brief + prompt; with a generated image, also conform, review and line it up. Returns report md."""
    g = calibrate(guide(cfg))
    save_guide(g, out / "art_style_guide.json")
    md, prompt = brief(g, spec)
    (out / f"art_brief_{spec['id']}.md").write_text(md)
    (out / f"art_prompt_{spec['id']}.txt").write_text(prompt)
    if not image:
        return md
    raw = Image.open(image)
    raw.save(out / f"{spec['id']}_raw.png")
    sprite, steps = conform(raw, g, spec)
    sprite.save(out / f"{spec['id']}.png")
    lineup({**cfg, "_outline": g["outline"]["color"]}, sprite, spec).save(out / f"{spec['id']}_lineup.png")
    before, after = review(measure(raw), g), review(measure(sprite), g)
    ok = all(c["passed"] for c in after)
    rows = [f"| {b['check']} | {'✓' if b['passed'] else '✗'} {b['detail']} | {'✓' if a['passed'] else '✗'} {a['detail']} |"
            for b, a in zip(before, after)]
    return "\n".join([f"# Art review: {spec['title']}", "", f"**Verdict:** {'✅ fits the measured style' if ok else '❌ does not fit yet'}"
                      f" (reviewer accepts {g['reviewer_accepts_game_sprites']} of the game's own unit sprites).", "",
                      f"![in game, beside real units]({spec['id']}_lineup.png)", "",
                      "| Check | As generated (incl. background) | Game-ready sprite |", "|---|---|---|", *rows, "",
                      "**Made game-ready by:** " + "; ".join(steps) + ".", "",
                      "**Still needs a human eye:** does the silhouette read clearly at game zoom, does it say its role "
                      "(\"a boss is coming\") at a glance, and any hand clean-up of stray pixels.", "", "---", "", md])
