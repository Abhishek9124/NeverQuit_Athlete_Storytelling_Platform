"""Supabase client + pgvector helpers."""
from __future__ import annotations
import os
try:
    from supabase import create_client  # type: ignore
except Exception:
    create_client = None  # package not installed — module no-ops below


def client():
    if create_client is None:
        return None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not (url and key):
        return None
    return create_client(url, key)


def upsert_story(story: dict, embedding: list[float] | None = None) -> dict | None:
    sb = client()
    if not sb:
        return None
    row = {
        "id": story["story_id"],
        "athlete_name": story["athlete_name"],
        "sport": story.get("sport"),
        "hook": story["sections"]["hook"],
        "full_story_en": story["sections"],
        "confidence_score": story.get("confidence_score", 0),
        "languages": list(story.get("translations", {}).keys()) + ["en"],
    }
    if embedding:
        row["embedding"] = embedding
    return sb.table("stories").upsert(row).execute().data
