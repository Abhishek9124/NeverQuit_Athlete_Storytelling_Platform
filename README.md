# NeverQuit — AI-Assisted Athlete Storytelling Platform

> An end-to-end content platform that **researches, writes, fact-checks, and publishes**
> long-form comeback stories of athletes, Paralympians, and differently-abled
> individuals — with a human editor in the loop at every step.

NeverQuit pairs a **multi-agent AI pipeline** with a **production Flask web app**.
The pipeline turns a single athlete name into a sourced research dossier and a
structured, editorially-reviewed story. The web app serves both a polished public
reader and a full admin console for review, approval, per-section visibility
control, and multi-channel publishing.

---

## Why this project is worth a look

| Area | What it demonstrates |
|---|---|
| **Multi-agent orchestration** | 6 specialised agents (discover → research → write → QA → publish → social) with isolated prompts, retries, and graceful degradation |
| **LLM engineering** | Provider-agnostic client, tolerant JSON parsing, exponential-backoff retries, rate-limit handling, optional MCP tool-use |
| **Human-in-the-loop design** | Confidence scoring, red-flag surfacing, per-section public-visibility controls, bulk review actions |
| **Full-stack delivery** | Flask app, SQLite persistence with an in-memory cache layer, gzip middleware, background job runner, SMTP + Mailchimp integration |
| **Production readiness** | Dockerfile, `render.yaml`, `Procfile`, WSGI entrypoint, health check, env-driven config, optional-dependency soft imports |

---

## Architecture

```
              ┌───────────────────────── AI PIPELINE ─────────────────────────┐
              │                                                               │
  athlete  →  │  discovery → research → story writer → quality checker        │
   name       │     │           │            │               │               │
              │     ▼           ▼            ▼               ▼               │
              │  queue.json   dossier      sections     confidence + flags    │
              │              (SQLite +    (10-section                        │
              │               JSON)        template)                         │
              └───────────────────────────────┬───────────────────────────────┘
                                              │
                              ┌───────────────▼───────────────┐
                              │       FLASK WEB APP            │
                              │                                │
   public reader  ◄───────────┤  /             public home     │
   (cards, search,            │  /story/<id>   story reader     │
    bookmarks, submit)        │  /saved        reading list     │
                              │  /submit       athlete suggest  │
                              │                                │
   admin console  ◄───────────┤  /admin        review+pipeline  │
   (review, approve,          │  /admin/...    subscribers, bulk│
    bulk actions,             │                actions, jobs   │
    visibility control)       └───────────────┬────────────────┘
                                              │
                          ┌───────────────────▼────────────────────┐
                          │  PUBLISHING (opt-in via env keys)       │
                          │  Webflow · Mailchimp · Notion · Supabase│
                          └─────────────────────────────────────────┘
```

**Pipeline flow:** `discovery → research → write → QA → human approval → publish → social assets`

1. **`discovery_agent`** finds athlete candidates and queues them in `data/athlete_queue.json`.
2. **`research_agent`** builds a sourced dossier (birth, struggles, turning point, quotes, competitions, outcomes) — mirrored to SQLite, with optional MCP tool-use enrichment.
3. **`story_writer_agent`** turns the dossier into a structured 10+ section story.
4. **`quality_checker_agent`** scores editorial confidence and flags unverified claims.
5. The **admin console** moves stories through `pending_review → approved / rejected → published`.
6. **`publishing_agent`** pushes approved stories to connected services (all opt-in, best-effort, non-blocking).

---

## Key Features

### AI pipeline
- **Provider-agnostic LLM client** (`nvidia_client.py`) over an OpenAI-compatible API, with legacy aliases so older imports keep working
- **Tolerant JSON parsing** — strips markdown fences, repairs malformed model output, retries on rate limits with exponential backoff
- **Per-agent prompt files** in `prompts/` — research, story writing, QA, and social assets are independently tunable
- **Optional MCP integration** (`mcp_research.py`) for Model Context Protocol tool-use during research
- **Independently configurable models** — research and story-writing models set via separate env vars

