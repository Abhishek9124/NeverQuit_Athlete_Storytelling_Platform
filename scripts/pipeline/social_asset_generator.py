"""Step 8 — Social Asset Generator."""
from __future__ import annotations
import json
from pathlib import Path
from dotenv import load_dotenv

from scripts.utils import gemini_client as claude_client

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]
PROMPT = (ROOT / "prompts" / "social_assets_prompt.txt").read_text(encoding="utf-8")

SYSTEM = "You are a social media editor for sports stories. Punchy, emotionally specific, never generic."


def run(story: dict) -> dict:
    user = PROMPT.replace("{story_json}", json.dumps(story or {}, ensure_ascii=False))
    out = claude_client.complete_json(SYSTEM, user, max_tokens=20000)
    if isinstance(out, list):
        out = out[0] if out and isinstance(out[0], dict) else {}
    if not isinstance(out, dict):
        out = {}
    out.setdefault("whatsapp", "")
    out.setdefault("twitter_thread", [])
    out.setdefault("instagram_caption", "")
    out.setdefault("instagram_card", {})
    out.setdefault("email_subject_a", "")
    out.setdefault("email_subject_b", "")
    out.setdefault("newsletter_summary", "")
    return out


def render_card(quote: str, athlete_name: str, sport: str, out_path: Path) -> Path:
    """Optional: render a 1080x1080 PNG with the pull quote."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1080, 1080), (15, 23, 42))
    d = ImageDraw.Draw(img)
    try:
        font_q = ImageFont.truetype("arial.ttf", 56)
        font_n = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font_q = ImageFont.load_default()
        font_n = ImageFont.load_default()
    margin = 80
    d.multiline_text((margin, 200), f"“{quote}”", font=font_q, fill=(255, 255, 255), spacing=12)
    d.text((margin, 940), f"— {athlete_name}, {sport}", font=font_n, fill=(250, 204, 21))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path
