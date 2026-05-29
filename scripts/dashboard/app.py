"""NeverQuit unified web app — public reader + admin console.

Public:
  GET  /                       Home (published stories, sport filters, search)
  GET  /story/<id>             Read a published story (with language tabs)

Admin (token-gated via ADMIN_TOKEN env var, sent as ?token=... or X-Admin-Token):
  GET  /admin                  Approval queue + recently published / rejected
  GET  /admin/story/<id>       Review a pending story with approve/reject buttons
  POST /admin/story/<id>/approve
  POST /admin/story/<id>/reject
  POST /admin/run-discovery    Queue more athletes
  POST /admin/run-pipeline     Process next N from queue (or a named athlete)
  POST /admin/run-pipeline/<id> Re-run pipeline on an existing story
"""
from __future__ import annotations
import os
import re
import sys
import threading
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify, make_response, flash
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.utils import storage, db, nvidia_client, country_flags, mailer  # noqa: E402
import logging as _logging
log = _logging.getLogger("neverquit.app")
from scripts.pipeline import publishing_agent, discovery_agent, run_pipeline, research_agent  # noqa: E402
from scripts.dashboard.seed_stories import SEED_STORIES  # noqa: E402

import json as _json
DOSSIERS = ROOT / "data" / "dossiers"
DOSSIERS.mkdir(parents=True, exist_ok=True)
IMAGES = ROOT / "data" / "images"
IMAGES.mkdir(parents=True, exist_ok=True)

load_dotenv()
app = Flask(__name__, static_folder=str(ROOT / "site"), static_url_path="/static")
app.secret_key = os.getenv("FLASK_SECRET", "change-me-in-production")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Available research models (can be extended)
RESEARCH_MODELS = {
    "gpt_oss": {
        "label": "GPT-OSS 120B  ✦ same as story writer",
        "model": "openai/gpt-oss-120b",
        "default": True,
        "description": "Slow but extremely thorough — same model that writes stories. ~60-90s.",
    },
    "nemotron": {
        "label": "NVIDIA Nemotron (Reasoning)",
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "default": False,
        "description": "Advanced reasoning with focused thinking (~20-30s)",
    },
    "deepseek": {
        "label": "DeepSeek v4 Pro",
        "model": "deepseek-ai/deepseek-v4-pro",
        "default": False,
        "description": "Fast, high-quality research (~15-25s)",
    },
    "glm": {
        "label": "GLM 5.1 (Thinking)",
        "model": "z-ai/glm-5.1",
        "default": False,
        "description": "Advanced thinking model (~15-25s)",
    },
}


@app.context_processor
def _inject_globals():
    # Get default research model
    default_model = next((k for k, v in RESEARCH_MODELS.items() if v.get("default")), "nemotron")
    story_model = os.getenv("NVIDIA_STORY_MODEL", "openai/gpt-oss-120b")
    return {
        "model_name": story_model,            # legacy: shown as the active model
        "story_model": story_model,           # new: explicit story-only label
        "research_model": RESEARCH_MODELS[default_model]["model"],
        "research_models": RESEARCH_MODELS,
        "is_nvidia_research": True,
        "flag": country_flags.flag_emoji,
        "country_iso": country_flags.iso_code,
        "max_tokens": 20000,
    }
SITE_NAME = "NeverQuit"
SITE_TAGLINE = "True stories of athletes who refused to quit."
LANGS = [("en", "English")]


# ---------- Helpers ----------

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
    import re as _re
    t = _re.sub(r"<[^>]+>", " ", str(text or ""))
    t = _re.sub(r"\s+", " ", t).strip()
    return (t[: n - 1].rstrip() + "…") if len(t) > n else t

def _is_admin() -> bool:
    if not ADMIN_TOKEN:
        return True  # dev mode: no token configured = open admin
    tok = request.cookies.get("admin_token") or request.args.get("token") or request.headers.get("X-Admin-Token", "")
    return tok == ADMIN_TOKEN


def admin_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not _is_admin():
            return render_template("admin_login.html", site=SITE_NAME), 401
        return view(*a, **kw)
    return wrapped


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


# ---------- Public ----------

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


@app.route("/")
def home():
    cards = _all_published_cards()
    showing_examples = not storage.list_stories("published")

    # Group by sport for the dynamic carousel rails.
    by_sport: dict = {}
    for c in cards:
        by_sport.setdefault(c.get("sport") or "Other", []).append(c)

    # Counts by athlete-type for the live stats row.
    counts = {
        "total": len(cards),
        "athletes": sum(1 for c in cards if c.get("type") == "athlete"),
        "para": sum(1 for c in cards if c.get("type") == "para"),
        "sports": len(by_sport),
        "countries": len({c.get("country") for c in cards if c.get("country")}),
    }

    return render_template(
        "public_home.html",
        cards=cards,
        sports=sorted(by_sport.keys()),
        by_sport=by_sport,
        counts=counts,
        langs=LANGS,
        site=SITE_NAME,
        is_admin=_is_admin(),
        showing_examples=showing_examples,
    )


# ---------- Visit logging (every page hit) ----------

import hashlib as _hashlib

@app.before_request
def _log_request_visit():
    p = request.path or ""
    # Only log content pages, skip media/static/admin/api
    if (p.startswith("/media") or p.startswith("/static") or
        p.startswith("/admin") or p.startswith("/api") or
        p in ("/healthz", "/favicon.ico", "/feed.xml", "/rss",
              "/sitemap.xml", "/robots.txt")):
        return
    try:
        ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
              or request.remote_addr or "")
        ip_hash = _hashlib.sha256(ip.encode()).hexdigest()[:24] if ip else ""
        story_id = ""
        if p.startswith("/story/"):
            story_id = p.split("/story/", 1)[1].split("/")[0]
        db.log_visit(p, story_id or None, ip_hash, request.headers.get("User-Agent", ""))
    except Exception:
        pass