### Admin console
- **Review queue** with confidence scores, QA red flags, and uncertain-fact surfacing
- **Bulk actions** — approve / reject / unpublish many stories at once
- **Per-section public visibility** — hide any of 21 story sections from the public reader without deleting content; one-click presets (Show all / Story only / Minimal)
- **Inline metadata editing** — fix athlete name, sport, country without re-running the pipeline
- **Live job runner** — background pipeline jobs with real-time progress, step tracking, and auto-refresh
- **Research dossier viewer** with field-coverage scoring and re-research using a different model
- **Subscriber management** — add, export CSV, resend welcome emails, broadcast updates

### Public site
- Responsive home with **live search**, sport filters, and lazy-loaded story cards
- Distraction-free **story reader** — reading-progress bar, real reading-time estimate, country flags, bookmark/save, highlight-to-share
- **`/saved`** — a personal reading list (localStorage, no login required)
- **`/submit`** — community submission form for suggesting athletes
- **Newsletter capture** — floating pill, inline CTA, dark-mode toggle

### Engineering
- **SQLite persistence** with an mtime-keyed in-memory cache layer for `list_stories()`
- **gzip middleware** — compresses HTML/JSON responses ~70%
- **Aggressive media caching** — athlete photos served with 30-day immutable cache headers
- **Visit analytics** — privacy-respecting (hashed IP) page-view tracking
- **SMTP mailer** — HTML welcome emails and admin broadcasts
- **Graceful degradation** — optional integrations (Notion, Supabase, MCP) soft-import and no-op when unconfigured

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| Web framework | Flask |
| Persistence | SQLite (+ human-readable JSON backups), optional Supabase |
| LLM | OpenAI-compatible API (NVIDIA-hosted models) |
| Email | SMTP + optional Mailchimp |
| Publishing | Webflow, Notion (all optional) |
| Serving | Waitress / Gunicorn |
| Deploy | Docker, Render, Fly, Railway, or any WSGI host |

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/Abhishek9124/NeverQuit-AI-Assisted-Athlete-Storytelling-Platform.git
cd NeverQuit-AI-Assisted-Athlete-Storytelling-Platform

# 2. Virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Install core dependencies
pip install flask python-dotenv openai requests tenacity json-repair Pillow waitress

# 4. Configure environment
cp .env.example .env           # then edit — see below

# 5. Run
python wsgi.py                 # development
# waitress-serve --listen=0.0.0.0:5000 wsgi:app   # production-style
```

Open **http://localhost:5000** (public site) and **http://localhost:5000/admin** (console).

### Minimum `.env`

```ini
NVIDIA_API_KEY=your-key-here
NVIDIA_STORY_MODEL=openai/gpt-oss-20b
NVIDIA_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
ADMIN_TOKEN=choose-a-secret     # leave blank for open dev mode
FLASK_SECRET=any-random-string
```

Everything else in `.env.example` (SMTP, Mailchimp, Webflow, Notion, Supabase) is
**optional** — the app boots and runs without any of it.

---

## Running the Pipeline

```bash
# Full end-to-end run for one athlete
python scripts/pipeline/run_pipeline.py --athlete "Neeraj Chopra" --sport "Javelin"

# Process the daily queue
python scripts/pipeline/run_pipeline.py --quota 1

# Dry run — generate without auto-publishing
python scripts/pipeline/run_pipeline.py --quota 1 --dry-run
```

Or drive it from the admin console: **`/admin` → Research → enter a name → Write story → Review → Approve**.
Stories land in `data/stories/` as JSON and mirror to `data/neverquit.sqlite`.

---

## Project Structure

```
scripts/
├── dashboard/
│   ├── app.py              # Flask app — routes, admin console, job runner
│   ├── seed_stories.py     # demo stories shown before the DB is populated
│   └── templates/          # Jinja2 templates (public + admin)
├── pipeline/
│   ├── discovery_agent.py        # finds athlete candidates
│   ├── research_agent.py         # builds sourced dossiers
│   ├── story_writer_agent.py     # dossier → structured story
│   ├── quality_checker_agent.py  # confidence scoring + fact flags
│   ├── publishing_agent.py       # pushes to external services
│   ├── social_asset_generator.py
│   └── run_pipeline.py           # end-to-end orchestrator
└── utils/
    ├── nvidia_client.py    # provider-agnostic LLM client
    ├── db.py               # SQLite layer
    ├── storage.py          # JSON store + mtime-keyed cache
    ├── mailer.py           # SMTP welcome emails + broadcasts
    ├── image_fetcher.py    # athlete photo lookup
    ├── country_flags.py    # ISO code + flag helpers
    └── mcp_research.py     # optional MCP tool-use
