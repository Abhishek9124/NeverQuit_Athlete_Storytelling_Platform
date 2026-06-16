"""NeverQuit web app — application factory.

`create_app()` builds the Flask app, registers context processors and
request hooks, and mounts the public / api / admin blueprints. Blueprint
imports are deferred into the function to keep package import side-effect free.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Ensure the project root is importable under any launcher (waitress, gunicorn…).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def create_app():
    import gzip
    import hashlib
    import logging

    from flask import Flask, request
    from scripts.utils import db, country_flags, model_config
    from scripts.dashboard import config
    from scripts.dashboard.helpers import is_visible
    from scripts.dashboard.views.public import bp as public_bp
    from scripts.dashboard.views.api import bp as api_bp
    from scripts.dashboard.views.admin import bp as admin_bp

    log = logging.getLogger("neverquit.app")

    app = Flask(__name__, static_folder=str(config.SITE_DIR), static_url_path="/static")
    app.secret_key = config.FLASK_SECRET

    # ── Template context ──
    @app.context_processor
    def _inject_globals():
        default_model = model_config.default_research_key()
        story_model = model_config.model_for("story")
        return {
            "model_name": story_model,            # legacy: shown as the active model
            "story_model": story_model,           # explicit story-only label
            "research_model": config.RESEARCH_MODELS[default_model]["model"],
            "research_models": config.RESEARCH_MODELS,
            "is_nvidia_research": True,
            "flag": country_flags.flag_emoji,
            "country_iso": country_flags.iso_code,
            "max_tokens": 20000,
        }

    @app.context_processor
    def _inject_visibility():
        return {"vis": is_visible, "SECTION_KEYS": config.SECTION_KEYS}

    # ── Request hooks ──
    @app.before_request
    def _log_request_visit():
        p = request.path or ""
        if (p.startswith("/media") or p.startswith("/static") or
            p.startswith("/admin") or p.startswith("/api") or
            p in ("/healthz", "/favicon.ico", "/feed.xml", "/rss",
                  "/sitemap.xml", "/robots.txt")):
            return
        try:
            ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                  or request.remote_addr or "")
            ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:24] if ip else ""
            story_id = ""
            if p.startswith("/story/"):
                story_id = p.split("/story/", 1)[1].split("/")[0]
            db.log_visit(p, story_id or None, ip_hash, request.headers.get("User-Agent", ""))
        except Exception:
            pass

    @app.after_request
    def _maybe_gzip(resp):
        """Lightweight gzip for text/JSON responses."""
        try:
            if (resp.status_code < 200 or resp.status_code >= 300
                    or "Content-Encoding" in resp.headers
                    or resp.direct_passthrough):
                return resp
            if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
                return resp
            ct = (resp.headers.get("Content-Type") or "").lower()
            if not any(ct.startswith(x) for x in ("text/", "application/json", "application/javascript", "application/xml")):
                return resp
            data = resp.get_data()
            if len(data) < 1024:  # not worth compressing tiny payloads
                return resp
            gzipped = gzip.compress(data, compresslevel=6)
            resp.set_data(gzipped)
            resp.headers["Content-Encoding"] = "gzip"
            resp.headers["Content-Length"] = str(len(gzipped))
            resp.headers["Vary"] = "Accept-Encoding"
        except Exception:
            pass
        return resp

    # ── Blueprints ──
    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    return app
