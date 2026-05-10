"""Step 7 — Publishing Agent. Pushes approved story everywhere."""
from __future__ import annotations
import os
from dotenv import load_dotenv

from scripts.utils import storage, webflow_client, mailchimp_client, notion_client, supabase_client
from scripts.pipeline import social_asset_generator

load_dotenv()


def publish(story_id: str) -> dict:
    s = storage.load_story(story_id)
    assert s.get("status") == "approved", f"Story {story_id} not approved (status={s.get('status')})"

    results = {"story_id": story_id}

    try:
        results["webflow"] = bool(webflow_client.publish(s))
    except Exception as e:
        results["webflow_error"] = str(e)

    try:
        assets = s.get("social_assets") or social_asset_generator.run(s["sections"])
        s["social_assets"] = assets
        subj = assets.get("email_subject_a") or s["sections"]["pull_quote"]
        html = f"<h1>{s['athlete_name']}</h1><p>{s['sections']['hook']}</p><p>{assets.get('newsletter_summary', '')}</p>"
        results["mailchimp"] = bool(mailchimp_client.send_campaign(subj, html))
    except Exception as e:
        results["mailchimp_error"] = str(e)

    try:
        results["notion"] = notion_client.push_story(s)
    except Exception as e:
        results["notion_error"] = str(e)

    try:
        results["supabase"] = bool(supabase_client.upsert_story(s))
    except Exception as e:
        results["supabase_error"] = str(e)

    storage.update_story(story_id, status="published", publish_results=results)
    return results


if __name__ == "__main__":
    import argparse, json
    p = argparse.ArgumentParser()
    p.add_argument("--story-id", required=True)
    args = p.parse_args()
    print(json.dumps(publish(args.story_id), indent=2, ensure_ascii=False))
