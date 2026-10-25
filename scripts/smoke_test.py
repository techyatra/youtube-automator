"""Local smoke test for the render pipeline: no network calls (no Gemini, no edge-tts).

Generates silent placeholder audio with ffmpeg and a hand-written sample
script, then runs the real scene_renderer against it. Verifies Playwright +
ffmpeg actually produce a playable MP4 end to end.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.scene_renderer import render_video  # noqa: E402

SAMPLE_SCENES = [
    {
        "type": "title_card",
        "narration": "Your async code might be silently leaking threads.",
        "visual": {"title": "Your async code is leaking threads.", "subtitle": "Here's how to catch it."},
        "duration_seconds": 3.5,
        "words": [
            {"text": "Your", "start": 0.0, "end": 0.3},
            {"text": "async", "start": 0.3, "end": 0.7},
            {"text": "code", "start": 0.7, "end": 1.0},
            {"text": "is", "start": 1.0, "end": 1.2},
            {"text": "leaking", "start": 1.2, "end": 1.7},
            {"text": "threads.", "start": 1.7, "end": 2.3},
        ],
    },
    {
        "type": "code_snippet",
        "narration": "If you call dot result on a task without await, you block the pool.",
        "visual": {"code": "var data = GetDataAsync()\n          .Result; // blocks!", "language": "csharp"},
        "duration_seconds": 4.0,
        "words": [],
    },
    {
        "type": "comparison",
        "narration": "Swap dot Result for await, and the thread goes right back to the pool.",
        "visual": {
            "left_label": "WRONG",
            "left_text": ".Result blocks the calling thread",
            "right_label": "RIGHT",
            "right_text": "await frees it instantly",
        },
        "duration_seconds": 4.0,
        "words": [],
    },
    {
        "type": "outro_card",
        "narration": "Follow for more dot NET gotchas like this one.",
        "visual": {"title": "Follow for more", "subtitle": ".NET gotchas like this"},
        "duration_seconds": 2.5,
        "words": [],
    },
]


def make_silent_audio(out_mp3: Path, seconds: float) -> None:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
            "-t", str(seconds),
            "-q:a", "9",
            str(out_mp3),
        ],
        check=True, capture_output=True,
    )


def main() -> None:
    work_dir = Path("output/_smoke_work")
    for i, scene in enumerate(SAMPLE_SCENES):
        audio_path = work_dir / f"placeholder_{i:02d}.mp3"
        make_silent_audio(audio_path, scene["duration_seconds"])
        scene["audio_path"] = str(audio_path)

    out = render_video(
        scenes=SAMPLE_SCENES,
        work_dir=work_dir,
        out_mp4=Path("output/_smoke_test.mp4"),
    )
    print(f"OK: rendered {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
