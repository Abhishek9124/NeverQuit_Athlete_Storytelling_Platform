"""Centralised configuration & constants for the NeverQuit web app.

Importing this module guarantees the project root is on sys.path and that
`.env` is loaded, so every other dashboard module can rely on it.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Project root on path (so `scripts.*` imports resolve under any launcher) ──
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from scripts.utils import model_config  # noqa: E402

# ── Paths ──
DATA = ROOT / "data"
DOSSIERS = DATA / "dossiers"
IMAGES = DATA / "images"
SUBMISSIONS = DATA / "submissions"
SITE_DIR = ROOT / "site"
for _p in (DOSSIERS, IMAGES, SUBMISSIONS):
    _p.mkdir(parents=True, exist_ok=True)

# ── Identity ──
SITE_NAME = "NeverQuit"
SITE_TAGLINE = "True stories of athletes who refused to quit."
LANGS = [("en", "English")]

# ── Security ──
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
FLASK_SECRET = os.getenv("FLASK_SECRET", "change-me-in-production")

# ── Models — single source of truth in scripts/utils/model_config.py ──
RESEARCH_MODELS = model_config.RESEARCH_MODEL_CHOICES

# ── Uploads ──
ALLOWED_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}

# ── Section visibility ──
# Canonical list of toggleable section keys. Anything not in this list is
# always rendered (e.g. title, byline, country flag).
SECTION_KEYS = [
    "key_facts",          # the highlight tiles (dossier.outcomes)
    "into_you",           # universal pain-point opener
    "hook",               # 3-sentence vivid hook
    "world_came_from",    # origin / family
    "pull_quote",         # the screenshot line
    "darkest_moment",     # rock-bottom scene
    "turning_point",      # the named mentor / moment
    "the_grind",          # daily training reality
    "outcome",            # what happened after
    "comeback_timeline",  # year-by-year box
    "lessons",            # 3 takeaways
    "goal_box_prompt",    # reader CTA box
    "inner_reframe",      # lie-vs-truth block
    "why_this_works",     # research backing
    "tiny_practices",     # numbered practices list
    "body_protocol",      # universal recovery basics
    "two_minute_actions", # 3 reader actions
    "ask_yourself",       # one question to carry away
    "share",              # share buttons
    "newsletter_cta",     # inline newsletter capture
    "related",            # "more comebacks" carousel
]
