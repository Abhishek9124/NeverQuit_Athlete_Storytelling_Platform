"""Shared request helpers: auth, story cards, absolute URLs, visibility, uploads."""
from __future__ import annotations
import os
import re
import logging
from functools import wraps

from flask import request, render_template

from scripts.utils import storage
from scripts.dashboard import config

log = logging.getLogger("neverquit.app")


# ---------- URLs ----------

def _site_url() -> str:
    """Absolute site origin, e.g. https://neverquit.in (no trailing slash).
    Prefers the SITE_URL env var; falls back to the current request's root."""
    base = (os.getenv("SITE_URL") or "").strip().rstrip("/")
    if base:
        return base
    try:
        return request.url_root.rstrip("/")
    except Exception:
        return ""


def _abs_url(path_or_url: str) -> str:
    """Turn a relative path (/media/x.jpg) into an absolute URL for OG/RSS tags.
    Leaves already-absolute http(s) URLs untouched."""
    u = (path_or_url or "").strip()
    if not u:
        return ""
    if u.startswith("http://") or u.startswith("https://"):
        return u
    return _site_url() + ("" if u.startswith("/") else "/") + u


def _excerpt(text: str, n: int = 160) -> str:
    """Collapse whitespace, strip tags, and truncate for meta descriptions."""
    t = re.sub(r"<[^>]+>", " ", str(text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[: n - 1].rstrip() + "…") if len(t) > n else t


# ---------- Auth ----------

def _is_admin() -> bool:
    if not config.ADMIN_TOKEN:
        return True  # dev mode: no token configured = open admin
    tok = (request.cookies.get("admin_token")
           or request.args.get("token")
           or request.headers.get("X-Admin-Token", ""))
    return tok == config.ADMIN_TOKEN


def admin_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not _is_admin():
            return render_template("admin_login.html", site=config.SITE_NAME), 401
        return view(*a, **kw)
    return wrapped


# ---------- Story cards ----------

def _card(s):
    if not isinstance(s, dict):
        s = {}
    dossier = s.get("dossier") if isinstance(s.get("dossier"), dict) else {}
    sections = s.get("sections") if isinstance(s.get("sections"), dict) else {}
    return {
        "id": s.get("story_id", ""),
        "athlete_name": s.get("athlete_name", "Untitled"),
        "sport": s.get("sport", ""),
        "country": s.get("country", ""),
        "hook": sections.get("hook", ""),
        "pull_quote": sections.get("pull_quote", ""),
        "confidence_score": s.get("confidence_score", 0),
        "status": s.get("status"),
        "image_url": s.get("image_url") or dossier.get("image_url", ""),
        "type": "para" if "para" in (s.get("sport", "") or "").lower() else "athlete",
    }


SEED_EXAMPLES = [
    {"id": "_seed_sheetal", "athlete_name": "Sheetal Devi", "sport": "Para Archery",
     "country": "India", "type": "para",
     "hook": "She has no arms. She holds the bow with her feet. At 17, she became the youngest Indian Paralympic gold medallist — a girl from Kishtwar who rewrote what an archer can be.",
     "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Sheetal_Devi_Indian_Paralympic_Archer.jpg/640px-Sheetal_Devi_Indian_Paralympic_Archer.jpg"},
    {"id": "_seed_mariyappan", "athlete_name": "Mariyappan Thangavelu", "sport": "Para High Jump",
     "country": "India", "type": "para",
     "hook": "His right leg was crushed by a drunk bus driver when he was five. Two decades later he stood on the Rio podium with Olympic gold around his neck — the first Indian to medal in three straight Paralympics.",
     "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Mariyappan_Thangavelu_-_3_-_Cropped.jpg/640px-Mariyappan_Thangavelu_-_3_-_Cropped.jpg"},
    {"id": "_seed_arunima", "athlete_name": "Arunima Sinha", "sport": "Mountaineering",
     "country": "India", "type": "athlete",
     "hook": "Pushed off a moving train by robbers. Lost her left leg below the knee. Two years later she stood on the summit of Everest — the first female amputee in history to do it.",
     "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Mrs_Arunima_Sinha_at_BNI_summit.jpg/640px-Mrs_Arunima_Sinha_at_BNI_summit.jpg"},
    {"id": "_seed_devendra", "athlete_name": "Devendra Jhajharia", "sport": "Para Javelin",
     "country": "India", "type": "para",
     "hook": "An eight-year-old climbed a tree to pluck a fruit and grabbed a live wire. He lost his left arm. He kept throwing. Two Paralympic golds, one silver, two world records — all with one arm.",
     "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Devendra_Jhajharia_2020_Paralympic_Games.jpg/640px-Devendra_Jhajharia_2020_Paralympic_Games.jpg"},
    {"id": "_seed_avani", "athlete_name": "Avani Lekhara", "sport": "Para Shooting",
     "country": "India", "type": "para",
     "hook": "A car crash at eleven left her paralysed from the waist down. She picked up a rifle to escape the depression. At Tokyo, she became the first Indian woman to win a Paralympic gold.",
     "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Avani_Lekhara_at_Paris_2024.jpg/640px-Avani_Lekhara_at_Paris_2024.jpg"},
    {"id": "_seed_murlikant", "athlete_name": "Murlikant Petkar", "sport": "Para Swimming",
     "country": "India", "type": "para",
     "hook": "Polio at one. Nine bullets in his body during the 1965 war. Doctors called it a miracle he survived. Eight years later he gave India its very first Paralympic gold — in a world record.",
     "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/Petkar_Murlikant_Rajaram_-_Indian_Paralympic_swimmer_-_2018_%28cropped%29.jpg/640px-Petkar_Murlikant_Rajaram_-_Indian_Paralympic_swimmer_-_2018_%28cropped%29.jpg"},
]


def _all_published_cards() -> list[dict]:
    """Return list of card dicts for every published story (or seed examples)."""
    cards = [_card(s) for s in storage.list_stories("published")]
    if cards:
        return cards
    return list(SEED_EXAMPLES)


# ---------- Section visibility ----------

def is_visible(s: dict, key: str) -> bool:
    """A section is visible unless the admin has explicitly hidden it."""
    hidden = (s or {}).get("hidden_sections") or []
    return key not in hidden


# ---------- Uploads ----------

def _save_uploaded_image(file_storage, slug: str) -> str | None:
    """Save an uploaded image to data/images/<slug>.jpg. Returns a /media/ URL."""
    if not file_storage or not file_storage.filename:
        return None
    ext = ("." + file_storage.filename.rsplit(".", 1)[-1].lower()) if "." in file_storage.filename else ""
    if ext not in config.ALLOWED_IMG_EXT:
        return None
    out = config.IMAGES / f"{slug}.jpg"
    file_storage.save(out)
    import time as _t
    return f"/media/{slug}.jpg?v={int(_t.time())}"  # bust browser cache
