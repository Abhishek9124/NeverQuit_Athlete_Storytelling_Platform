# GoAhead.md — NeverQuit Launch Checklist

> A concrete, copy-pasteable runbook to take this scaffold from zero to a live, revenue-bearing product.

---

## 0. What was just built

A production-ready scaffold of the NeverQuit pipeline lives in this folder:

```
NeverQuit/
├── scripts/
│   ├── pipeline/         # 8 agents (discovery → research → write → translate → QA → publish → social)
│   ├── dashboard/        # Flask owner-approval UI with 8 language tabs
│   └── utils/            # Claude, Notion, Webflow, Mailchimp, Supabase clients + storage
├── prompts/              # All 5 agent prompts (research, writer, translator, QA, social)
├── templates/            # 10-section story template schema
├── data/                 # Athlete queue + sports list seed
├── docs/                 # Pipeline architecture, dashboard guide, revenue playbook
├── make_blueprints/      # Make.com daily-cron scenario
├── requirements.txt
├── .env.example
└── GoAhead.md            # This file
```

Every agent is independently runnable with `--dry-run`. The orchestrator `run_pipeline.py` chains them all.

---

## 1. Day 1 — Get keys, run dry pipeline (≈ 2 hours)

```bash
cd NeverQuit
python -m venv .venv && source .venv/Scripts/activate   # or .venv\Scripts\activate on Windows cmd
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` — at minimum set `ANTHROPIC_API_KEY`. Everything else can stay blank for the dry run.

```bash
# Dry-run on a known athlete
python -m scripts.pipeline.run_pipeline --athlete "Sheetal Devi" --sport "Para Archery" --dry-run
```

Confirm `data/stories/sheetal-devi-*.json` exists with `sections`, `qa`, `confidence_score` populated.

Open the dashboard:
```bash
python -m scripts.dashboard.app
```
Visit http://localhost:5000 — story should appear in "Pending review".

---

## 2. Week 1 — Wire the publishing platforms

In order of priority (each unblocks the next):

1. **GoDaddy** — register `neverquit.in` (₹800).
2. **Notion** — create a database with columns: Name (title), Sport (text), Status (select: draft/approved/published), Confidence (number), Hook (text), URL (url). Copy `NOTION_DATABASE_ID` and integration token into `.env`.
3. **Webflow** — build the site (use Webflow University 2-hr course). Create a CMS collection `stories` with fields: name, slug, sport, hook, body-en, body-hi, body-ta, body-kn, body-mr, body-bn, body-te, body-gu, confidence. Copy IDs into `.env`.
4. **Mailchimp** — create an audience, copy API key + audience ID + server prefix into `.env`.
5. **Supabase** — create a project. Run the SQL in the README's "Supabase Vector Search" section.

Smoke-test each one:
```bash
python -m scripts.pipeline.publishing_agent --story-id sheetal-devi-YYYYMMDD
```
Inspect the JSON output — every platform should report success or a specific error.

---

## 3. Week 2 — Manual gold-standard pass

Write 3 stories **by hand** in Notion before trusting the AI. Pick:
- **Sheetal Devi** (Para Archery, recent Olympic gold)
- **Murlikant Petkar** (1972 Paralympic swimmer, biopic Chandu Champion)
- **Mariyappan Thangavelu** (Para High Jump, Rio gold)

This calibrates your editorial taste. Compare hand-written vs `--dry-run` output for each. Tune `prompts/story_writer_prompt.txt` until AI output meets your bar at ≥80% of the time.

---

## 4. Week 3 — Automate the daily run

Set up Make.com:
1. Import `make_blueprints/daily_pipeline.json`.
2. Replace `{{REPLIT_URL}}`, `{{PIPELINE_TOKEN}}`, `{{OWNER_PHONE}}`, `{{DASHBOARD_URL}}`.
3. Schedule cron at 06:00 IST.
4. Add an HTTP endpoint to the dashboard (`/run-daily`) that calls `run_pipeline.run_daily()` — gated by `X-Auth` header.

Confirm: Day 1 of automation, you wake up to a WhatsApp ping and a single "Pending review" story.

---

## 5. Month 2 — Validation gate

Before pouring more money in, hit these numbers:
- [ ] 20 published stories
- [ ] 500 monthly visitors
- [ ] 50 newsletter subscribers
- [ ] At least one unsolicited share in a non-seeded WhatsApp group

If you don't hit these, the problem is **distribution**, not the pipeline. Pause feature work and spend two weeks posting in Reddit/IndianSports, IIT/college sports clubs, and Paralympic-fan groups.

---

## 6. Month 3-6 — AI features

Pull these from `Phase 3` of the README. The relevant code paths in this scaffold:

| Feature | Where to add |
|---------|--------------|
| AI story match | New file `scripts/pipeline/match_agent.py` — embed user query, query `supabase_client.client().rpc('match_stories', ...)` |
| 30-day goal plan | Extend `scripts/pipeline/social_asset_generator.py` with a `generate_plan(story, user_goal)` function |
| Instagram card image | Already stubbed in `social_asset_generator.render_card()` — wire to publishing_agent |
| India sports map | Webflow page + a Supabase `state` column on `stories` table |

---

## 7. Month 6-12 — Revenue activation

Follow `docs/revenue_playbook.md`. Specifically:

- [ ] Month 6: First sponsor pitch sent (target: JSW Sports, OGQ).
- [ ] Month 7: Razorpay live, first 10 paid subs.
- [ ] Month 8: Apply to Startup India + iStart Rajasthan grants.
- [ ] Month 10: First school programme pilot signed.
- [ ] Month 12: ₹1,00,000/month run-rate.

---

## 8. Things this scaffold deliberately does NOT include

- **No tests yet.** Add `pytest` once you have your first 5 published stories — that's when output stability starts to matter.
- **No auth on the dashboard.** Run it on Replit private + IP-restricted, or add Flask-Login when you go remote.
- **No image generation for the IG card** beyond a Pillow stub. Swap in Claude's image API or a Bannerbear template once you settle on visual identity.
- **No retry queue persistence** — failed Webflow/Mailchimp pushes are logged but not auto-retried. Add a `failed_publishes` table in Supabase when the platform stabilizes.

---

## 9. The one rule that matters

Every shortcut you take in writing a story shows up as bland, generic motivational copy that nobody shares. The pipeline is fine. **The prompts in `prompts/` are the product.** Spend more time tuning them than tuning code.

> "They told Sheetal Devi she had no future without arms. She drew a bow with her feet and won Olympic gold."

Ship.
