"""End-to-end orchestrator. Runs: discovery → research → write → translate → QA → save for approval."""
from __future__ import annotations
import os
import re
import json
import time
import argparse
import logging
import traceback
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

log = logging.getLogger("neverquit.pipeline")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

from scripts.pipeline import (
    discovery_agent,
    research_agent,
    story_writer_agent,
    translation_agent,
    quality_checker_agent,
    social_asset_generator,
    publishing_agent,
)
from scripts.utils import storage

load_dotenv()


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return f"{s}-{datetime.utcnow():%Y%m%d}"


def _safe(label: str, fn, *args, default=None, **kw):
    """Run a step, log any failure with full traceback, return `default` on failure."""
    try:
        return fn(*args, **kw)
    except Exception as e:
        log.error("Step %r failed: %s", label, e)
        log.debug("Traceback:\n%s", traceback.format_exc())
        return default


def run_one(athlete: dict, dry_run: bool = False) -> str | None:
    name = athlete["name"]
    sport = athlete.get("sport", "")
    log.info("=== Processing: %s (%s) ===", name, sport)

    log.info("[1/5] Research...")
    dossier = _safe("research", research_agent.run, name, sport, default=None)
    if not dossier:
        log.error("Research failed for %s — skipping.", name)
        return None
    time.sleep(2)  # gentle pacing for free-tier rate limits

    log.info("[2/5] Story writing...")
    sections = _safe("write", story_writer_agent.run, dossier, default=None)
    if not sections:
        log.error("Story writing failed for %s — skipping.", name)
        return None
    time.sleep(2)

    log.info("[3/5] (translation step disabled — English only)")
    translations = {}

    log.info("[4/5] Quality check...")
    qa = _safe("qa", quality_checker_agent.run, sections, dossier, default={"confidence_score": 0, "verdict": "review", "red_flags": [], "uncertain_facts": []})
    confidence = qa.get("confidence_score", 0)
    log.info("  confidence=%s verdict=%s", confidence, qa.get("verdict"))
    time.sleep(2)

    log.info("[5/5] Generating social assets...")
    social = _safe("social", social_asset_generator.run, sections, default={}) or {}

    sid = slugify(name)
    auto_thr = int(os.getenv("AUTO_APPROVE_THRESHOLD", "90"))
    min_thr = int(os.getenv("MIN_CONFIDENCE_SCORE", "75"))
    status = "approved" if (qa.get("verdict") == "auto_approve" and confidence >= auto_thr) else (
        "rejected" if confidence < min_thr else "pending_review"
    )

    payload = {
        "story_id": sid,
        "athlete_name": name,
        "sport": sport,
        "country": athlete.get("country", ""),
        "status": status,
        "confidence_score": confidence,
        "qa": qa,
        "dossier": dossier,
        "sections": sections,
        "translations": translations,
        "social_assets": social,
    }
    storage.save_story(sid, payload)
    log.info("Saved → data/stories/%s.json (status=%s)", sid, status)

    if status == "approved" and not dry_run:
        log.info("Auto-publishing...")
        _safe("publish", publishing_agent.publish, sid)

    return sid


def run_daily(quota: int | None = None, dry_run: bool = False) -> list[str]:
    quota = quota or int(os.getenv("DAILY_STORY_QUOTA", "1"))
    q = storage.load_queue()
    if len(q["queue"]) < quota:
        discovery_agent.run(quota * 3)
    ids = []
    for _ in range(quota):
        a = storage.pop_next()
        if not a:
            log.info("Queue empty.")
            break
        try:
            sid = run_one(a, dry_run=dry_run)
            if sid:
                ids.append(sid)
            q = storage.load_queue()
            q.setdefault("processed", []).append(a)
            storage.save_queue(q)
        except Exception as e:
            log.error("FAILED on %s: %s", a.get("name"), e)
            log.debug("Traceback:\n%s", traceback.format_exc())
            q = storage.load_queue()
            q.setdefault("rejected", []).append({**a, "error": str(e)[:300]})
            storage.save_queue(q)
        time.sleep(3)  # spacing between athletes
    return ids


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--athlete", help="Run on a single athlete by name")
    p.add_argument("--sport", default="")
    p.add_argument("--quota", type=int, help="Daily story count")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.athlete:
        run_one({"name": args.athlete, "sport": args.sport}, dry_run=args.dry_run)
    else:
        run_daily(args.quota, args.dry_run)
