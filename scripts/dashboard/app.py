"""NeverQuit web app entry point.

The implementation now lives in an application factory + blueprints:
  scripts/dashboard/__init__.py   create_app() factory
  scripts/dashboard/config.py     configuration & constants
  scripts/dashboard/helpers.py    auth, cards, URLs, visibility, uploads
  scripts/dashboard/jobs.py       background pipeline job runner
  scripts/dashboard/views/        public · api · admin blueprints

This module just exposes `app` so existing entry points (wsgi.py,
`waitress-serve wsgi:app`) keep working unchanged.
"""
from __future__ import annotations
import os

from scripts.dashboard import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG") == "1")
