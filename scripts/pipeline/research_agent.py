"""Step 2 — Research Agent. Build detailed factual dossier for an athlete.

Uses enhanced research prompt requiring 500+ words of detailed, verified information.
Fetches images from multiple sources (Wikipedia, Wikimedia, Olympics, etc.)
Uses NVIDIA Nemotron 3 Nano Omni with reasoning for deep research insights.
"""
from __future__ import annotations
import json
from pathlib import Path
from dotenv import load_dotenv

from scripts.utils import nvidia_client as client, image_fetcher, mcp_research, model_config

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]

# Try to use the new detailed research prompt (v2), fall back to original
PROMPT_V2 = (ROOT / "prompts" / "research_prompt_v2.txt").read_text(encoding="utf-8") if (ROOT / "prompts" / "research_prompt_v2.txt").exists() else None
PROMPT = PROMPT_V2 or (ROOT / "prompts" / "research_prompt.txt").read_text(encoding="utf-8")

SYSTEM = """You are NeverQuit's senior research agent — meticulous, thorough, uncompromising on quality.

Your job: Build comprehensive athlete dossiers with 500+ words of verified detail using deep reasoning.
- Think through multiple angles and verify facts carefully
- Research AGGRESSIVELY from multiple sources
- Cross-verify every fact from 2+ sources
- Use EXACT quotes from interviews (not paraphrased)
- Include specific names, dates, places, numbers
- Mark anything unverified or conflicted
- Return DETAILED JSON with all required fields populated

Minimum standards:
✓ 500+ total words of narrative
✓ 8+ sources cited
✓ 3-4 direct verified quotes
✓ 6-8+ competition results with years/results
✓ 4-5 specific struggles documented
✓ High quality, not generic summary"""


def run(athlete_name: str, sport: str = "", is_paralympics: bool = False, model_name: str = None) -> dict:
    """Build a comprehensive research dossier on an athlete.
    
    Args:
        athlete_name: Full name of athlete
        sport: Sport/discipline (e.g., "100m Sprint", "Swimming")
        is_paralympics: True if this is a Paralympic athlete
        model_name: Optional model name override (defaults to NVIDIA_MODEL from .env)
    
    Returns:
        dict: Comprehensive dossier with 500+ words of detail
    """
    # ── MCP enrichment (optional). Pulls authoritative facts from web search,
    #    Wikipedia, fetch tools, etc. via Model Context Protocol servers.
    mcp_context = ""
    if mcp_research.is_enabled():
        try:
            mcp_context = mcp_research.enrich(athlete_name, sport, timeout=45)
        except Exception:
            mcp_context = ""

    user = PROMPT.replace("{athlete_name}", athlete_name).replace("{sport}", sport)
    if mcp_context:
        user += (
            "\n\n═══════ AUTHORITATIVE CONTEXT FROM MCP TOOLS ═══════\n"
            "Treat this as your PRIMARY source. Cross-check the LLM's training\n"
            "data against these passages — when they conflict, trust this block.\n\n"
            + mcp_context
        )
    
    # Resolve model + token budget from the central registry; a per-call
    # model_name override (e.g. from the admin "re-research" tool) wins.
    cfg = model_config.config_for("research")
    model_id = model_name or cfg["model"]

    raw = client.complete(
        SYSTEM,
        user,
        max_tokens=cfg["max_tokens"],  # Generous limit so the dossier is rich enough for the writer.
        enable_reasoning=model_config.supports_reasoning(model_id),  # Reasoning iff the model family supports it
        model_name=model_id,
    )
    
    parsed = client.parse_json(raw)
    
    # Handle list-wrapped responses
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {}
    
    if not isinstance(parsed, dict):
        parsed = {}
    
    # Ensure basic fields
    parsed.setdefault("athlete_name", athlete_name)
    parsed.setdefault("sport", sport)
    parsed.setdefault("country", "")
    
    # Fetch hero image from multiple sources (best-effort)
    try:
        img = image_fetcher.fetch(
            parsed.get("athlete_name") or athlete_name,
            is_paralympics=is_paralympics
        )
        if img:
            parsed["image_url"] = img["url"]
            parsed["image_source"] = img["source"]
            parsed["image_remote_url"] = img.get("remote_url", "")
            parsed["image_athlete_name"] = img.get("athlete_name", athlete_name)
    except Exception as e:
        # Image fetch failure never fails the whole dossier
        pass
    
    # Validation: Check minimum word count in narrative sections
    narrative_fields = [
        parsed.get("early_life", ""),
        parsed.get("disability_or_injury", "") if isinstance(parsed.get("disability_or_injury"), str) else "",
        parsed.get("darkest_moment_scene", ""),
        parsed.get("daily_routine_details", ""),
        parsed.get("ripple_effects", ""),
        parsed.get("turning_point", {}).get("what", "") if isinstance(parsed.get("turning_point"), dict) else "",
        parsed.get("principle_or_research", ""),
    ]
    
    total_narrative_words = sum(len(field.split()) for field in narrative_fields if field)
    parsed["_research_metrics"] = {
        "narrative_word_count": total_narrative_words,
        "meets_500_word_minimum": total_narrative_words >= 500,
        "sources_count": len(parsed.get("sources", [])),
        "quotes_count": len(parsed.get("exact_quotes", [])),
        "mcp_used": bool(mcp_context),
        "mcp_context_chars": len(mcp_context),
    }
    
    return parsed


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--athlete", required=True, help="Athlete full name")
    p.add_argument("--sport", default="", help="Sport/discipline")
    p.add_argument("--paralympics", action="store_true", help="Is Paralympic athlete")
    args = p.parse_args()
    result = run(args.athlete, args.sport, args.paralympics)
    print(json.dumps(result, indent=2, ensure_ascii=False))
