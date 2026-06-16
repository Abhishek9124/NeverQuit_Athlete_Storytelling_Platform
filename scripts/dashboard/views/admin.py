"""Admin console: review queue, pipeline triggers, subscribers, media, jobs."""
from __future__ import annotations
import os
import re
import json as _json
import time as _t
import threading
import logging

from flask import (
    Blueprint, render_template, request, redirect, url_for, abort,
    jsonify, make_response, flash, Response,
)

from scripts.utils import storage, db, model_config, mailer
from scripts.pipeline import publishing_agent
from scripts.dashboard import config, jobs
from scripts.dashboard.helpers import admin_required, _save_uploaded_image

log = logging.getLogger("neverquit.app")
bp = Blueprint("admin", __name__)


# ---------- Auth ----------

@bp.route("/admin/login", methods=["POST"])
def admin_login():
    tok = request.form.get("token", "")
    if config.ADMIN_TOKEN and tok != config.ADMIN_TOKEN:
        flash("Invalid admin token.")
        return redirect(url_for("public.home"))
    resp = make_response(redirect(url_for("admin.admin_home")))
    resp.set_cookie("admin_token", tok, httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 7)
    return resp


@bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    resp = make_response(redirect(url_for("public.home")))
    resp.delete_cookie("admin_token")
    return resp


# ---------- Console home ----------

@bp.route("/admin")
@admin_required
def admin_home():
    pending = storage.list_stories("pending_review")
    published = storage.list_stories("published")[-10:][::-1]
    rejected = storage.list_stories("rejected")[-10:][::-1]
    queue = storage.load_queue()
    dossiers = []
    for p in sorted(config.DOSSIERS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
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
        analytics=analytics, site=config.SITE_NAME, is_admin=True,
        model_name=model_config.model_for("story"),
        research_models=config.RESEARCH_MODELS, is_nvidia_research=True,
    )


@bp.route("/admin/story/<sid>")
@admin_required
def admin_review(sid):
    try:
        s = storage.load_story(sid)
    except FileNotFoundError:
        abort(404)
    return render_template(
        "admin_review.html",
        s=s, sections=s["sections"], lang="en", langs=config.LANGS, site=config.SITE_NAME, is_admin=True,
    )


@bp.route("/admin/story/<sid>/approve", methods=["POST"])
@admin_required
def admin_approve(sid):
    storage.update_story(sid, status="approved")
    try:
        publishing_agent.publish(sid)
        flash(f"Approved & published: {sid}")
    except Exception as e:
        flash(f"Approved but publishing failed: {e}")
    return redirect(url_for("admin.admin_home"))


@bp.route("/admin/story/<sid>/reject", methods=["POST"])
@admin_required
def admin_reject(sid):
    storage.update_story(sid, status="rejected", reject_reason=request.form.get("reason", ""))
    flash(f"Rejected: {sid}")
    return redirect(url_for("admin.admin_home"))


# ---------- Pipeline triggers ----------

@bp.route("/admin/run-discovery", methods=["POST"])
@admin_required
def admin_run_discovery():
    n = int(request.form.get("n", "5"))
    jobs.spawn(f"discovery-{int(_t.time())}", f"Discovery · {n} athletes", jobs.discovery_job, n)
    flash("Discovery started — watch progress below.")
    return redirect(url_for("admin.admin_home"))


@bp.route("/admin/research", methods=["POST"])
@admin_required
def admin_research():
    """Research-only flow: build a dossier in the background and show progress."""
    name = request.form.get("athlete", "").strip()
    sport = request.form.get("sport", "").strip()
    model_key = request.form.get("model", "nemotron").strip()
    if model_key not in config.RESEARCH_MODELS:
        model_key = "nemotron"
    model_cfg = config.RESEARCH_MODELS[model_key]

    if not name:
        flash("Enter an athlete name.")
        return redirect(url_for("admin.admin_home"))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    job_id = f"research-{int(_t.time())}"
    jobs.spawn(job_id, f"Research · {name} ({model_cfg['label']})", jobs.research_job,
               name, sport, slug, model_key, model_cfg["model"])
    flash(f"Research started for {name} using {model_cfg['label']} — opens automatically when done. Refresh to check.")
    return redirect(url_for("admin.admin_home"))


@bp.route("/admin/research/<slug>")
@admin_required
def admin_research_view(slug):
    path = config.DOSSIERS / f"{slug}.json"
    if not path.exists():
        abort(404)
    dossier = _json.loads(path.read_text(encoding="utf-8"))
    if isinstance(dossier, list):
        dossier = (dossier[0] if dossier else {}) if isinstance(dossier[0] if dossier else None, dict) else {}
    return render_template(
        "admin_research.html", dossier=dossier, slug=slug, site=config.SITE_NAME, is_admin=True,
        research_model=model_config.model_for("research"), model_name=model_config.model_for("story"),
        is_nvidia_research=True,
    )


