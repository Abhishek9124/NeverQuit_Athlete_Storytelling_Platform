# Pipeline Architecture

```
discovery -> research -> write -> translate -> QA -> [HUMAN APPROVE] -> publish -> social
   |           |         |         |        |                          |        |
queue.json  dossier   sections  langs   confidence              Webflow + Mailchimp + Notion + Supabase
```

## State Machine

| status | set by | next states |
|---|---|---|
| `pending_review` | `run_pipeline` | approved, rejected |
| `approved` | dashboard / auto-QA | published |
| `rejected` | dashboard / low-QA | terminal |
| `published` | publishing_agent | terminal |

## Triggers

- Make.com cron at 06:00 IST -> `POST /run-daily` -> `run_pipeline.run_daily()`
- Owner click in dashboard -> `publishing_agent.publish(sid)`

## Failure Handling

- Each agent retries with exponential backoff through `tenacity`.
- `publishing_agent` records per-platform errors but does not block other platforms.
- Failed runs leave the athlete in `processed` to avoid retry storms; manual re-queue is available through the dashboard or `data/athlete_queue.json`.

## Model Configuration

The project uses NVIDIA's OpenAI-compatible API through `scripts/utils/nvidia_client.py`.

- `NVIDIA_API_KEY` supplies the API key.
- `NVIDIA_MODEL` is the default model for research and general agent calls.
- `NVIDIA_STORY_MODEL=openai/gpt-oss-20b` is used for story writing.

Costs depend on the selected NVIDIA models and account quota.
