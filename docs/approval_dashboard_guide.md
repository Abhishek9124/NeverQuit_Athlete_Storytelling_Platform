# Approval Dashboard Guide

## Run locally
```bash
pip install -r requirements.txt
python -m scripts.dashboard.app
```
Open http://localhost:5000.

## Deploy on Replit
1. Import this repo into Replit.
2. Set Secrets from `.env.example`.
3. Run command: `python -m scripts.dashboard.app`.
4. Public URL = your dashboard.

## Approving a story (your daily 2-10 min job)

1. Open dashboard, click a pending story.
2. Read the English version. If you read regional languages, switch tabs to spot-check.
3. Look at the confidence score:
   - **≥90% with low/medium flags** → approve (2 min).
   - **75-89%** → check flagged facts on Wikipedia or the federation site, then approve.
   - **<75%** → reject. Pipeline auto-rejects these too.
4. Click **Approve & publish everywhere**. Publishing happens in ~30 seconds.

## Re-queueing a rejected athlete

Edit `data/athlete_queue.json` — move the entry from `rejected` back to `queue`.