@bp.route("/admin/research/<slug>/write", methods=["POST"])
@admin_required
def admin_research_write(slug):
    """Promote a saved dossier into a full pipeline run (write/QA)."""
    path = config.DOSSIERS / f"{slug}.json"
    if not path.exists():
        abort(404)
    dossier = _json.loads(path.read_text(encoding="utf-8"))
    if isinstance(dossier, list):
        dossier = (dossier[0] if dossier else {}) if isinstance(dossier[0] if dossier else None, dict) else {}
    athlete = {"name": dossier.get("athlete_name", slug), "sport": dossier.get("sport", ""), "country": dossier.get("country", "")}
    jobs.spawn(f"write-{slug}", f"Writing story · {athlete['name']}", jobs.write_from_dossier, athlete, dossier, slug)
    flash(f"Writing story for {athlete['name']} — watch progress on the admin home.")
    return redirect(url_for("admin.admin_home"))


@bp.route("/admin/research/<slug>/rerun", methods=["POST"])
@admin_required
def admin_research_rerun(slug):
    """Re-run the research agent on an existing dossier with a chosen model."""
    existing = db.get_dossier(slug) or {}
    name = existing.get("athlete_name") or slug.replace("-", " ").title()
    sport = existing.get("sport", "")
    model_key = request.form.get("model", "gpt_oss")
    if model_key not in config.RESEARCH_MODELS:
        model_key = "gpt_oss"
    model_name = config.RESEARCH_MODELS[model_key]["model"]
    jobs.spawn(f"research-{int(_t.time())}",
               f"Re-research · {name} · {config.RESEARCH_MODELS[model_key]['label']}",
               jobs.research_job, name, sport, slug, model_key, model_name)
    flash(f"Re-running research for {name} with {config.RESEARCH_MODELS[model_key]['label']}.")
    return redirect(url_for("admin.admin_research_view", slug=slug))


@bp.route("/admin/research/<slug>/delete", methods=["POST"])
@admin_required
def admin_research_delete(slug):
    path = config.DOSSIERS / f"{slug}.json"
    if path.exists():
        path.unlink()
    try:
        db.delete_dossier(slug)
    except Exception:
        pass
    flash("Dossier discarded.")
    return redirect(url_for("admin.admin_home"))


@bp.route("/admin/run-pipeline", methods=["POST"])
@admin_required
def admin_run_pipeline():
    name = request.form.get("athlete", "").strip()
    sport = request.form.get("sport", "").strip()
    quota = int(request.form.get("quota", "1"))
    if name:
        jobs.spawn(f"pipeline-{int(_t.time())}", f"Pipeline · {name}", jobs.pipeline_one_job, {"name": name, "sport": sport})
        flash(f"Pipeline started for {name} — watch progress below.")
    else:
        jobs.spawn(f"daily-{int(_t.time())}", f"Daily pipeline · {quota} story(s)", jobs.pipeline_daily_job, quota)
        flash(f"Daily pipeline started ({quota} stories) — watch progress below.")
    return redirect(url_for("admin.admin_home"))


# ---------- Subscribers + broadcast + analytics ----------

@bp.route("/admin/subscribers")
@admin_required
def admin_subscribers():
    subs = db.list_subscribers(active_only=False)
    return render_template("admin_subscribers.html",
                           subscribers=subs, total=db.count_subscribers(),
                           broadcasts=db.list_broadcasts(20),
                           site=config.SITE_NAME, is_admin=True)


@bp.route("/admin/subscribers/remove", methods=["POST"])
@admin_required
def admin_subscriber_remove():
    db.remove_subscriber(request.form.get("email", ""))
    flash("Subscriber removed.")
    return redirect(url_for("admin.admin_subscribers"))


@bp.route("/admin/subscribers/add", methods=["POST"])
@admin_required
def admin_subscriber_add():
    email = (request.form.get("email") or "").strip().lower()
    if db.add_subscriber(email, source="manual"):
        flash(f"Added {email}")
    else:
        flash(f"Invalid email: {email}")
    return redirect(url_for("admin.admin_subscribers"))


