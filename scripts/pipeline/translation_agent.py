"""Step 4 — Translation Agent (7 Indian languages)."""
from __future__ import annotations
import json
from pathlib import Path
from dotenv import load_dotenv

from scripts.utils import nvidia_client, model_config

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]

# Translations are disabled in NeverQuit (English-only). The prompt file may
# not exist — degrade gracefully so this module can still be imported.
_PROMPT_PATH = ROOT / "prompts" / "translation_prompt.txt"
PROMPT = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""

LANGUAGES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "kn": "Kannada",
    "mr": "Marathi",
    "bn": "Bengali",
    "te": "Telugu",
    "gu": "Gujarati",
}

SYSTEM = "You are an expert literary translator into Indian languages. Faithful tone, natural phrasing."


def translate(story: dict, code: str) -> dict:
    if not PROMPT:
        raise RuntimeError(
            "Translation is disabled — prompts/translation_prompt.txt was removed."
        )
    user = (
        PROMPT.replace("{target_language_name}", LANGUAGES[code])
        .replace("{target_language_code}", code)
        .replace("{story_json}", json.dumps(story, ensure_ascii=False))
    )
    cfg = model_config.config_for("translation")
    return nvidia_client.complete_json(
        SYSTEM, user, max_tokens=cfg["max_tokens"],
        enable_reasoning=cfg["reasoning"], model_name=cfg["model"],
    )


def run(story: dict) -> dict:
    """No-op when translations are disabled (English-only project)."""
    if not PROMPT:
        return {}
    out = {}
    for code in LANGUAGES:
        try:
            out[code] = translate(story, code)
            print(f"  ✓ {code}")
        except Exception as e:
            print(f"  ✗ {code}: {e}")
            out[code] = {"error": str(e)}
    return out


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--story", required=True)
    args = p.parse_args()
    s = json.loads(Path(args.story).read_text(encoding="utf-8"))
    print(json.dumps(run(s), indent=2, ensure_ascii=False))
