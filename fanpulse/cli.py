"""fanpulse scan   --config games/<game>.toml        collect -> rank -> report
   fanpulse label  --config ...                       ...then the LLM reads which way each player wants the top theme to move
   fanpulse trace  --config ... [--labels FILE]       ...then tune it into a verified code change
   fanpulse draft  --config ... --spec FEATURE.toml   the LLM drafts code for a feature request
   fanpulse verify --config ... --spec ... --draft F  apply the draft, run the game, check acceptance criteria
   fanpulse art    --config ... --spec ART.toml [--image GEN.png]   style guide + brief; then review a generated image"""
from __future__ import annotations

import argparse
import json
import logging
import urllib.error
from pathlib import Path

from . import art, config, feature, pipeline
from .report import build_html


def _model_call(fn):
    """Run an LLM step, turning API/reply failures into one readable line."""
    try:
        return fn()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Model API refused the request (HTTP {e.code}). "
                         + ("Check the API key." if e.code in (401, 403) else e.read().decode()[:300]))
    except (RuntimeError, ValueError, KeyError) as e:  # empty or malformed model replies
        raise SystemExit(f"Model reply problem: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="fanpulse")
    ap.add_argument("cmd", choices=["scan", "label", "trace", "draft", "verify", "art"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--theme", default=None, help="trace this theme id instead of the top traceable one")
    ap.add_argument("--posts", default=None, help="analyze saved real posts (JSON) instead of the configured sources")
    ap.add_argument("--labels", default=None, help="direction labels from `label` to use instead of keyword rules")
    ap.add_argument("--spec", default=None, help="feature spec (games/<game>/features/<id>.toml)")
    ap.add_argument("--draft", default=None, help="draft JSON to verify (from `draft`)")
    ap.add_argument("--previous", default=None, help="failed verification JSON to feed back into `draft`")
    ap.add_argument("--image", default=None, help="generated image to conform and review (`art`)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = config.load(args.config)
    out = pipeline.out_dir(cfg)

    if args.cmd == "art":
        spec = art.load_spec(args.spec)
        md = art.run(cfg, spec, out, args.image)
        name = f"art_review_{spec['id']}" if args.image else f"art_brief_{spec['id']}"
        (out / f"{name}.md").write_text(md)
        (out / f"{name}.html").write_text(build_html(md, f"FanPulse art: {spec['title']}", out))
        print(md.split("\n\n|")[0] if args.image else md)
        print(f"\nReport: {out / (name + '.html')}\nGenerator prompt: {out / ('art_prompt_' + spec['id'] + '.txt')}")
        return

    if args.cmd in ("draft", "verify"):
        spec = feature.load_spec(args.spec)
        if args.cmd == "draft":
            prev = json.loads(Path(args.previous).read_text()) if args.previous else None
            d = _model_call(lambda: feature.draft(spec, cfg, prev))
            path = out / f"feature_{spec['id']}_draft.json"
            path.write_text(json.dumps(d, indent=1))
            print(f"Draft ({len(d.get('edits', []))} edits): {path}")
            return
        proposal = json.loads(Path(args.draft).read_text())
        result = feature.verify(spec, cfg, proposal)
        md = feature.to_markdown(spec, proposal, result)
        for ext, body in (("md", md), ("html", build_html(md, f"FanPulse feature: {spec['title']}")),
                          ("json", json.dumps(result, indent=1)), ("diff", result.get("diff", ""))):
            (out / f"feature_{spec['id']}.{ext}").write_text(body)
        print(f"{'PASSED' if result['passed'] else 'FAILED'}: {result.get('error', '')}")
        for c in result.get("checks", []):
            print(f"  {'✓' if c['passed'] else '✗'} {c['detail']}")
        print(f"Report: {out / ('feature_' + spec['id'] + '.md')}")
        return

    if args.posts:
        cfg |= {k: {"enabled": False} for k in ("steam", "reddit", "discord", "meta")}
        cfg["file"] = {"enabled": True, "path": args.posts, "synthetic": False}
    clusters = pipeline.scan(cfg)
    md, html = pipeline.write_reports(clusters, cfg)
    for i, c in enumerate(clusters[:cfg.get("analysis", {}).get("top_n", 8)], 1):
        print(f"{i:>2}. [{c.kind:<15}] {c.score:7.1f}  {c.title}  ({len(c.posts)} posts)")
    print(f"\nReport: {md}\n        {html}")

    if args.cmd == "label":
        print(f"\nDirection labels: {_model_call(lambda: pipeline.label(clusters, cfg, args.theme))}")
    if args.cmd == "trace":
        labels = json.loads(Path(args.labels).read_text()) if args.labels else None
        r = pipeline.trace(clusters, cfg, args.theme, labels)
        print(f"\nTrace [{r.theme_id}]: intent {r.intent}, target {r.target:+.1%} on {r.metric}")
        print(f"  tested {r.searched} numbers in the real code, {r.measurable} moved {r.metric}")
        for e in r.change.get("edits", []):
            print(f"  edit {e['file']}:{e['line']}  {e['old']} -> {e['new']}")
        if r.change:
            print(f"  measured {r.change['hit']:+.1%} on {r.metric}")
        if r.note:
            print(f"  note: {r.note}")
        print(f"  details: {out / f'trace_{r.theme_id}.md'}")


if __name__ == "__main__":
    main()
