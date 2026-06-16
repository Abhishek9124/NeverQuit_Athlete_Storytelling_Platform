"""Background job runner for admin-triggered pipeline work.

Jobs run on daemon threads and post granular progress steps that the admin
console polls via /admin/jobs.json. State lives in the module-level `JOBS`
dict guarded by `JOBS_LOCK`.
"""
from __future__ import annotations
import json as _json
import time as _t
import threading
import traceback
import logging

from scripts.utils import storage, db, model_config
from scripts.pipeline import research_agent, discovery_agent
from scripts.dashboard import config

log = logging.getLogger("neverquit.app")

JOBS_LOCK = threading.Lock()
JOBS: dict = {}  # job_id -> {label, status, steps:[{name,status,t}], started, finished, result}


# ---------- Job lifecycle ----------

def new_job(job_id: str, label: str) -> None:
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id, "label": label, "status": "running",
            "steps": [], "started": _t.time(), "finished": None, "result": "",
        }


def step(job_id: str, step_name: str, status: str = "running", note: str = "") -> None:
    """status: running | done | error"""
    with JOBS_LOCK:
        j = JOBS.get(job_id)
        if not j:
            return
        # Update existing running step of same name, else append new.
        for s in reversed(j["steps"]):
            if s["name"] == step_name and s["status"] == "running":
                s["status"] = status
                s["finished"] = _t.time()
                if note:
                    s["note"] = note
                return
        j["steps"].append({"name": step_name, "status": status, "started": _t.time(),
                           "finished": _t.time() if status != "running" else None,
                           "note": note})


def finish_job(job_id: str, status: str, result: str = "") -> None:
    with JOBS_LOCK:
        j = JOBS.get(job_id)
        if not j:
            return
        j["status"] = status
        j["finished"] = _t.time()
        j["result"] = result[:500]


def spawn(job_id: str, label: str, fn, *args, **kw):
    """Spawn a job. The target fn receives `job_id` as a kwarg so it can call step()."""
    new_job(job_id, label)

    def _runner():
        try:
            res = fn(*args, job_id=job_id, **kw)
            finish_job(job_id, "done", str(res))
        except Exception as e:
            step(job_id, "error", "error", str(e)[:200])
            finish_job(job_id, "error", str(e))
            traceback.print_exc()

    threading.Thread(target=_runner, daemon=True).start()


# ---------- Job targets ----------

def write_from_dossier(athlete: dict, dossier: dict, slug: str = "", job_id: str = ""):
    """Write the story, then QA + score in the background.

    Order:
      1. Story writer — primary, blocking
      2. Save to disk + DB as `pending_review` so it appears in the queue
      3. QA scoring (writes confidence + flags back to the same record)
    """
    import re as _re
    from datetime import datetime as _dt
    from scripts.pipeline import story_writer_agent, quality_checker_agent

    step(job_id, f"Writing story · {athlete['name']}", "running")
    try:
        sections = story_writer_agent.run(dossier, slug=slug or None)
        word_count = sum(len(str(v).split()) for v in sections.values() if isinstance(v, str))
        step(job_id, f"Writing story · {athlete['name']}", "done", note=f"{word_count} words")
    except Exception as e:
        step(job_id, f"Writing story · {athlete['name']}", "error", note=str(e)[:160])
        sections = {"hook": "(write failed)"}

    sid = _re.sub(r"[^a-zA-Z0-9]+", "-", athlete["name"].lower()).strip("-") + f"-{_dt.utcnow():%Y%m%d}"
    payload = {
        "story_id": sid,
        "athlete_name": athlete["name"],
        "sport": athlete.get("sport", ""),
        "country": athlete.get("country", ""),
        "status": "pending_review",
        "confidence_score": 0,
        "image_url": dossier.get("image_url", ""),
        "qa": {"verdict": "pending", "red_flags": [], "uncertain_facts": []},
        "dossier": dossier,
        "sections": sections,
        "translations": {},
        "social_assets": {},
        "story_model": model_config.model_for("story"),
        "research_model": (dossier.get("_research_model") or {}).get("name", ""),
    }
    storage.save_story(sid, payload)
    step(job_id, "Saved · ready for review", "done")

    step(job_id, "Quality check · scoring confidence", "running")
    try:
        qa = quality_checker_agent.run(sections, dossier)
        confidence = int(qa.get("confidence_score", 0) or 0)
        payload["qa"] = qa
        payload["confidence_score"] = confidence
        storage.save_story(sid, payload)
        step(job_id, "Quality check · scoring confidence", "done",
             note=f"confidence {confidence}% · {qa.get('verdict','review')}")
    except Exception as e:
        step(job_id, "Quality check · scoring confidence", "error", note=str(e)[:160])

    return sid


