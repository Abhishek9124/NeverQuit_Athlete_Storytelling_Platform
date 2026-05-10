"""WSGI entry point for Gunicorn / Waitress / cloud platforms."""
from scripts.dashboard.app import app

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
