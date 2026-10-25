"""Orchestrator: topic -> script -> voice -> render -> thumbnail -> safety check -> upload.

    python main.py                  # full run, picks topic automatically, publishes
    python main.py --dry-run        # does everything except the real YouTube upload
    python main.py --topic "..."    # skip topic picking, use this topic directly
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import content_safety_check, script_writer, thumbnail_generator  # noqa: E402
from engine import topic_generator, voice_generator  # noqa: E402
from engine.scene_renderer import render_video  # noqa: E402
from engine.youtube_uploader import upload_video  # noqa: E402

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
STATE_PATH = DATA_DIR / "state.json"


def load_json(path: Path, default: object) -> object:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def load_settings() -> dict:
    settings_path = CONFIG_DIR / "settings.json"
    if not settings_path.is_file():
        settings_path = CONFIG_DIR / "settings.example.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def run(*, dry_run: bool, manual_topic: str | None) -> dict:
    settings = load_settings()
    niches = topic_generator.load_niche_config
    niche_config = niches(settings["niche"], CONFIG_DIR / "niches.json")

    state = load_json(STATE_PATH, {"videos": []})
    recent_topics = [v["topic"] for v in state["videos"][-15:]]

    gemini_key = os.environ["GEMINI_API_KEY"]

    if manual_topic:
        topic_data = {"topic": manual_topic, "angle": manual_topic, "pool": "manual"}
    else:
        topic_data = topic_generator.pick_topic(
            niche_config=niche_config, recent_topics=recent_topics, api_key=gemini_key
        )
    print(f"[1/7] Topic: {topic_data['topic']}")

    script = script_writer.write_script(
        topic=topic_data["topic"],
        angle=topic_data["angle"],
        niche_config=niche_config,
        target_seconds=settings.get("video_length_seconds_target", 45),
        api_key=gemini_key,
    )
    print(f"[2/7] Script written: {len(script['scenes'])} scenes, title={script['title']!r}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    work_dir = OUTPUT_DIR / run_id
    voice = settings["voice"]["en"]
    voice_generator.generate_all_scene_audio(
        scenes=script["scenes"], voice=voice, work_dir=work_dir / "audio"
    )
    print("[3/7] Voice generated for all scenes")

    final_mp4 = render_video(
        scenes=script["scenes"],
        work_dir=work_dir / "render",
        out_mp4=work_dir / "final.mp4",
        fps=settings.get("fps", 30),
        resolution=(settings["resolution"]["width"], settings["resolution"]["height"]),
    )
    print(f"[4/7] Video rendered: {final_mp4}")

    thumb_paths = thumbnail_generator.generate_thumbnails(
        variant_texts=[script["title"]], out_dir=work_dir / "thumbnails"
    )
    thumbnail_path = thumb_paths[0] if thumb_paths else None
    print(f"[5/7] Thumbnail generated: {thumbnail_path}")

    safety = content_safety_check.check_script_safety(
        title=script["title"],
        description=script["description"],
        scenes=script["scenes"],
        api_key=gemini_key,
    )
    print(f"[6/7] Safety check: safe={safety['safe']} concerns={safety['concerns']}")

    privacy_status = settings.get("privacy_status_on_upload", "public")
    if not safety["safe"]:
        privacy_status = "private"
        print(f"    -> BLOCKING public upload (uploading private instead): {safety['reasoning']}")

    video_id = upload_video(
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        video_path=final_mp4,
        thumbnail_path=thumbnail_path,
        title=script["title"],
        description=script["description"],
        tags=script["tags"],
        category_id=settings.get("category_id", "28"),
        privacy_status=privacy_status,
        dry_run=dry_run,
    )
    print(f"[7/7] Upload: video_id={video_id} privacy={privacy_status} dry_run={dry_run}")

    record = {
        "run_id": run_id,
        "topic": topic_data["topic"],
        "title": script["title"],
        "video_id": video_id,
        "privacy_status": privacy_status,
        "safety": safety,
        "dry_run": dry_run,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    state["videos"].append(record)
    save_state(state)
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--topic", default=None)
    args = parser.parse_args()
    record = run(dry_run=args.dry_run, manual_topic=args.topic)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
