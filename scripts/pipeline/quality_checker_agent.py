"""Step 5 — Quality Checker Agent."""
from __future__ import annotations
import json
from pathlib import Path
from dotenv import load_dotenv

from scripts.utils import nvidia_client as claude_client

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]
PROMPT = (ROOT / "prompts" / "quality_checker_prompt.txt").read_text(encoding="utf-8")

SYSTEM = "You are a strict editorial QA agent. Be skeptical, terse, and honest."


def run(story: dict, dossier: dict) -> dict:
    user = (
        PROMPT.replace("{story_json}", json.dumps(story or {}, ensure_ascii=False))
        .replace("{dossier_json}", json.dumps(dossier or {}, ensure_ascii=False))
    )
    qa = claude_client.complete_json(SYSTEM, user, max_tokens=20000)
    if isinstance(qa, list):
        qa = qa[0] if qa and isinstance(qa[0], dict) else {}
    if not isinstance(qa, dict):
        qa = {}
    qa.setdefault("scores", {})
    qa.setdefault("red_flags", [])
    qa.setdefault("uncertain_facts", [])
    qa.setdefault("verdict", "review")
    # If model omitted confidence, average the per-axis scores.
    if "confidence_score" not in qa:
        scores = [v for v in (qa.get("scores") or {}).values() if isinstance(v, (int, float))]
        qa["confidence_score"] = int(sum(scores) / len(scores)) if scores else 0
    qa["confidence_score"] = int(qa["confidence_score"] or 0)
    return qa


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--story", required=True)
    p.add_argument("--dossier", required=True)
    args = p.parse_args()
    s = json.loads(Path(args.story).read_text(encoding="utf-8"))
    d = json.loads(Path(args.dossier).read_text(encoding="utf-8"))
    print(json.dumps(run(s, d), indent=2, ensure_ascii=False))
