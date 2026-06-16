"""JSON APIs: newsletter, story search/feed, single-story payload, submissions."""
from __future__ import annotations
import os
import re
import json as _json
import time as _time
import threading
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

from scripts.utils import storage, db
from scripts.dashboard import config
from scripts.dashboard.seed_stories import SEED_STORIES
from scripts.dashboard.helpers import _card, _all_published_cards

log = logging.getLogger("neverquit.app")
bp = Blueprint("api", __name__)


@bp.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    email = (request.form.get("email") or request.json and request.json.get("email") or "").strip().lower()
    source = (request.form.get("source") or "home_pill").strip()
    if not email or "@" not in email or len(email) > 200:
        return jsonify({"ok": False, "error": "Invalid email"}), 400
    ok = db.add_subscriber(email, source)
    if ok:
        from scripts.utils import mailer

        def _send_welcome():
            try:
                subj, html, text = mailer.welcome_email(email)
                if mailer.send_email(email, subj, html, text):
                    log.info("Welcome email sent to %s", email)
            except Exception as e:
                log.warning("Welcome email failed for %s: %s", email, e)

        threading.Thread(target=_send_welcome, daemon=True).start()
    return jsonify({"ok": ok, "count": db.count_subscribers(), "welcome_sent": bool(os.getenv("SMTP_HOST"))})


@bp.route("/api/unsubscribe")
def api_unsubscribe():
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return "Missing email", 400
    db.remove_subscriber(email)
    return f"<p style='font-family:system-ui;padding:48px;text-align:center;'>Unsubscribed <strong>{email}</strong>. We're sorry to see you go.</p>"


@bp.route("/api/stories.json")
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

    if sort == "name":
        cards = sorted(cards, key=lambda c: (c.get("athlete_name") or "").lower())
    elif sort == "confidence":
        cards = sorted(cards, key=lambda c: c.get("confidence_score") or 0, reverse=True)
    elif sort == "newest":
        cards = list(reversed(cards))

    total = len(cards)
    page = cards[offset: offset + limit]
    return jsonify({
        "total": total, "offset": offset, "limit": limit,
        "results": page, "has_more": (offset + limit) < total,
    })


@bp.route("/api/story/<sid>.json")
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


@bp.route("/api/submit", methods=["POST"])
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
        "submitted_at": datetime.utcnow().isoformat(),
    }
    (config.SUBMISSIONS / f"{slug}-{int(_time.time())}.json").write_text(
        _json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return jsonify({"ok": True})
