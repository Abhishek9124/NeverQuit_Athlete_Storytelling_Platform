"""Webflow CMS v2 publisher."""
from __future__ import annotations
import os
import requests

API = "https://api.webflow.com/v2"


def publish(story: dict) -> dict | None:
    key = os.getenv("WEBFLOW_API_KEY")
    cid = os.getenv("WEBFLOW_COLLECTION_ID")
    if not (key and cid):
        return None
    headers = {"Authorization": f"Bearer {key}", "accept": "application/json", "content-type": "application/json"}
    fields = {
        "name": story["athlete_name"],
        "slug": story["story_id"],
        "sport": story.get("sport", ""),
        "hook": story["sections"]["hook"],
        "body-en": story["sections"].get("full_html_en", ""),
        "confidence": story.get("confidence_score", 0),
    }
    for lang in ["hi", "ta", "kn", "mr", "bn", "te", "gu"]:
        fields[f"body-{lang}"] = story.get("translations", {}).get(lang, "")
    r = requests.post(
        f"{API}/collections/{cid}/items/live",
        headers=headers,
        json={"fieldData": fields},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