def research_job(name: str, sport: str, slug: str, model_key: str, model_name: str, job_id: str = ""):
    """Background research job — runs the research agent, fetches an image,
    counts sources/quotes, and saves to both disk and SQLite."""
    step(job_id, f"Researching {name} · gathering facts", "running")
    try:
        dossier = research_agent.run(name, sport, model_name=model_name)
    except Exception as e:
        step(job_id, f"Researching {name} · gathering facts", "error", note=str(e)[:200])
        raise
    sources = dossier.get("sources", []) or []
    quotes = dossier.get("exact_quotes", []) or []
    step(job_id, f"Researching {name} · gathering facts", "done",
         note=f"{len(sources)} sources · {len(quotes)} quotes")

    step(job_id, "Tagging model + verifying coverage", "running")
    dossier["_research_model"] = {
        "key": model_key,
        "name": model_name,
        "label": config.RESEARCH_MODELS[model_key]["label"],
    }
    required = ["birth", "disability_or_injury", "early_life", "key_struggles",
                "darkest_moment_scene", "turning_point", "training_habits",
                "daily_routine_details", "competitions", "exact_quotes", "outcomes",
                "ripple_effects", "principle_or_research"]
    missing = [k for k in required if not dossier.get(k)]
    dossier["_coverage_missing"] = missing
    cov_pct = int(100 * (len(required) - len(missing)) / len(required))
    note = f"{cov_pct}% coverage" + (f" · missing: {', '.join(missing[:3])}" if missing else " · all fields present")
    step(job_id, "Tagging model + verifying coverage", "done", note=note)

    step(job_id, "Saving dossier", "running")
    try:
        (config.DOSSIERS / f"{slug}.json").write_text(
            _json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8")
        db.upsert_dossier(slug, dossier)
        img_note = "with photo" if dossier.get("image_url") else "no photo found"
        step(job_id, "Saving dossier", "done", note=img_note)
    except Exception as e:
        step(job_id, "Saving dossier", "error", note=str(e)[:160])
        raise
    return slug


def discovery_job(n: int, job_id: str = ""):
    step(job_id, f"Searching for {n} new athletes", "running")
    found = discovery_agent.run(n)
    step(job_id, f"Searching for {n} new athletes", "done", note=f"{len(found)} queued")
    return f"queued {len(found)}"


def pipeline_one_job(athlete: dict, job_id: str = ""):
    """Full pipeline on one athlete with per-step progress."""
    name = athlete["name"]
    sport = athlete.get("sport", "")
    step(job_id, f"Researching {name}", "running")
    dossier = research_agent.run(name, sport)
    step(job_id, f"Researching {name}", "done", note=f"{len(dossier.get('sources', []))} sources")
    return write_from_dossier(athlete, dossier, job_id=job_id)


def pipeline_daily_job(quota: int, job_id: str = ""):
    step(job_id, "Loading queue", "running")
    q = storage.load_queue()
    if len(q["queue"]) < quota:
        step(job_id, "Queue empty — running discovery", "running")
        discovery_agent.run(quota * 3)
        step(job_id, "Queue empty — running discovery", "done")
    step(job_id, "Loading queue", "done")
    sids = []
    for i in range(quota):
        a = storage.pop_next()
        if not a:
            break
        try:
            sids.append(pipeline_one_job(a, job_id=job_id))
            q = storage.load_queue()
            q.setdefault("processed", []).append(a)
            storage.save_queue(q)
        except Exception as e:
            step(job_id, f"Failed: {a.get('name')}", "error", note=str(e)[:200])
    return f"processed {len(sids)}"
