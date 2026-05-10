"""SQLite store for stories, dossiers, and queue.

Lives at data/neverquit.sqlite. JSON files in data/stories/ are still written
as a human-readable backup. The DB is the source of truth for queries.
"""
from __future__ import annotations
import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "neverquit.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
  story_id        TEXT PRIMARY KEY,
  athlete_name    TEXT NOT NULL,
  sport           TEXT,
  country         TEXT,
  status          TEXT,                -- pending_review | approved | rejected | published
  confidence      INTEGER DEFAULT 0,
  hook            TEXT,
  pull_quote      TEXT,
  image_url       TEXT,                -- /media/<slug>.jpg if we have one
  payload_json    TEXT NOT NULL,       -- full sections + qa + dossier + social
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS stories_status_idx ON stories(status);
CREATE INDEX IF NOT EXISTS stories_sport_idx  ON stories(sport);

CREATE TABLE IF NOT EXISTS dossiers (
  slug         TEXT PRIMARY KEY,
  athlete_name TEXT NOT NULL,
  sport        TEXT,
  country      TEXT,
  image_url    TEXT,
  payload_json TEXT NOT NULL,
  created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue (
  athlete_name TEXT PRIMARY KEY,
  sport        TEXT,
  country      TEXT,
  why_now      TEXT,
  state        TEXT NOT NULL,    -- queued | processed | rejected
  added_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscribers (
  email          TEXT PRIMARY KEY COLLATE NOCASE,
  source         TEXT,           -- home_pill | story | manual
  created_at     TEXT NOT NULL,
  unsubscribed   INTEGER DEFAULT 0,
  last_emailed_at TEXT
);

CREATE TABLE IF NOT EXISTS visits (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  path        TEXT NOT NULL,
  story_id    TEXT,
  ip_hash     TEXT,
  user_agent  TEXT,
  ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS visits_path_idx     ON visits(path);
CREATE INDEX IF NOT EXISTS visits_story_id_idx ON visits(story_id);
CREATE INDEX IF NOT EXISTS visits_ts_idx       ON visits(ts);

CREATE TABLE IF NOT EXISTS broadcasts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  subject     TEXT NOT NULL,
  body        TEXT NOT NULL,
  sent_to     INTEGER DEFAULT 0,
  failures    INTEGER DEFAULT 0,
  created_at  TEXT NOT NULL
);
"""


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


# ---------- Stories ----------

def upsert_story(s: dict) -> None:
    now = datetime.utcnow().isoformat()
    sections = s.get("sections") or {}
    with conn() as c:
        c.execute(
            """INSERT INTO stories(story_id, athlete_name, sport, country, status,
                                   confidence, hook, pull_quote, image_url, payload_json,
                                   created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(story_id) DO UPDATE SET
                 athlete_name=excluded.athlete_name,
                 sport=excluded.sport, country=excluded.country, status=excluded.status,
                 confidence=excluded.confidence, hook=excluded.hook,
                 pull_quote=excluded.pull_quote, image_url=excluded.image_url,
                 payload_json=excluded.payload_json, updated_at=excluded.updated_at""",
            (
                s["story_id"], s["athlete_name"], s.get("sport", ""), s.get("country", ""),
                s.get("status", "pending_review"), int(s.get("confidence_score", 0) or 0),
                sections.get("hook", ""), sections.get("pull_quote", ""),
                s.get("image_url", ""), json.dumps(s, ensure_ascii=False), now, now,
            ),
        )


def get_story(story_id: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT payload_json FROM stories WHERE story_id=?", (story_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None


def update_story_status(story_id: str, status: str, **extra) -> None:
    s = get_story(story_id)
    if not s:
        return
    s["status"] = status
    s.update(extra)
    upsert_story(s)


def list_stories(status: str | None = None, limit: int = 200) -> list[dict]:
    sql = "SELECT payload_json FROM stories"
    args: tuple = ()
    if status:
        sql += " WHERE status=?"
        args = (status,)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    args = args + (limit,)
    with conn() as c:
        return [json.loads(r["payload_json"]) for r in c.execute(sql, args).fetchall()]


# ---------- Dossiers ----------

def upsert_dossier(slug: str, dossier: dict) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO dossiers(slug, athlete_name, sport, country, image_url,
                                    payload_json, created_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET
                 athlete_name=excluded.athlete_name, sport=excluded.sport,
                 country=excluded.country, image_url=excluded.image_url,
                 payload_json=excluded.payload_json""",
            (slug, dossier.get("athlete_name", slug), dossier.get("sport", ""),
             dossier.get("country", ""), dossier.get("image_url", ""),
             json.dumps(dossier, ensure_ascii=False), datetime.utcnow().isoformat()),
        )


def get_dossier(slug: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT payload_json FROM dossiers WHERE slug=?", (slug,)).fetchone()
        return json.loads(row["payload_json"]) if row else None


def list_dossiers() -> list[dict]:
    with conn() as c:
        return [
            {"slug": r["slug"], "name": r["athlete_name"], "sport": r["sport"],
             "country": r["country"], "image_url": r["image_url"]}
            for r in c.execute(
                "SELECT slug,athlete_name,sport,country,image_url FROM dossiers ORDER BY created_at DESC"
            ).fetchall()
        ]


def delete_dossier(slug: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM dossiers WHERE slug=?", (slug,))


# ---------- Subscribers ----------

def add_subscriber(email: str, source: str = "home_pill") -> bool:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return False
    with conn() as c:
        c.execute(
            """INSERT INTO subscribers(email, source, created_at) VALUES(?,?,?)
               ON CONFLICT(email) DO UPDATE SET source=excluded.source, unsubscribed=0""",
            (email, source, datetime.utcnow().isoformat()),
        )
    return True


def list_subscribers(active_only: bool = True) -> list[dict]:
    sql = "SELECT email, source, created_at, unsubscribed, last_emailed_at FROM subscribers"
    if active_only:
        sql += " WHERE unsubscribed=0"
    sql += " ORDER BY created_at DESC"
    with conn() as c:
        return [dict(r) for r in c.execute(sql).fetchall()]


def remove_subscriber(email: str) -> None:
    with conn() as c:
        c.execute("UPDATE subscribers SET unsubscribed=1 WHERE email=?", ((email or "").lower(),))


def count_subscribers() -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM subscribers WHERE unsubscribed=0").fetchone()["n"]


# ---------- Visits ----------

def log_visit(path: str, story_id: str | None, ip_hash: str | None, ua: str | None) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO visits(path, story_id, ip_hash, user_agent, ts) VALUES(?,?,?,?,?)",
            (path, story_id, ip_hash, (ua or "")[:300], datetime.utcnow().isoformat()),
        )


def total_visits() -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM visits").fetchone()["n"]


def visits_today() -> int:
    today = datetime.utcnow().date().isoformat()
    with conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM visits WHERE ts >= ?", (today,)).fetchone()["n"]


def unique_visitors() -> int:
    with conn() as c:
        return c.execute(
            "SELECT COUNT(DISTINCT ip_hash) AS n FROM visits WHERE ip_hash IS NOT NULL"
        ).fetchone()["n"]


def top_stories(limit: int = 10) -> list[dict]:
    with conn() as c:
        return [
            {"story_id": r["story_id"], "views": r["n"]}
            for r in c.execute(
                "SELECT story_id, COUNT(*) AS n FROM visits "
                "WHERE story_id IS NOT NULL AND story_id != '' "
                "GROUP BY story_id ORDER BY n DESC LIMIT ?", (limit,),
            ).fetchall()
        ]


# ---------- Broadcasts ----------

def log_broadcast(subject: str, body: str, sent_to: int, failures: int) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO broadcasts(subject, body, sent_to, failures, created_at) VALUES(?,?,?,?,?)",
            (subject, body, sent_to, failures, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def list_broadcasts(limit: int = 20) -> list[dict]:
    with conn() as c:
        return [
            dict(r) for r in c.execute(
                "SELECT id, subject, sent_to, failures, created_at FROM broadcasts "
                "ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        ]


def backfill_from_json() -> tuple[int, int]:
    """Import any pre-existing JSON files into SQLite. Idempotent."""
    n_stories = n_dossiers = 0
    stories_dir = ROOT / "data" / "stories"
    dossiers_dir = ROOT / "data" / "dossiers"
    if stories_dir.exists():
        for p in stories_dir.glob("*.json"):
            try:
                upsert_story(json.loads(p.read_text(encoding="utf-8")))
                n_stories += 1
            except Exception:
                pass
    if dossiers_dir.exists():
        for p in dossiers_dir.glob("*.json"):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, list):
                    d = d[0] if (d and isinstance(d[0], dict)) else None
                if isinstance(d, dict):
                    upsert_dossier(p.stem, d)
                    n_dossiers += 1
            except Exception:
                pass
    return n_stories, n_dossiers


# Initialize on import.
init()
backfill_from_json()
