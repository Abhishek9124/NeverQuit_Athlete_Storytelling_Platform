# NeverQuit

NeverQuit is an AI-assisted storytelling platform for publishing inspiring athlete comeback stories. It combines a research and writing pipeline with a Flask-based admin dashboard so stories can be researched, drafted, reviewed, approved, and published from one project.

The current codebase is built around athlete and Paralympian profiles, with a strong focus on resilience narratives, factual research, editorial review, and multi-channel publishing.

## What This Project Does

- Discovers new athlete story candidates and queues them for processing
- Builds structured research dossiers with sources, quotes, and image metadata
- Writes long-form story drafts from those dossiers
- Runs QA and confidence scoring before human review
- Provides an admin console for research, review, approval, rejection, and reruns
- Publishes approved stories to external platforms such as Webflow, Mailchimp, Notion, and Supabase
- Serves a public-facing site for browsing published stories

## How It Works

The pipeline in this repo follows this flow:

`discovery -> research -> write -> QA -> human approval -> publish -> social assets`

Main stages:

1. `discovery_agent` finds athlete candidates and stores them in `data/athlete_queue.json`.
2. `research_agent` builds a dossier in `data/dossiers/` and mirrors it to SQLite.
3. `story_writer_agent` turns the dossier into structured story sections.
4. `quality_checker_agent` scores confidence and flags uncertain claims.
5. The dashboard places stories into `pending_review`, `approved`, `rejected`, or `published`.
6. `publishing_agent` pushes approved stories to connected services.

## Tech Stack

- Python
- Flask
- SQLite plus JSON file storage
- NVIDIA OpenAI-compatible API for research and story generation
- Optional integrations: Supabase, Webflow, Mailchimp, Notion
- Waitress / Gunicorn for deployment

## Project Structure

```text
.
|-- scripts/
|   |-- dashboard/          # Flask app, templates, admin/public views
|   |-- pipeline/           # Discovery, research, writing, QA, publishing
|   `-- utils/              # Storage, DB, API clients, helpers
|-- data/
|   |-- dossiers/           # Research dossiers
|   |-- stories/            # Generated story JSON files
|   |-- images/             # Downloaded or uploaded athlete images
|   |-- athlete_queue.json  # Candidate queue
|   `-- neverquit.sqlite    # Local database
|-- prompts/                # Prompt templates used by agents
|-- docs/                   # Deployment and architecture notes
|-- site/                   # Static assets for the public site
|-- wsgi.py                 # Production entrypoint
`-- requirements.txt
```

## Local Development

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create environment file

```bash
cp .env.example .env
```

At minimum, set:

- `NVIDIA_API_KEY`
- `ADMIN_TOKEN`
- `FLASK_SECRET`

Recommended model defaults from this repo:

- `NVIDIA_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- `NVIDIA_STORY_MODEL=openai/gpt-oss-20b`

### 3. Run the app

For development:

```bash
python wsgi.py
```

For production-style local runs:

```bash
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```

Then open:

- Public site: `http://localhost:5000`
- Admin dashboard: `http://localhost:5000/admin`

If `ADMIN_TOKEN` is set, use it to sign in.

## Running the Pipeline

Run a single athlete:

```bash
python scripts/pipeline/run_pipeline.py --athlete "Neeraj Chopra" --sport "Javelin"
```

Run the daily queue:

```bash
python scripts/pipeline/run_pipeline.py --quota 1
```

Dry run without auto-publishing:

```bash
python scripts/pipeline/run_pipeline.py --quota 1 --dry-run
```

## Admin Dashboard

The Flask app in `scripts/dashboard/app.py` provides:

- Public homepage and story pages
- Admin login
- Approval queue
- Research-only dossier generation
- Story review and publishing actions
- Background job progress tracking
- Photo replacement for dossiers and stories

Important routes:

- `/`
- `/story/<id>`
- `/admin`
- `/admin/run-discovery`
- `/admin/run-pipeline`
- `/admin/research`
- `/healthz`

## Data Storage

This project uses a hybrid local storage model:

- JSON files are written to `data/stories/` and `data/dossiers/`
- SQLite lives at `data/neverquit.sqlite`
- Queue state lives in `data/athlete_queue.json`

The JSON files are human-readable backups, while SQLite is used for query-friendly persistence.

## Environment Variables

### Core

- `NVIDIA_API_KEY`
- `NVIDIA_MODEL`
- `NVIDIA_STORY_MODEL`
- `ADMIN_TOKEN`
- `FLASK_SECRET`
- `PORT`

### Optional publishing/integration keys

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `WEBFLOW_API_KEY`
- `WEBFLOW_COLLECTION_ID`
- `WEBFLOW_SITE_ID`
- `MAILCHIMP_API_KEY`
- `MAILCHIMP_AUDIENCE_ID`
- `MAILCHIMP_SERVER_PREFIX`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

### Pipeline tuning

- `DAILY_STORY_QUOTA`
- `MIN_CONFIDENCE_SCORE`
- `AUTO_APPROVE_THRESHOLD`
- `NVIDIA_MIN_INTERVAL_S`
- `NVIDIA_MAX_CONCURRENT`

## Deployment

This repo already includes deployment assets:

- `Dockerfile`
- `Procfile`
- `render.yaml`
- `wsgi.py`

The app is designed to run as a single Flask service serving both the public site and the admin console.

## Current Repository State

The repo already contains:

- Sample dossiers and stories under `data/`
- A working Flask dashboard
- Prompt files for research, writing, QA, and social assets
- Deployment notes in `docs/`

That makes it suitable both as a working prototype and as a base for expanding into a fuller editorial publishing system.

## Useful Docs

- `docs/pipeline_architecture.md`
- `docs/deployment.md`
- `docs/approval_dashboard_guide.md`
- `docs/database_choice.md`

## Notes

- Translation is present in the code structure, but the current orchestrator is effectively English-only.
- Publishing integrations are best-effort and do not block other publishing targets if one fails.
- If `ADMIN_TOKEN` is empty, the admin interface is effectively open in local development mode.
