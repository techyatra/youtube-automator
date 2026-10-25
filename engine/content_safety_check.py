"""Automated (non-human) pre-publish policy check.

Since this pipeline publishes with zero human review, this is the one
safety net standing between a bad script and a live upload. It is
deliberately conservative: any flagged concern blocks the public upload
(the video is still uploaded as `private` so nothing is lost, just not
published) rather than trying to auto-fix and republish.
"""

from __future__ import annotations

import json
import os

PROMPT_TEMPLATE = """You are a conservative pre-publish safety reviewer for a YouTube Short.
Review this script for anything that could get the video flagged, demonetized,
or struck by YouTube, BEFORE it goes live with zero human review.

Title: {title}
Description: {description}
Full narration (all scenes, in order):
{narration}

Check specifically for:
1. Copyright: does it quote song lyrics, read out copyrighted text verbatim,
   or claim ownership of someone else's work?
2. Misinformation: medical, financial, or safety claims stated as fact that
   are false, unverifiable, or could cause real harm if wrong.
3. Impersonation or defamation of a real, named person or company.
4. Spam/clickbait patterns that misrepresent the content (title promises
   something the video doesn't deliver).
5. Anything else that plausibly violates YouTube's Community Guidelines.

Respond with ONLY a JSON object, no markdown fences, no commentary:
{{
  "safe": true or false,
  "concerns": ["short description of each concern found, empty list if none"],
  "reasoning": "one sentence explaining the verdict"
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


def check_script_safety(
    *, title: str, description: str, scenes: list[dict], api_key: str | None = None
) -> dict:
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    narration = "\n".join(f"- {s['narration']}" for s in scenes)
    prompt = PROMPT_TEMPLATE.format(title=title, description=description, narration=narration)
    raw = _gemini_generate(prompt, api_key)
    data = json.loads(_strip_json_fences(raw))
    for field in ("safe", "concerns", "reasoning"):
        if field not in data:
            raise ValueError(f"Gemini safety response missing `{field}`: {raw!r}")
    return data
