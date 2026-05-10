# SQLite vs MongoDB for NeverQuit

## Recommendation: **stay on SQLite for now. Migrate to Postgres (not Mongo) only when you outgrow it.**

## The honest comparison

| Concern | SQLite (current) | MongoDB |
|---|---|---|
| Setup | Zero — one file at `data/neverquit.sqlite` | Run a server / pay Atlas |
| Cost | ₹0, forever | ₹0 dev tier, ~₹500-2000/mo at scale |
| Backup | Copy one file | Configure backup snapshots |
| Schema | Strict columns + JSON blob — best of both | Schemaless |
| Writes | Single-writer (fine for solo founder) | Multi-writer concurrent |
| Search | `WHERE sport=? AND confidence>?` | Same, slightly different syntax |
| Vector search | `pgvector` if you switch to Postgres later | Atlas Vector Search (paid) |
| Hosting | Render disk volume / Fly volume | Atlas / self-hosted |
| Operational complexity | None | Moderate |

## Why SQLite wins for this project

1. **You're one founder publishing ~1 story/day.** Nothing about that workload needs a distributed database.
2. **Your stories already store full JSON** in the `payload_json` column — you have schemaless flexibility *and* indexed columns (`status`, `sport`, `confidence`).
3. **One file = one backup.** `cp data/neverquit.sqlite backup.sqlite` — done. Mongo backups need `mongodump` or Atlas plans.
4. **Render / Fly / Railway** all support SQLite on a 1GB persistent disk for free or near-free.
5. **AI story matching** (the Phase-3 feature in your README) needs vector search. SQLite has the `sqlite-vss` extension, but if you decide vector search is critical, **Postgres + pgvector is the migration path** — not Mongo. Postgres gives you SQL + JSONB + vectors in one engine.

## When MongoDB *would* make sense

- Multi-region writes (you're not multi-region)
- 100s of concurrent writers (you have 1)
- Document-level versioning at scale (overkill here)
- A team that already runs Mongo in production

None of those are NeverQuit today.

## The migration ladder (only if you grow)

```
data/neverquit.sqlite    ← you are here
        ↓
   1,000 stories
        ↓
Postgres (managed, e.g. Supabase you already have keys for)
+ pgvector for AI story match
        ↓
Read replicas / sharding (probably never)
```

## Concrete advice

**For now**: stay on SQLite. The schema is in `scripts/utils/db.py`. The DB is the source of truth; JSON files in `data/stories/` are human-readable backups.

**When you cross 1,000 stories or add multi-user editing**: migrate to Supabase Postgres. Your existing `scripts/utils/supabase_client.py` already has the wiring stub — uncomment it and run a one-off importer that reads from SQLite and inserts into Postgres.

**Never**: switch to Mongo. It buys you nothing for this workload and forfeits SQL — which you'll want for analytics and reporting.
