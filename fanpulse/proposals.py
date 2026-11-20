"""Fix proposals: hand-written ones for known themes, LLM-drafted for new themes.

LLM drafts are labelled DRAFT and need a human engineer's review before anyone treats
them as a plan. The tool never edits game files: it outputs proposals and code for review.
"""
from __future__ import annotations

from pathlib import Path

from . import llm
from .models import Cluster

ROOT = Path(__file__).resolve().parents[1] / "proposals"

SENIOR_DEV_SYSTEM = """You are a senior gameplay/engine programmer at a AAA open-world studio writing
an internal fix proposal from aggregated player feedback. Be concrete and engineering-led:
1. Diagnosis: likely root causes, and the telemetry/repro that would CONFIRM each before changing code.
2. Fix: the smallest change that addresses the root cause; prefer server-side tunables and feature
   flags so it can be re-balanced without a certification round-trip.
3. Code: engine-agnostic C++17 (header + implementation sketch), with the telemetry it emits.
4. Rollout: flag, cohort A/B, guardrail metrics.
5. Risks/trade-offs, including players who LIKE the current behaviour.
6. Test plan.
Do not claim knowledge of any studio's proprietary code. Markdown, under 900 words."""


def proposal_for(cluster: Cluster, themes: dict, *, allow_llm: bool = True) -> dict:
    key = themes.get(cluster.theme_id, {}).get("proposal")
    if key:
        md = (ROOT / f"{key}.md").read_text()
        code = sorted(p.name for p in (ROOT / "code").glob(f"{key}.*"))
        return {"source": "authored", "markdown": md, "code_files": code}

    if allow_llm and llm.available():
        examples = "\n".join(f"- ({p.platform}, {p.likes} likes) {p.text[:240]}" for p in cluster.top_examples(8))
        user = (f"Game: an open-world crime action game at launch.\nTheme: {cluster.title} ({cluster.kind})\n"
                f"Mentions: {len(cluster.posts)} from {cluster.unique_authors} unique players on "
                f"{', '.join(cluster.platforms)}.\nRepresentative posts:\n{examples}")
        try:
            md = llm.chat(SENIOR_DEV_SYSTEM, user)
            return {"source": "llm_draft", "markdown": "> **DRAFT — generated, needs engineer review.**\n\n" + md,
                    "code_files": []}
        except Exception as exc:
            return {"source": "error", "markdown": f"_LLM draft failed: {exc}_", "code_files": []}

    return {"source": "none", "code_files": [],
            "markdown": "_No authored proposal yet. Set MODEL_API_KEY to have Muse draft one._"}