# ---------- Newsletter ----------

@app.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    email = (request.form.get("email") or request.json and request.json.get("email") or "").strip().lower()
    source = (request.form.get("source") or "home_pill").strip()
    if not email or "@" not in email or len(email) > 200:
        return jsonify({"ok": False, "error": "Invalid email"}), 400
    ok = db.add_subscriber(email, source)
    if ok:
        # Send welcome email in the background so the request returns instantly.
        from scripts.utils import mailer

        def _send_welcome():
            try:
                subj, html, text = mailer.welcome_email(email)
                sent = mailer.send_email(email, subj, html, text)
                if sent:
                    log.info("Welcome email sent to %s", email)
            except Exception as e:
                log.warning("Welcome email failed for %s: %s", email, e)

        threading.Thread(target=_send_welcome, daemon=True).start()
    return jsonify({"ok": ok, "count": db.count_subscribers(), "welcome_sent": bool(os.getenv("SMTP_HOST"))})


@app.route("/api/unsubscribe")
def api_unsubscribe():
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return "Missing email", 400
    db.remove_subscriber(email)
    return f"<p style='font-family:system-ui;padding:48px;text-align:center;'>Unsubscribed <strong>{email}</strong>. We're sorry to see you go.</p>"


@app.route("/api/stories.json")
def api_stories():
    """Filter / search / paginate. Used by the dynamic home page."""
    q = (request.args.get("q") or "").strip().lower()
    sport = (request.args.get("sport") or "").strip()
    typ = (request.args.get("type") or "").strip()           # athlete | para
    country = (request.args.get("country") or "").strip()
    sort = (request.args.get("sort") or "").strip().lower()  # newest | confidence | name
    limit = max(1, min(60, int(request.args.get("limit", "12"))))
    offset = max(0, int(request.args.get("offset", "0")))

    cards = _all_published_cards()

    if q:
        cards = [c for c in cards if q in (
            (c.get("athlete_name", "") + " " + c.get("sport", "") + " " +
             c.get("country", "") + " " + c.get("hook", "") + " " +
             c.get("pull_quote", "")).lower()
        )]
    if sport and sport != "all":
        cards = [c for c in cards if (c.get("sport") or "").lower() == sport.lower()]
    if typ and typ != "all":
        cards = [c for c in cards if (c.get("type") or "") == typ]
    if country and country != "all":
        cards = [c for c in cards if (c.get("country") or "").lower() == country.lower()]

    # Sort (default keeps storage order = newest published last → reverse for newest-first)
    if sort == "name":
        cards = sorted(cards, key=lambda c: (c.get("athlete_name") or "").lower())
    elif sort == "confidence":
        cards = sorted(cards, key=lambda c: c.get("confidence_score") or 0, reverse=True)
    elif sort == "newest":
        cards = list(reversed(cards))

    total = len(cards)
    page = cards[offset: offset + limit]
    return jsonify({
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": page,
        "has_more": (offset + limit) < total,
    })


@app.route("/story/<sid>")
def public_story(sid):
    # Seed (demo) stories live in code, not on disk.
    if sid in SEED_STORIES:
        s = SEED_STORIES[sid]
    else:
        try:
            s = storage.load_story(sid)
        except FileNotFoundError:
            abort(404)
        if s.get("status") != "published" and not _is_admin():
            abort(404)
    # 3 related stories — same sport first, fall back to other published or seed.
    all_pub = [_card(x) for x in storage.list_stories("published") if x.get("story_id") != sid]
    if not all_pub:
        all_pub = [_card(x) for k, x in SEED_STORIES.items() if k != sid]
    same_sport = [c for c in all_pub if c["sport"].lower() == (s.get("sport") or "").lower()]
    related = (same_sport + [c for c in all_pub if c not in same_sport])[:3]

    # Social-share / SEO metadata for this story (link previews + JSON-LD).
    sections = s.get("sections") or {}
    desc = _excerpt(sections.get("hook") or sections.get("into_you") or s.get("pull_quote") or SITE_TAGLINE)
    meta = {
        "title": f"{s.get('athlete_name','')} · {SITE_NAME}",
        "description": desc,
        "image": _abs_url(s.get("image_url") or (s.get("dossier") or {}).get("image_url") or ""),
        "url": _abs_url(url_for("public_story", sid=sid)),
        "type": "article",
        "athlete": s.get("athlete_name", ""),
        "sport": s.get("sport", ""),
    }
    return render_template(
        "public_story.html",
        s=s, sections=s["sections"], lang="en", langs=LANGS, site=SITE_NAME, is_admin=_is_admin(),
        related=related, meta=meta,
    )


# ---------- Admin login ----------

@app.route("/admin/login", methods=["POST"])
def admin_login():
    tok = request.form.get("token", "")
    if ADMIN_TOKEN and tok != ADMIN_TOKEN:
        flash("Invalid admin token.")
        return redirect(url_for("home"))
    resp = make_response(redirect(url_for("admin_home")))
    resp.set_cookie("admin_token", tok, httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 7)
    return resp


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    resp = make_response(redirect(url_for("home")))
    resp.delete_cookie("admin_token")
    return resp


# ---------- Admin console ----------