@bp.route("/admin/subscribers/export")
@admin_required
def admin_subscribers_export():
    rows = db.list_subscribers(active_only=True)
    csv = "email,source,created_at\n" + "\n".join(
        f'{r["email"]},{r.get("source","")},{r["created_at"]}' for r in rows
    )
    return Response(csv, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=neverquit_subscribers.csv"})


@bp.route("/admin/broadcast", methods=["POST"])
@admin_required
def admin_broadcast():
    subject = (request.form.get("subject") or "").strip()
    body = (request.form.get("body") or "").strip()
    if not subject or not body:
        flash("Subject and body are required.")
        return redirect(url_for("admin.admin_subscribers"))

    subs = db.list_subscribers(active_only=True)
    sent = failures = 0
    via = "none"

    if os.getenv("MAILCHIMP_API_KEY"):
        try:
            from scripts.utils import mailchimp_client
            mailchimp_client.send_campaign(
                subject, f"<h1>{subject}</h1><div>{body.replace(chr(10), '<br>')}</div>",
            )
            sent, via = len(subs), "mailchimp"
        except Exception as e:
            failures = len(subs)
            flash(f"Mailchimp send failed: {e}")

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
    return redirect(url_for("admin.admin_subscribers"))


@bp.route("/admin/analytics.json")
@admin_required
def admin_analytics():
    return jsonify({
        "total_visits": db.total_visits(),
        "today": db.visits_today(),
        "unique_visitors": db.unique_visitors(),
        "top_stories": db.top_stories(10),
        "subscribers": db.count_subscribers(),
    })


# ---------- Story lifecycle ----------

@bp.route("/admin/story/<sid>/delete", methods=["POST"])
@admin_required
def admin_story_delete(sid):
    """Move a story to trash (mark rejected) or hard-delete with ?hard=1."""
    hard = request.form.get("hard") == "1"
    s = storage.load_story(sid)
    if not s:
        abort(404)
    if hard:
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
    return redirect(url_for("admin.admin_home"))


@bp.route("/admin/story/<sid>/visibility", methods=["POST"])
@admin_required
def admin_story_visibility(sid):
    """Toggle which sections show to the public. Form: `visible=key1&visible=key2&...`"""
    s = storage.load_story(sid)
    if not s:
        abort(404)
    visible_keys = set(request.form.getlist("visible"))
    s["hidden_sections"] = [k for k in config.SECTION_KEYS if k not in visible_keys]
    storage.save_story(sid, s)
    flash(f"Visibility updated · {len(s['hidden_sections'])} section(s) hidden from public.")
    return redirect(request.referrer or url_for("admin.admin_review", sid=sid))


@bp.route("/admin/story/<sid>/visibility/preset", methods=["POST"])
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
        keep = {"into_you", "hook", "world_came_from", "pull_quote",
                "darkest_moment", "turning_point", "outcome",
                "comeback_timeline", "share"}
        s["hidden_sections"] = [k for k in config.SECTION_KEYS if k not in keep]
    elif preset == "reader_only":
        keep = {"into_you", "hook", "world_came_from", "pull_quote",
                "darkest_moment", "turning_point", "the_grind", "outcome",
                "comeback_timeline", "lessons"}
        s["hidden_sections"] = [k for k in config.SECTION_KEYS if k not in keep]
    else:
        flash(f"Unknown preset: {preset}")
        return redirect(request.referrer or url_for("admin.admin_review", sid=sid))
    storage.save_story(sid, s)
    flash(f"Applied preset '{preset}'.")
    return redirect(request.referrer or url_for("admin.admin_review", sid=sid))


@bp.route("/admin/story/<sid>/edit", methods=["POST"])
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
    return redirect(request.referrer or url_for("admin.admin_home"))


@bp.route("/admin/bulk", methods=["POST"])
@admin_required
def admin_bulk():
    """Apply an action to many stories at once. Pass `ids=a,b,c` and `action`."""
    ids = [x.strip() for x in (request.form.get("ids") or "").split(",") if x.strip()]
    action = (request.form.get("action") or "").strip()
    if not ids or not action:
        flash("Pick stories and an action.")
        return redirect(url_for("admin.admin_home"))
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
    return redirect(url_for("admin.admin_home"))


@bp.route("/admin/story/<sid>/unpublish", methods=["POST"])
@admin_required
def admin_story_unpublish(sid):
    s = storage.load_story(sid)
    if not s:
        abort(404)
    s["status"] = "pending_review"
    storage.save_story(sid, s)
    flash(f"Unpublished {s['athlete_name']}")
    return redirect(request.referrer or url_for("admin.admin_home"))


@bp.route("/admin/subscribers/resend", methods=["POST"])
@admin_required
def admin_subscriber_resend():
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        flash("Email required.")
        return redirect(url_for("admin.admin_subscribers"))
    try:
        subj, html, text = mailer.welcome_email(email)
        sent = mailer.send_email(email, subj, html, text)
        flash(f"Welcome email {'sent to' if sent else 'queued (SMTP disabled) for'} {email}.")
    except Exception as e:
        flash(f"Resend failed: {e}")
    return redirect(url_for("admin.admin_subscribers"))


@bp.route("/admin/jobs.json")
@admin_required
def admin_jobs():
    with jobs.JOBS_LOCK:
        return jsonify(jobs.JOBS)


# ---------- Media editing ----------

@bp.route("/admin/story/<sid>/edit-photo", methods=["POST"])
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
                    (config.IMAGES / f"{slug}.jpg").write_bytes(resp.content)
                    new_url = f"/media/{slug}.jpg?v={int(_t.time())}"
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
    return redirect(request.referrer or url_for("admin.admin_review", sid=sid))


@bp.route("/admin/research/<slug>/edit-photo", methods=["POST"])
@admin_required
def admin_edit_dossier_photo(slug):
    """Replace photo on a saved dossier."""
    path = config.DOSSIERS / f"{slug}.json"
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
                    (config.IMAGES / f"{slug}.jpg").write_bytes(resp.content)
                    new_url = f"/media/{slug}.jpg?v={int(_t.time())}"
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
    return redirect(url_for("admin.admin_research_view", slug=slug))
