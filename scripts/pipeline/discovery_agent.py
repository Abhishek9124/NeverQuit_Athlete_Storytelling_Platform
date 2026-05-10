"""Step 1 — Discovery Agent. Find new athletes daily (Gemini 2.5 Flash + Google Search)."""
from __future__ import annotations
import json
from pathlib import Path
from dotenv import load_dotenv

from scripts.utils import gemini_client, storage

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]

SYSTEM = """You are NeverQuit's Discovery Agent. Use Google Search grounding to find athletes,
Paralympians, or differently-abled individuals with documented comeback stories
that fit a 'never quit' narrative. Return ONLY a JSON list."""

USER_TMPL = """Find {n} new athletes (not in this exclusion list: {excluded}) whose stories are
well-documented in news, Wikipedia, or federation pages. Prefer Indian and Paralympic athletes.

Return JSON: [{{"name": str, "sport": str, "country": str, "why_now": str}}]"""


def run(n: int = 5) -> list[dict]:
    q = storage.load_queue()
    excluded = [a["name"] for a in q["queue"] + q["processed"]]
    raw = gemini_client.complete(
        SYSTEM,
        USER_TMPL.format(n=n, excluded=excluded[:50]),
        max_tokens=20000,
        web_search=True,
    )
    parsed = gemini_client.parse_json(raw)
    found = parsed if isinstance(parsed, list) else parsed.get("athletes", [])
    for a in found:
        storage.enqueue(a)
    print(f"Discovery: queued {len(found)} athletes")
    return found


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("-n", type=int, default=5)
    args = p.parse_args()
    run(args.n)
