"""Picks the next video topic using Gemini's free tier, avoiding recent repeats."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROMPT_TEMPLATE = """You are a YouTube Shorts topic strategist for a channel about: {description}
Audience: {audience}
Tone: {tone}

Pick ONE specific, narrow topic for the next 45-60 second short. Favor topics
that are concrete and visual (a trick, a comparison, a "gotcha", a before/after),
not vague ("intro to X"). Avoid anything in this list of already-covered topics:

{recent_topics}

Pick from or stay close to these topic pools, but make it SPECIFIC (not the
pool name itself):
{topic_pools}

Respond with ONLY a JSON object, no markdown fences, no commentary:
{{
  "topic": "a specific, narrow topic in <= 12 words",
  "angle": "the specific hook/angle for this video in one sentence",
  "pool": "which topic pool this came from"
}}
"""


def _gemini_generate(prompt: str, api_key: str, model: str = "gemini-2.0-flash") -> str:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(model)
    response = gen_model.generate_content(prompt)
    return response.text


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def pick_topic(
    *,
    niche_config: dict[str, Any],
    recent_topics: list[str],
    api_key: str | None = None,
) -> dict[str, str]:
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    prompt = PROMPT_TEMPLATE.format(
        description=niche_config["description"],
        audience=niche_config["audience"],
        tone=niche_config["tone"],
        recent_topics="\n".join(f"- {t}" for t in recent_topics) or "(none yet)",
        topic_pools="\n".join(f"- {p}" for p in niche_config["topic_pools"]),
    )
    raw = _gemini_generate(prompt, api_key)
    data = json.loads(_strip_json_fences(raw))
    for field in ("topic", "angle", "pool"):
        if field not in data:
            raise ValueError(f"Gemini topic response missing `{field}`: {raw!r}")
    return data


def load_niche_config(niche: str, config_path: Path) -> dict[str, Any]:
    niches = json.loads(config_path.read_text(encoding="utf-8"))
    if niche not in niches:
        raise KeyError(f"Unknown niche `{niche}`. Known: {list(niches)}")
    return niches[niche]
