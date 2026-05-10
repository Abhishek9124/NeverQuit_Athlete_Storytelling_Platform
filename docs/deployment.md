# Deployment

The web app is a single Flask process that serves both the **public site** and the **admin console** (gated by `ADMIN_TOKEN`).

## Run locally (production-style)

```bash
pip install -r requirements.txt
cp .env.example .env  # set GOOGLE_API_KEY + ADMIN_TOKEN

# Linux / macOS
gunicorn wsgi:app --bind 0.0.0.0:5000 --workers 2 --threads 4 --timeout 600

# Windows
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```

Then visit:
- Public: http://localhost:5000
- Admin: http://localhost:5000/admin (sign in with `ADMIN_TOKEN`)

## Deploy to Render.com

1. Push this repo to GitHub.
2. New → Blueprint → point at the repo. Render reads `render.yaml`.
3. In the dashboard, set `GOOGLE_API_KEY` (sync:false in YAML).
4. `ADMIN_TOKEN` and `FLASK_SECRET` are auto-generated.
5. The persistent disk at `/app/data` keeps stories across deploys.

## Deploy to Fly.io

```bash
fly launch                    # detects the Dockerfile
fly secrets set GOOGLE_API_KEY=... ADMIN_TOKEN=... FLASK_SECRET=...
fly volumes create neverquit_data --size 1
# add to fly.toml: [[mounts]] source="neverquit_data" destination="/app/data"
fly deploy
```

## Deploy to Railway

```bash
railway init
railway up
railway variables set GOOGLE_API_KEY=... ADMIN_TOKEN=... FLASK_SECRET=...
```

## Deploy with Docker

```bash
docker build -t neverquit .
docker run -p 5000:5000 \
  -e GOOGLE_API_KEY=... \
  -e ADMIN_TOKEN=... \
  -e FLASK_SECRET=... \
  -v $(pwd)/data:/app/data \
  neverquit
```

## Daily cron (post-deploy)

Hit the admin endpoint from a cron service (Render Cron, GitHub Actions, EasyCron):

```
curl -X POST https://YOUR-DOMAIN/admin/run-pipeline \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d "quota=1"
```

## Production checklist

- [ ] Strong `ADMIN_TOKEN` (32+ random chars)
- [ ] Strong `FLASK_SECRET`
- [ ] HTTPS only (Render/Fly/Railway provide this automatically)
- [ ] Persistent volume mounted at `/app/data`
- [ ] Daily cron pinging `/admin/run-pipeline`
- [ ] Webflow + Mailchimp + Notion + Supabase keys set if you want auto-publishing