@app.route("/admin")
@admin_required
def admin_home():
    pending = storage.list_stories("pending_review")
    published = storage.list_stories("published")[-10:][::-1]
    rejected = storage.list_stories("rejected")[-10:][::-1]
    queue = storage.load_queue()
    dossiers = []
    for p in sorted(DOSSIERS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = _json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, list):
                d = d[0] if (d and isinstance(d[0], dict)) else {}
            if not isinstance(d, dict):
                continue
            dossiers.append({"slug": p.stem, "name": d.get("athlete_name", p.stem),
                             "sport": d.get("sport", ""), "country": d.get("country", ""),
                             "image_url": d.get("image_url", "")})
        except Exception:
            pass
    analytics = {
        "total_visits":     db.total_visits(),
        "today":            db.visits_today(),
        "unique_visitors":  db.unique_visitors(),
        "subscribers":      db.count_subscribers(),
        "top_stories":      db.top_stories(5),
    }
    return render_template(
        "admin_home.html",
        pending=pending, published=published, rejected=rejected, queue=queue, dossiers=dossiers,
        analytics=analytics,
        site=SITE_NAME, is_admin=True, model_name=os.getenv("NVIDIA_STORY_MODEL", "openai/gpt-oss-20b"),
        research_models=RESEARCH_MODELS, is_nvidia_research=True,
    )


@app.route("/admin/story/<sid>")
@admin_required
def admin_review(sid):
    try:
        s = storage.load_story(sid)
    except FileNotFoundError:
        abort(404)
    return render_template(
        "admin_review.html",
        s=s, sections=s["sections"], lang="en", langs=LANGS, site=SITE_NAME, is_admin=True,
    )


@app.route("/admin/story/<sid>/approve", methods=["POST"])
@admin_required
def admin_approve(sid):
    storage.update_story(sid, status="approved")
    try:
        publishing_agent.publish(sid)
        flash(f"Approved & published: {sid}")
    except Exception as e:
        flash(f"Approved but publishing failed: {e}")
    return redirect(url_for("admin_home"))


@app.route("/admin/story/<sid>/reject", methods=["POST"])
@admin_required
def admin_reject(sid):
    storage.update_story(sid, status="rejected", reject_reason=request.form.get("reason", ""))
    flash(f"Rejected: {sid}")
    return redirect(url_for("admin_home"))


# ---------- Background actions ----------

_jobs_lock = threading.Lock()
_jobs: dict = {}  # job_id -> {label, status, steps:[{name,status,t}], started, finished, result}


def _new_job(job_id: str, label: str) -> None:
    import time as _t
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id, "label": label, "status": "running",
            "steps": [], "started": _t.time(), "finished": None, "result": "",
        }


def _step(job_id: str, step_name: str, status: str = "running", note: str = "") -> None:
    """status: running | done | error"""
    import time as _t
    with _jobs_lock:
        j = _jobs.get(job_id)
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


def _finish_job(job_id: str, status: str, result: str = "") -> None:
    import time as _t
    with _jobs_lock:
        j = _jobs.get(job_id)
        if not j:
            return
        j["status"] = status
        j["finished"] = _t.time()
        j["result"] = result[:500]


def _spawn(job_id: str, label: str, fn, *args, **kw):
    """Spawn a job. The target fn receives `job_id` as a keyword argument so it can call _step()."""
    _new_job(job_id, label)

    def _runner():
        try:
            res = fn(*args, job_id=job_id, **kw)
            _finish_job(job_id, "done", str(res))
        except Exception as e:
            import traceback
            _step(job_id, "error", "error", str(e)[:200])
            _finish_job(job_id, "error", str(e))
            traceback.print_exc()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()


@app.route("/admin/run-discovery", methods=["POST"])
@admin_required
def admin_run_discovery():
    n = int(request.form.get("n", "5"))
    import time as _t
    _spawn(f"discovery-{int(_t.time())}", f"Discovery · {n} athletes", _discovery_job, n)
    flash("Discovery started — watch progress below.")
    return redirect(url_for("admin_home"))


@app.route("/admin/research", methods=["POST"])
@admin_required
def admin_research():
    """Research-only flow: build a dossier in the background and show progress."""
    name = request.form.get("athlete", "").strip()
    sport = request.form.get("sport", "").strip()
    model_key = request.form.get("model", "nemotron").strip()
    
    # Validate model selection
    if model_key not in RESEARCH_MODELS:
        model_key = "nemotron"
    
    model_config = RESEARCH_MODELS[model_key]
    
    if not name:
        flash("Enter an athlete name.")
        return redirect(url_for("admin_home"))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    import time as _t
    job_id = f"research-{int(_t.time())}"
    _spawn(job_id, f"Research · {name} ({model_config['label']})", _research_job, 
           name, sport, slug, model_key, model_config["model"])
    flash(f"Research started for {name} using {model_config['label']} — opens automatically when done. Refresh to check.")
    return redirect(url_for("admin_home"))


@app.route("/admin/research/<slug>")
@admin_required
def admin_research_view(slug):
    path = DOSSIERS / f"{slug}.json"
    if not path.exists():
        abort(404)
    dossier = _json.loads(path.read_text(encoding="utf-8"))
    if isinstance(dossier, list):
        dossier = (dossier[0] if dossier else {}) if isinstance(dossier[0] if dossier else None, dict) else {}
    return render_template(
        "admin_research.html", dossier=dossier, slug=slug, site=SITE_NAME, is_admin=True,
        research_model=nvidia_client.MODEL, model_name=os.getenv("NVIDIA_STORY_MODEL", "openai/gpt-oss-20b"),
        is_nvidia_research=True,
    )