prompts/                    # per-agent prompt files
templates/story_template.json
docs/                       # architecture, deployment, DB-choice notes
data/                       # SQLite DB, story JSON, images (gitignored)
```

### Important routes

| Route | Purpose |
|---|---|
| `/` | Public home — search, filters, story cards |
| `/story/<id>` | Story reader |
| `/saved` · `/submit` | Reading list · community submission form |
| `/admin` | Admin console — review queue, pipeline tools, live jobs |
| `/admin/run-research` · `/admin/run-pipeline` | Trigger pipeline stages |
| `/admin/subscribers` | Newsletter management + broadcasts |
| `/healthz` | Health check |

---

## Data Storage

A hybrid local model:

- **JSON files** in `data/stories/` and `data/dossiers/` — human-readable backups, source of truth for the cache
- **SQLite** at `data/neverquit.sqlite` — query-friendly persistence, mirrored on every write
- **Queue state** in `data/athlete_queue.json`

Rationale for SQLite over a hosted DB is documented in `docs/database_choice.md`.

---

## Environment Variables

**Core** — `NVIDIA_API_KEY`, `NVIDIA_MODEL`, `NVIDIA_STORY_MODEL`, `ADMIN_TOKEN`, `FLASK_SECRET`, `PORT`

**Pipeline tuning** — `DAILY_STORY_QUOTA`, `MIN_CONFIDENCE_SCORE`, `AUTO_APPROVE_THRESHOLD`, `NVIDIA_MIN_INTERVAL_S`, `NVIDIA_MAX_CONCURRENT`

**Optional integrations** — `SMTP_*`, `MAILCHIMP_*`, `WEBFLOW_*`, `NOTION_*`, `SUPABASE_*`

See `.env.example` for the full annotated list.

---

## Deployment

The repo ships with `Dockerfile`, `render.yaml`, `Procfile`, and `wsgi.py`.

```bash
# Docker
docker build -t neverquit .
docker run -p 5000:5000 --env-file .env neverquit

# Any WSGI host
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```

The app runs as a **single Flask service** serving both the public site and the admin console. See `docs/deployment.md` for platform-specific notes.

---

## Design Decisions & Trade-offs

- **SQLite over Postgres** — single-file persistence keeps the project portable and zero-config; the `db.py` layer is thin enough to swap later.
- **JSON + SQLite dual write** — JSON files are human-readable backups; SQLite powers fast queries.
- **Human-in-the-loop by default** — no story auto-publishes. Confidence scores and red flags *inform* the editor; they don't replace them.
- **Optional integrations soft-import** — the app never crashes because Notion or Supabase isn't installed; missing services simply no-op.
- **Provider-agnostic LLM layer** — swapping models or providers is an env-var change, not a code change.
- **Best-effort publishing** — if one publishing target fails, the others still run.

---

## Docs

- `docs/pipeline_architecture.md` — agent flow in detail
- `docs/deployment.md` — platform-specific deploy notes
- `docs/approval_dashboard_guide.md` — admin console walkthrough
- `docs/database_choice.md` — why SQLite

---

## Notes

- Translation scaffolding exists in the codebase, but the current orchestrator is effectively English-only.
- If `ADMIN_TOKEN` is empty, the admin interface is open in local development mode.

---

## License

This project is for portfolio and educational purposes.
