"""File-based queue + story storage. Swap for Supabase in production via supabase_client."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
STORIES = DATA / "stories"
STORIES.mkdir(parents=True, exist_ok=True)
QUEUE = DATA / "athlete_queue.json"


def load_queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(q: dict) -> None:
    QUEUE.write_text(json.dumps(q, indent=2, ensure_ascii=False), encoding="utf-8")


def enqueue(athlete: dict) -> None:
    q = load_queue()
    if any(a["name"].lower() == athlete["name"].lower() for a in q["queue"] + q["processed"]):
        return
    q["queue"].append(athlete)
    save_queue(q)


def pop_next() -> dict | None:
    q = load_queue()
    if not q["queue"]:
        return None
    a = q["queue"].pop(0)
    save_queue(q)
    return a


def save_story(story_id: str, payload: dict) -> Path:
    payload.setdefault("saved_at", datetime.utcnow().isoformat())
    # Carry image_url from dossier into the story for the UI.
    if "image_url" not in payload and isinstance(payload.get("dossier"), dict):
        if payload["dossier"].get("image_url"):
            payload["image_url"] = payload["dossier"]["image_url"]
    p = STORIES / f"{story_id}.json"
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # Mirror to SQLite (best-effort).
    try:
        from scripts.utils import db
        db.upsert_story(payload)
    except Exception:
        pass
    return p


def load_story(story_id: str) -> dict:
    s = json.loads((STORIES / f"{story_id}.json").read_text(encoding="utf-8"))
    if isinstance(s, list):
        s = s[0] if (s and isinstance(s[0], dict)) else {}
    return s if isinstance(s, dict) else {}


def list_stories(status: str | None = None) -> list[dict]:
    out = []
    for p in sorted(STORIES.glob("*.json")):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(s, list):
            s = s[0] if (s and isinstance(s[0], dict)) else None
        if not isinstance(s, dict):
            continue
        if status is None or s.get("status") == status:
            out.append(s)
    return out


def update_story(story_id: str, **fields) -> dict:
    s = load_story(story_id)
    s.update(fields)
    save_story(story_id, s)
    return s