@app.route("/admin/research/<slug>/write", methods=["POST"])
@admin_required
def admin_research_write(slug):
    """Promote a saved dossier into a full pipeline run (write/translate/QA)."""
    path = DOSSIERS / f"{slug}.json"
    if not path.exists():
        abort(404)
    dossier = _json.loads(path.read_text(encoding="utf-8"))
    if isinstance(dossier, list):
        dossier = (dossier[0] if dossier else {}) if isinstance(dossier[0] if dossier else None, dict) else {}
    athlete = {"name": dossier.get("athlete_name", slug), "sport": dossier.get("sport", ""), "country": dossier.get("country", "")}
    _spawn(f"write-{slug}", f"Writing story · {athlete['name']}", _write_from_dossier, athlete, dossier, slug)
    flash(f"Writing story for {athlete['name']} — watch progress on the admin home.")
    return redirect(url_for("admin_home"))


@app.route("/admin/research/<slug>/rerun", methods=["POST"])
@admin_required
def admin_research_rerun(slug):
    """Re-run the research agent on an existing dossier with a chosen model."""
    existing = db.get_dossier(slug) or {}
    name = existing.get("athlete_name") or slug.replace("-", " ").title()
    sport = existing.get("sport", "")
    model_key = request.form.get("model", "gpt_oss")
    if model_key not in RESEARCH_MODELS:
        model_key = "gpt_oss"
    model_name = RESEARCH_MODELS[model_key]["model"]
    import time as _t
    _spawn(f"research-{int(_t.time())}",
           f"Re-research · {name} · {RESEARCH_MODELS[model_key]['label']}",
           _research_job, name, sport, slug, model_key, model_name)
    flash(f"Re-running research for {name} with {RESEARCH_MODELS[model_key]['label']}.")
    return redirect(url_for("admin_research_view", slug=slug))


@app.route("/admin/research/<slug>/delete", methods=["POST"])
@admin_required
def admin_research_delete(slug):
    path = DOSSIERS / f"{slug}.json"
    if path.exists():
        path.unlink()
    try:
        db.delete_dossier(slug)
    except Exception:
        pass
    flash("Dossier discarded.")
    return redirect(url_for("admin_home"))


def _write_from_dossier(athlete: dict, dossier: dict, slug: str = "", job_id: str = ""):
    """Write the story, then QA + score in the background so the editor can
    immediately review the prose while QA runs.

    Order:
      1. Story writer (gpt-oss-120b) — primary, blocking
      2. Save to disk + DB as `pending_review` so it appears in the queue
      3. QA scoring (writes confidence + flags back to the same record)
    """
    import re as _re
    from datetime import datetime as _dt
    from scripts.pipeline import story_writer_agent, quality_checker_agent

    _step(job_id, f"Writing story · {athlete['name']}", "running")
    try:
        sections = story_writer_agent.run(dossier, slug=slug or None)
        word_count = sum(len(str(v).split()) for v in sections.values() if isinstance(v, str))
        _step(job_id, f"Writing story · {athlete['name']}", "done", note=f"{word_count} words")
    except Exception as e:
        _step(job_id, f"Writing story · {athlete['name']}", "error", note=str(e)[:160])
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
        "story_model": os.getenv("NVIDIA_STORY_MODEL", "openai/gpt-oss-120b"),
        "research_model": (dossier.get("_research_model") or {}).get("name", ""),
    }
    storage.save_story(sid, payload)
    _step(job_id, "Saved · ready for review", "done")

    # QA in the SAME job so the progress card shows the score arriving.
    _step(job_id, "Quality check · scoring confidence", "running")
    try:
        qa = quality_checker_agent.run(sections, dossier)
        confidence = int(qa.get("confidence_score", 0) or 0)
        payload["qa"] = qa
        payload["confidence_score"] = confidence
        storage.save_story(sid, payload)
        _step(job_id, "Quality check · scoring confidence", "done",
              note=f"confidence {confidence}% · {qa.get('verdict','review')}")
    except Exception as e:
        _step(job_id, "Quality check · scoring confidence", "error", note=str(e)[:160])

    return sid


