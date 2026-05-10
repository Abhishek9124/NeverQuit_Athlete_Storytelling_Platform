"""Step 3 — Story Writer Agent.

Uses NVIDIA's openai/gpt-oss-120b exclusively for the highest narrative quality.
Override only via NVIDIA_STORY_MODEL in .env.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from dotenv import load_dotenv

from scripts.utils import nvidia_client, db

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]
PROMPT = (ROOT / "prompts" / "story_writer_prompt.txt").read_text(encoding="utf-8")

# Stories ALWAYS use gpt-oss-120b unless explicitly overridden in .env.
STORY_MODEL = os.getenv("NVIDIA_STORY_MODEL", "openai/gpt-oss-120b")

SYSTEM = (
    "You are NeverQuit's senior story writer. Vivid, specific, restrained prose. "
    "Show, never tell. Use named coaches, exact dates, real quotes from the dossier — "
    "never invent facts. Match the 10-section template exactly."
)


def run(dossier: dict, slug: str | None = None) -> dict:
    """Generate the 10-section story.

    If `slug` is provided we re-fetch the latest dossier from SQLite first —
    that way any admin edits (photo, fact corrections) are picked up.
    """
    if slug:
        latest = db.get_dossier(slug)
        if isinstance(latest, dict) and latest:
            dossier = latest
    if not isinstance(dossier, dict) or not dossier:
        raise ValueError("Story writer received an empty / invalid dossier")

    safe = {
        "athlete_name": dossier.get("athlete_name", "Unknown"),
        "sport": dossier.get("sport", ""),
        "country": dossier.get("country", ""),
        "birth": dossier.get("birth", {}),
        "disability_or_injury": dossier.get("disability_or_injury", ""),
        "early_life": dossier.get("early_life", ""),
        "key_struggles": dossier.get("key_struggles", []),
        "turning_point": dossier.get("turning_point", {}),
        "training_habits": dossier.get("training_habits", []),
        "competitions": dossier.get("competitions", []),
        "exact_quotes": dossier.get("exact_quotes", []),
        "sources": dossier.get("sources", []),
        "uncertain_facts": dossier.get("uncertain_facts", []),
    }
    user = PROMPT.replace("{dossier_json}", json.dumps(safe, ensure_ascii=False))

    sections = nvidia_client.complete_json(
        SYSTEM, user, max_tokens=20000, model_name=STORY_MODEL
    )

    if isinstance(sections, list):
        sections = sections[0] if sections and isinstance(sections[0], dict) else {}
    if not isinstance(sections, dict):
        sections = {}

    # Guarantee every section the UI expects, regardless of model output.
    defaults = {
        "into_you": "",
        "hook": "",
        "world_came_from": "",
        "darkest_moment": "",
        "turning_point": "",
        "outcome": "",
        "the_grind": "",
        "pull_quote": "",
        "constraints": {"physical": "", "emotional": "", "identity": ""},
        "tiny_practices": [],
        "inner_reframe": "",
        "body_protocol": [],
        "two_minute_actions": [],
        "lessons": [],
        "ask_yourself": "",
        "why_this_works": "",
        "comeback_timeline": [],
        "goal_box_prompt": "",
        "whatsapp_share": "",
    }
    for k, v in defaults.items():
        sections.setdefault(k, v)
    return sections


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dossier", required=True, help="Path to dossier JSON")
    args = parser.parse_args()
    d = json.loads(Path(args.dossier).read_text(encoding="utf-8"))
    print(json.dumps(run(d), indent=2, ensure_ascii=False))
