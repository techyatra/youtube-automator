"""Turns a topic into a structured, scene-by-scene script for the renderer."""

from __future__ import annotations

import json
import os
from typing import Any

SCENE_TYPES = """
- "title_card": big title text. visual: {"title": str, "subtitle": str}
- "text_point": one short statement/kinetic text on screen. visual: {"text": str}
- "code_snippet": a short code block (<=6 lines). visual: {"code": str, "language": str}
- "comparison": two-column before/after or wrong/right. visual: {"left_label": str, "left_text": str, "right_label": str, "right_text": str}
- "stat_card": one big number/fact. visual: {"stat": str, "label": str}
- "outro_card": closing CTA. visual: {"title": str, "subtitle": str}
"""

PROMPT_TEMPLATE = """Write a {target_seconds}-second YouTube Short script.

Topic: {topic}
Angle: {angle}
Audience: {audience}
Tone: {tone}

Rules:
- The hook (first scene) must grab attention in under 3 seconds — a bold claim,
  a surprising fact, or a direct question. No throat-clearing intros.
- Write narration as natural spoken sentences, not bullet fragments.
- Build the middle as a short story/argument, not a list of unrelated facts.
- End with a concrete, single-sentence CTA (subscribe for more / follow for part 2 / etc.)
  worked into the outro_card naturally, not bolted on.
- 4 to 7 scenes total. Each scene's narration should take roughly 4-9 seconds
  to speak aloud (count ~2.5 words/second).
- Use these scene types only:
{scene_types}

Respond with ONLY a JSON object, no markdown fences, no commentary:
{{
  "title": "YouTube title, <=70 chars, curiosity-driven, no clickbait lies",
  "description": "2-3 sentence YouTube description",
  "tags": ["5 to 8 relevant tags"],
  "scenes": [
    {{"type": "title_card", "narration": "...", "visual": {{...fields for this type...}}}},
    ...
  ]
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


def write_script(
    *,
    topic: str,
    angle: str,
    niche_config: dict[str, Any],
    target_seconds: int = 45,
    api_key: str | None = None,
) -> dict[str, Any]:
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    prompt = PROMPT_TEMPLATE.format(
        topic=topic,
        angle=angle,
        audience=niche_config["audience"],
        tone=niche_config["tone"],
        target_seconds=target_seconds,
        scene_types=SCENE_TYPES,
    )
    raw = _gemini_generate(prompt, api_key)
    data = json.loads(_strip_json_fences(raw))
    for field in ("title", "description", "tags", "scenes"):
        if field not in data:
            raise ValueError(f"Gemini script response missing `{field}`: {raw!r}")
    if not data["scenes"]:
        raise ValueError("Gemini returned a script with zero scenes")
    return data
