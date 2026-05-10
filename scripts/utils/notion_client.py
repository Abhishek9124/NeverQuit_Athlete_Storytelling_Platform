"""Thin Notion wrapper. No-op if NOTION_TOKEN unset."""
from __future__ import annotations
import os
from notion_client import Client


def client():
    token = os.getenv("NOTION_TOKEN")
    return Client(auth=token) if token else None


def push_story(story: dict) -> str | None:
    n = client()
    db = os.getenv("NOTION_DATABASE_ID")
    if not n or not db:
        return None
    page = n.pages.create(
        parent={"database_id": db},
        properties={
            "Name": {"title": [{"text": {"content": story["athlete_name"]}}]},
            "Sport": {"rich_text": [{"text": {"content": story.get("sport", "")}}]},
            "Status": {"select": {"name": story.get("status", "draft")}},
            "Confidence": {"number": story.get("confidence_score", 0)},
        },
    )
    return page["id"]
