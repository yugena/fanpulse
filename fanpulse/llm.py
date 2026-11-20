"""Meta Model API (Muse Spark) client. OpenAI-compatible chat completions, standard library only.

Base URL https://api.meta.ai/v1, bearer MODEL_API_KEY. Any other OpenAI-compatible endpoint works:
set FANPULSE_LLM_BASE_URL / FANPULSE_LLM_MODEL / FANPULSE_LLM_KEY. Everything else in FanPulse runs
without a key; the LLM (a) labels posts the keyword rules can't place, (b) reads which way each player
wants a theme to move, and (c) drafts proposals for brand-new themes.
"""
from __future__ import annotations

import json
import os
import sys

from .net import json_request

BASE_URL = os.environ.get("FANPULSE_LLM_BASE_URL", "https://api.meta.ai/v1")
MODEL = os.environ.get("FANPULSE_LLM_MODEL", "muse-spark-1.3")


def _key() -> str | None:
    return os.environ.get("FANPULSE_LLM_KEY") or os.environ.get("MODEL_API_KEY")


def available() -> bool:
    return bool(_key())


class EmptyReply(RuntimeError):
    """Reasoning models can spend the whole token budget thinking and return no text."""


def chat(system: str, user: str, *, json_mode: bool = False, max_tokens: int = 16000) -> str:
    body = {"model": MODEL, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    choice = json_request(f"{BASE_URL}/chat/completions", body, {"Authorization": f"Bearer {_key()}"})["choices"][0]
    content = choice.get("message", {}).get("content")
    if isinstance(content, list):  # some servers return content parts
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not content:
        raise EmptyReply(f"model returned no text (finish_reason={choice.get('finish_reason')})")
    return content


CLASSIFY_SYSTEM = """You label video-game player feedback. For each post return the best theme_id
from the provided list, or "new:<short_snake_case_name>" if it is a clear, actionable request that
fits none, or "none" for chatter/praise/questions. Also return kind: one of
bug|feature_request|qol|balance|performance|ops. Respond as JSON:
{"labels":[{"i":<index>,"theme":"...","kind":"...","title":"<short title if new>"}]}"""


def classify(texts: list[str], theme_ids: list[str]) -> list[dict]:
    payload = {"themes": theme_ids, "posts": [{"i": i, "text": t[:500]} for i, t in enumerate(texts)]}
    return json.loads(chat(CLASSIFY_SYSTEM, json.dumps(payload), json_mode=True)).get("labels", [])


DIRECTION_SYSTEM = """You read player reviews of a video game about one topic: {topic}.
For each review decide what the player ASKS FOR about that topic:
  -1 = wants less of it / easier / more forgiving (e.g. "enemies walk through everything", "not enough time to build")
   1 = wants more of it / harder / more challenge (e.g. "no challenge", "way too easy")
   0 = no request about this topic: describing the game, praise, or complaints about something else.
Most reviews that merely mention the topic are 0. A mixed complaint with no single direction is 0.
Respond as JSON: {{"labels":[{{"i":<index>,"d":-1|0|1}}]}}"""


def directions(texts: list[str], topic: str, batch: int = 10) -> list[int]:
    out = [0] * len(texts)
    for start in range(0, len(texts), batch):
        chunk = [{"i": i, "text": t[:1200]} for i, t in enumerate(texts[start:start + batch])]
        prompt = (DIRECTION_SYSTEM.format(topic=topic), json.dumps(chunk))
        try:
            reply = chat(*prompt, json_mode=True)
        except EmptyReply:  # one retry with a bigger thinking budget
            reply = chat(*prompt, json_mode=True, max_tokens=32000)
        print(f"\r  read {min(start + batch, len(texts))}/{len(texts)} reviews", end="", file=sys.stderr)
        for lab in json.loads(reply).get("labels", []):
            if isinstance(lab.get("i"), int) and 0 <= lab["i"] < len(chunk) and lab.get("d") in (-1, 0, 1):
                out[start + lab["i"]] = lab["d"]
    print(file=sys.stderr)
    return out
