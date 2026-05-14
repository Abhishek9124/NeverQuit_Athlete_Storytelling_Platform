"""File-based queue + story storage. Swap for Supabase in production via supabase_client."""
from __future__ import annotations
import json
import threading
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
STORIES = DATA / "stories"
STORIES.mkdir(parents=True, exist_ok=True)
QUEUE = DATA / "athlete_queue.json"

# ─── In-memory cache for list_stories() ───
# `list_stories()` was re-reading every JSON file on every request, dominating
# home-page render time. We cache parsed payloads keyed by (path, mtime).
_cache: dict[Path, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


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
    _invalidate_cache(p)
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
    """Cached list of stories. Re-parses a JSON file only if its mtime changed."""
    out = []
    paths = sorted(STORIES.glob("*.json"))
    with _cache_lock:
        for p in paths:
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            cached = _cache.get(p)
            if cached and cached[0] == mtime:
                s = cached[1]
            else:
                try:
                    s = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if isinstance(s, list):
                    s = s[0] if (s and isinstance(s[0], dict)) else None
                if not isinstance(s, dict):
                    continue
                _cache[p] = (mtime, s)
            if status is None or s.get("status") == status:
                out.append(s)
        # Drop entries whose files no longer exist
        live = set(paths)
        for stale in [k for k in _cache.keys() if k not in live]:
            _cache.pop(stale, None)
    return out


def _invalidate_cache(p: Path) -> None:
    with _cache_lock:
        _cache.pop(p, None)


def update_story(story_id: str, **fields) -> dict:
    s = load_story(story_id)
    s.update(fields)
    save_story(story_id, s)
    return s