def _research_job(name: str, sport: str, slug: str, model_key: str, model_name: str, job_id: str = ""):
    """Background research job — runs the research agent, fetches an image,
    counts sources/quotes, and saves to both disk and SQLite.

    The job posts multiple progress steps so the admin sees a real progress
    bar instead of a single spinner during the long research call.
    """
    # 1) Build dossier (this is the slow step — gpt-oss-120b can take 60-90s)
    _step(job_id, f"Researching {name} · gathering facts", "running")
    try:
        dossier = research_agent.run(name, sport, model_name=model_name)
    except Exception as e:
        _step(job_id, f"Researching {name} · gathering facts", "error", note=str(e)[:200])
        raise
    sources = dossier.get("sources", []) or []
    quotes = dossier.get("exact_quotes", []) or []
    _step(job_id, f"Researching {name} · gathering facts", "done",
          note=f"{len(sources)} sources · {len(quotes)} quotes")

    # 2) Tag with model metadata
    _step(job_id, "Tagging model + verifying coverage", "running")
    dossier["_research_model"] = {
        "key": model_key,
        "name": model_name,
        "label": RESEARCH_MODELS[model_key]["label"],
    }
    # Quick coverage audit — flag missing critical fields
    required = ["birth", "disability_or_injury", "early_life", "key_struggles",
                "darkest_moment_scene", "turning_point", "training_habits",
                "daily_routine_details", "competitions", "exact_quotes", "outcomes",
                "ripple_effects", "principle_or_research"]
    missing = [k for k in required if not dossier.get(k)]
    dossier["_coverage_missing"] = missing
    cov_pct = int(100 * (len(required) - len(missing)) / len(required))
    note = f"{cov_pct}% coverage" + (f" · missing: {', '.join(missing[:3])}" if missing else " · all fields present")
    _step(job_id, "Tagging model + verifying coverage", "done", note=note)

    # 3) Save (disk + DB)
    _step(job_id, "Saving dossier", "running")
    try:
        (DOSSIERS / f"{slug}.json").write_text(_json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8")
        db.upsert_dossier(slug, dossier)
        img_note = "with photo" if dossier.get("image_url") else "no photo found"
        _step(job_id, "Saving dossier", "done", note=img_note)
    except Exception as e:
        _step(job_id, "Saving dossier", "error", note=str(e)[:160])
        raise
    return slug


def _discovery_job(n: int, job_id: str = ""):
    _step(job_id, f"Searching for {n} new athletes", "running")
    found = discovery_agent.run(n)
    _step(job_id, f"Searching for {n} new athletes", "done", note=f"{len(found)} queued")
    return f"queued {len(found)}"


def _pipeline_one_job(athlete: dict, job_id: str = ""):
    """Full pipeline on one athlete with per-step progress."""
    name = athlete["name"]
    sport = athlete.get("sport", "")
    _step(job_id, f"Researching {name}", "running")
    dossier = research_agent.run(name, sport)
    _step(job_id, f"Researching {name}", "done", note=f"{len(dossier.get('sources', []))} sources")
    return _write_from_dossier(athlete, dossier, job_id=job_id)


def _pipeline_daily_job(quota: int, job_id: str = ""):
    _step(job_id, "Loading queue", "running")
    q = storage.load_queue()
    if len(q["queue"]) < quota:
        _step(job_id, "Queue empty — running discovery", "running")
        discovery_agent.run(quota * 3)
        _step(job_id, "Queue empty — running discovery", "done")
    _step(job_id, "Loading queue", "done")
    sids = []
    for i in range(quota):
        a = storage.pop_next()
        if not a:
            break
        try:
            sids.append(_pipeline_one_job(a, job_id=job_id))
            q = storage.load_queue()
            q.setdefault("processed", []).append(a)
            storage.save_queue(q)
        except Exception as e:
            _step(job_id, f"Failed: {a.get('name')}", "error", note=str(e)[:200])
    return f"processed {len(sids)}"


@app.route("/admin/run-pipeline", methods=["POST"])
@admin_required
def admin_run_pipeline():
    name = request.form.get("athlete", "").strip()
    sport = request.form.get("sport", "").strip()
    quota = int(request.form.get("quota", "1"))
    import time as _t
    if name:
        _spawn(f"pipeline-{int(_t.time())}", f"Pipeline · {name}", _pipeline_one_job, {"name": name, "sport": sport})
        flash(f"Pipeline started for {name} — watch progress below.")
    else:
        _spawn(f"daily-{int(_t.time())}", f"Daily pipeline · {quota} story(s)", _pipeline_daily_job, quota)
        flash(f"Daily pipeline started ({quota} stories) — watch progress below.")
    return redirect(url_for("admin_home"))


# ---------- Admin: subscribers + broadcast + analytics ----------

@app.route("/admin/subscribers")
@admin_required
def admin_subscribers():
    subs = db.list_subscribers(active_only=False)
    return render_template("admin_subscribers.html",
                           subscribers=subs,
                           total=db.count_subscribers(),
                           broadcasts=db.list_broadcasts(20),
                           site=SITE_NAME, is_admin=True)


@app.route("/admin/subscribers/remove", methods=["POST"])
@admin_required
def admin_subscriber_remove():
    db.remove_subscriber(request.form.get("email", ""))
    flash("Subscriber removed.")
    return redirect(url_for("admin_subscribers"))


@app.route("/admin/subscribers/add", methods=["POST"])
@admin_required
def admin_subscriber_add():
    email = (request.form.get("email") or "").strip().lower()
    if db.add_subscriber(email, source="manual"):
        flash(f"Added {email}")
    else:
        flash(f"Invalid email: {email}")
    return redirect(url_for("admin_subscribers"))


@app.route("/admin/subscribers/export")
@admin_required
def admin_subscribers_export():
    rows = db.list_subscribers(active_only=True)
    csv = "email,source,created_at\n" + "\n".join(
        f'{r["email"]},{r.get("source","")},{r["created_at"]}' for r in rows
    )
    from flask import Response
    return Response(csv, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=neverquit_subscribers.csv"})


@app.route("/admin/broadcast", methods=["POST"])
@admin_required
def admin_broadcast():
    subject = (request.form.get("subject") or "").strip()
    body = (request.form.get("body") or "").strip()
    if not subject or not body:
        flash("Subject and body are required.")
        return redirect(url_for("admin_subscribers"))

    subs = db.list_subscribers(active_only=True)
    sent = failures = 0
    via = "none"

    # Mailchimp first (single-campaign send to whole list)
    if os.getenv("MAILCHIMP_API_KEY"):
        try:
            from scripts.utils import mailchimp_client
            mailchimp_client.send_campaign(
                subject,
                f"<h1>{subject}</h1><div>{body.replace(chr(10), '<br>')}</div>",
            )
            sent, via = len(subs), "mailchimp"
        except Exception as e:
            failures = len(subs)
            flash(f"Mailchimp send failed: {e}")

    # Fall back to direct SMTP — per-subscriber, in a background thread
    elif os.getenv("SMTP_HOST"):
        recipients = [s["email"] for s in subs]

        def _send_all():
            ok = bad = 0
            for em in recipients:
                try:
                    subj, html, text = mailer.broadcast_email(subject, body, em)
                    if mailer.send_email(em, subj, html, text):
                        ok += 1
                    else:
                        bad += 1
                except Exception:
                    bad += 1
            log.info("Broadcast finished: %s sent, %s failed", ok, bad)
            db.log_broadcast(subject, body, ok, bad)

        threading.Thread(target=_send_all, daemon=True).start()
        sent, via = len(recipients), "smtp"
        flash(f"Broadcast queued via SMTP for {len(recipients)} subscribers — you'll see them arrive over the next minute or two.")

    else:
        sent = len(subs)
        flash("No mail provider configured. Set SMTP_HOST/SMTP_USER/SMTP_PASS or MAILCHIMP_API_KEY in .env to actually send. Broadcast was logged.")

    if via != "smtp":  # SMTP path logs from inside the thread
        db.log_broadcast(subject, body, sent, failures)
    return redirect(url_for("admin_subscribers"))


@app.route("/admin/analytics.json")
@admin_required
def admin_analytics():
    return jsonify({
        "total_visits": db.total_visits(),
        "today": db.visits_today(),
        "unique_visitors": db.unique_visitors(),
        "top_stories": db.top_stories(10),
        "subscribers": db.count_subscribers(),
    })


# ---------- Admin: delete a story ----------

@app.route("/admin/story/<sid>/delete", methods=["POST"])
@admin_required
def admin_story_delete(sid):
    """Move a story to trash (mark rejected) or hard-delete with ?hard=1."""
    hard = request.form.get("hard") == "1"
    s = storage.load_story(sid)
    if not s:
        abort(404)
    if hard:
        # Remove JSON file + DB row
        try:
            (storage.STORIES / f"{sid}.json").unlink(missing_ok=True)
        except Exception:
            pass
        try:
            with db.conn() as c:
                c.execute("DELETE FROM stories WHERE story_id=?", (sid,))
        except Exception:
            pass
        flash(f"Hard-deleted {sid}")
    else:
        s["status"] = "rejected"
        s["reject_reason"] = request.form.get("reason", "deleted by admin")
        storage.save_story(sid, s)
        flash(f"Moved {sid} to rejected")
    return redirect(url_for("admin_home"))


# ─── Section visibility (admin controls what the public reader sees) ───

# Canonical list of toggleable section keys. Anything not in this list
# is always rendered (e.g. title, byline, country flag).
SECTION_KEYS = [
    "key_facts",          # the orange highlight tiles (dossier.outcomes)
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
    "inner_reframe",      # italic lie-vs-truth block
    "why_this_works",     # research backing
    "tiny_practices",     # numbered practices list
    "body_protocol",      # universal recovery basics
    "two_minute_actions", # 3 reader actions
    "ask_yourself",       # one question to carry away
    "share",              # share buttons
    "newsletter_cta",     # inline newsletter capture
    "related",            # "more comebacks" carousel
]


def is_visible(s: dict, key: str) -> bool:
    """A section is visible unless the admin has explicitly hidden it."""
    hidden = (s or {}).get("hidden_sections") or []
    return key not in hidden


# Expose to all templates as `vis(section_key, story)`
@app.context_processor
def _inject_visibility():
    return {"vis": is_visible, "SECTION_KEYS": SECTION_KEYS}


@app.route("/admin/story/<sid>/visibility", methods=["POST"])
@admin_required
def admin_story_visibility(sid):
    """Toggle which sections show to the public. Form: `visible=key1&visible=key2&...`
    Any SECTION_KEYS not in the form value list end up in `hidden_sections`."""
    s = storage.load_story(sid)
    if not s:
        abort(404)
    visible_keys = set(request.form.getlist("visible"))
    s["hidden_sections"] = [k for k in SECTION_KEYS if k not in visible_keys]
    storage.save_story(sid, s)
    flash(f"Visibility updated · {len(s['hidden_sections'])} section(s) hidden from public.")
    return redirect(request.referrer or url_for("admin_review", sid=sid))


@app.route("/admin/story/<sid>/visibility/preset", methods=["POST"])
@admin_required
def admin_story_visibility_preset(sid):
    """Apply a one-click preset: 'all', 'minimal', 'reader_only'."""
    s = storage.load_story(sid)
    if not s:
        abort(404)
    preset = request.form.get("preset", "all")
    if preset == "all":
        s["hidden_sections"] = []
    elif preset == "minimal":
        # Bare-essentials reading flow only
        keep = {"into_you", "hook", "world_came_from", "pull_quote",
                "darkest_moment", "turning_point", "outcome",
                "comeback_timeline", "share"}
        s["hidden_sections"] = [k for k in SECTION_KEYS if k not in keep]
    elif preset == "reader_only":
        # Story-only — no practices, no CTAs
        keep = {"into_you", "hook", "world_came_from", "pull_quote",
                "darkest_moment", "turning_point", "the_grind", "outcome",
                "comeback_timeline", "lessons"}
        s["hidden_sections"] = [k for k in SECTION_KEYS if k not in keep]
    else:
        flash(f"Unknown preset: {preset}")
        return redirect(request.referrer or url_for("admin_review", sid=sid))
    storage.save_story(sid, s)
    flash(f"Applied preset '{preset}'.")
    return redirect(request.referrer or url_for("admin_review", sid=sid))


# ─── Inline edit story metadata (title/sport/country) ───

@app.route("/admin/story/<sid>/edit", methods=["POST"])
@admin_required
def admin_story_edit(sid):
    s = storage.load_story(sid)
    if not s:
        abort(404)
    name = (request.form.get("athlete_name") or "").strip()
    sport = (request.form.get("sport") or "").strip()
    country = (request.form.get("country") or "").strip()
    headline = (request.form.get("headline") or "").strip()
    if name:    s["athlete_name"] = name
    if sport:   s["sport"] = sport
    if country: s["country"] = country
    if headline:
        s.setdefault("sections", {})["headline"] = headline
    storage.save_story(sid, s)
    flash(f"Updated metadata for {s['athlete_name']}")
    return redirect(request.referrer or url_for("admin_home"))


# ─── Bulk actions on pending stories ───

@app.route("/admin/bulk", methods=["POST"])
@admin_required
def admin_bulk():
    """Apply an action to many stories at once. Pass `ids=a,b,c` and `action`."""
    ids = [x.strip() for x in (request.form.get("ids") or "").split(",") if x.strip()]
    action = (request.form.get("action") or "").strip()
    if not ids or not action:
        flash("Pick stories and an action.")
        return redirect(url_for("admin_home"))
    done = 0
    for sid in ids:
        try:
            s = storage.load_story(sid)
        except Exception:
            continue
        if not s:
            continue
        if action == "approve":
            s["status"] = "approved"
            storage.save_story(sid, s)
            try: publishing_agent.publish(sid)
            except Exception: pass
            done += 1
        elif action == "reject":
            s["status"] = "rejected"
            s["reject_reason"] = "bulk-rejected"
            storage.save_story(sid, s)
            done += 1
        elif action == "unpublish":
            s["status"] = "pending_review"
            storage.save_story(sid, s)
            done += 1
    flash(f"Applied '{action}' to {done} stor{'y' if done == 1 else 'ies'}.")
    return redirect(url_for("admin_home"))


@app.route("/admin/story/<sid>/unpublish", methods=["POST"])
@admin_required
def admin_story_unpublish(sid):
    s = storage.load_story(sid)
    if not s: abort(404)
    s["status"] = "pending_review"
    storage.save_story(sid, s)
    flash(f"Unpublished {s['athlete_name']}")
    return redirect(request.referrer or url_for("admin_home"))


# ─── Resend welcome email to a subscriber ───

@app.route("/admin/subscribers/resend", methods=["POST"])
@admin_required
def admin_subscriber_resend():
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        flash("Email required.")
        return redirect(url_for("admin_subscribers"))
    try:
        subj, html, text = mailer.welcome_email(email)
        sent = mailer.send_email(email, subj, html, text)
        flash(f"Welcome email {'sent to' if sent else 'queued (SMTP disabled) for'} {email}.")
    except Exception as e:
        flash(f"Resend failed: {e}")
    return redirect(url_for("admin_subscribers"))


# ─── User: saved stories page (powered by localStorage IDs in the browser) ───

@app.route("/saved")
def saved_page():
    # No server-side state — the page reads IDs from localStorage and hits /api/stories.json/<id>
    return render_template("saved.html", site=SITE_NAME, is_admin=_is_admin())


@app.route("/api/story/<sid>.json")
def api_one_story(sid):
    """Return a compact card payload for one story — used by /saved."""
    if sid in SEED_STORIES:
        s = SEED_STORIES[sid]
    else:
        try:
            s = storage.load_story(sid)
        except FileNotFoundError:
            return jsonify({"error": "not_found"}), 404
        if s.get("status") != "published":
            return jsonify({"error": "not_published"}), 404
    return jsonify(_card(s))


# ─── User: submit an athlete ───

SUBMISSIONS = ROOT / "data" / "submissions"
SUBMISSIONS.mkdir(parents=True, exist_ok=True)


@app.route("/submit")
def submit_page():
    return render_template("submit.html", site=SITE_NAME, is_admin=_is_admin())


@app.route("/api/submit", methods=["POST"])
def api_submit():
    name = (request.form.get("athlete_name") or "").strip()
    sport = (request.form.get("sport") or "").strip()
    country = (request.form.get("country") or "").strip()
    why = (request.form.get("why") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    if not name or len(why) < 30:
        return jsonify({"ok": False, "error": "Name and a reason (30+ chars) are required."}), 400
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    payload = {
        "athlete_name": name, "sport": sport, "country": country,
        "why": why, "submitted_by": email,
        "submitted_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
    (SUBMISSIONS / f"{slug}-{int(__import__('time').time())}.json").write_text(
        _json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return jsonify({"ok": True})


@app.route("/admin/jobs.json")
@admin_required
def admin_jobs():
    with _jobs_lock:
        return jsonify(_jobs)


# ---------- SEO / syndication: RSS feed, sitemap, robots ----------

from xml.sax.saxutils import escape as _xml_escape  # noqa: E402


@app.route("/feed.xml")
@app.route("/rss")
def rss_feed():
    """RSS 2.0 feed of the most recent published stories."""
    cards = list(reversed(_all_published_cards()))[:30]
    base = _site_url()
    items = []
    for c in cards:
        link = _abs_url(url_for("public_story", sid=c["id"]))
        title = _xml_escape(f'{c["athlete_name"]} — {c.get("sport","")}'.strip(" —"))
        desc = _xml_escape(_excerpt(c.get("hook") or c.get("pull_quote") or "", 300))
        img = _abs_url(c.get("image_url") or "")
        enclosure = f'<enclosure url="{_xml_escape(img)}" type="image/jpeg" />' if img else ""
        items.append(
            f"<item><title>{title}</title><link>{link}</link>"
            f"<guid isPermaLink=\"true\">{link}</guid>"
            f"<description>{desc}</description>{enclosure}</item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{_xml_escape(SITE_NAME)}</title>"
        f"<link>{_xml_escape(base)}</link>"
        f"<description>{_xml_escape(SITE_TAGLINE)}</description>"
        "<language>en</language>"
        + "".join(items)
        + "</channel></rss>"
    )
    return app.response_class(xml, mimetype="application/rss+xml")


@app.route("/sitemap.xml")
def sitemap():
    """XML sitemap covering static pages + every published story."""
    base = _site_url()
    urls = [f"{base}/", f"{base}/saved", f"{base}/submit"]
    urls += [_abs_url(url_for("public_story", sid=c["id"])) for c in _all_published_cards()]
    body = "".join(f"<url><loc>{_xml_escape(u)}</loc></url>" for u in urls)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           f"{body}</urlset>")
    return app.response_class(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    base = _site_url()
    txt = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /api\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return app.response_class(txt, mimetype="text/plain")


# ---------- Health ----------

@app.route("/media/<path:filename>")
def media(filename):
    from flask import send_from_directory
    resp = send_from_directory(IMAGES, filename)
    # Athlete photos rarely change — cache aggressively at the browser & CDN.
    resp.headers["Cache-Control"] = "public, max-age=2592000, immutable"  # 30 days
    return resp


# ─── Lightweight gzip compression for HTML/JSON responses ───
@app.after_request
def _maybe_gzip(resp):
    try:
        if (
            resp.status_code < 200 or resp.status_code >= 300
            or "Content-Encoding" in resp.headers
            or resp.direct_passthrough
        ):
            return resp
        accept = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept.lower():
            return resp
        ct = (resp.headers.get("Content-Type") or "").lower()
        if not any(ct.startswith(x) for x in ("text/", "application/json", "application/javascript", "application/xml")):
            return resp
        data = resp.get_data()
        if len(data) < 1024:  # not worth compressing tiny payloads
            return resp
        import gzip
        gzipped = gzip.compress(data, compresslevel=6)
        resp.set_data(gzipped)
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Content-Length"] = str(len(gzipped))
        resp.headers["Vary"] = "Accept-Encoding"
    except Exception:
        pass
    return resp


# ---------- Admin: edit athlete photo ----------

ALLOWED_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _save_uploaded_image(file_storage, slug: str) -> str | None:
    """Save an uploaded image to data/images/<slug>.jpg. Returns /media/ URL."""
    if not file_storage or not file_storage.filename:
        return None
    ext = ("." + file_storage.filename.rsplit(".", 1)[-1].lower()) if "." in file_storage.filename else ""
    if ext not in ALLOWED_IMG_EXT:
        return None
    out = IMAGES / f"{slug}.jpg"
    file_storage.save(out)
    # bust browser cache
    return f"/media/{slug}.jpg?v={int(__import__('time').time())}"


@app.route("/admin/story/<sid>/edit-photo", methods=["POST"])
@admin_required
def admin_edit_story_photo(sid):
    """Replace an athlete photo for a saved story (upload OR remote URL)."""
    s = storage.load_story(sid)
    if not s:
        abort(404)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (s.get("athlete_name") or sid).lower()).strip("-") or sid
    new_url = None
    file = request.files.get("photo")
    if file and file.filename:
        new_url = _save_uploaded_image(file, slug)
    else:
        remote = (request.form.get("photo_url") or "").strip()
        if remote:
            try:
                import requests as _r
                resp = _r.get(remote, headers={"User-Agent": "NeverQuitBot/1.0"}, timeout=15)
                resp.raise_for_status()
                if resp.headers.get("content-type", "").startswith("image/"):
                    (IMAGES / f"{slug}.jpg").write_bytes(resp.content)
                    new_url = f"/media/{slug}.jpg?v={int(__import__('time').time())}"
            except Exception as e:
                flash(f"Failed to fetch image: {e}")
    if new_url:
        s["image_url"] = new_url
        if isinstance(s.get("dossier"), dict):
            s["dossier"]["image_url"] = new_url
        storage.save_story(sid, s)
        flash("Photo updated.")
    else:
        flash("No valid image provided. Use a JPG/PNG/WebP file or a direct image URL.")
    return redirect(request.referrer or url_for("admin_review", sid=sid))


@app.route("/admin/research/<slug>/edit-photo", methods=["POST"])
@admin_required
def admin_edit_dossier_photo(slug):
    """Replace photo on a saved dossier."""
    path = DOSSIERS / f"{slug}.json"
    if not path.exists():
        abort(404)
    dossier = _json.loads(path.read_text(encoding="utf-8"))
    if isinstance(dossier, list):
        dossier = dossier[0] if dossier else {}
    new_url = None
    file = request.files.get("photo")
    if file and file.filename:
        new_url = _save_uploaded_image(file, slug)
    else:
        remote = (request.form.get("photo_url") or "").strip()
        if remote:
            try:
                import requests as _r
                resp = _r.get(remote, headers={"User-Agent": "NeverQuitBot/1.0"}, timeout=15)
                resp.raise_for_status()
                if resp.headers.get("content-type", "").startswith("image/"):
                    (IMAGES / f"{slug}.jpg").write_bytes(resp.content)
                    new_url = f"/media/{slug}.jpg?v={int(__import__('time').time())}"
            except Exception as e:
                flash(f"Failed to fetch image: {e}")
    if new_url:
        dossier["image_url"] = new_url
        path.write_text(_json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            db.upsert_dossier(slug, dossier)
        except Exception:
            pass
        flash("Photo updated.")
    return redirect(url_for("admin_research_view", slug=slug))


@app.route("/healthz")
def healthz():
    return {"ok": True, "site": SITE_NAME}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
