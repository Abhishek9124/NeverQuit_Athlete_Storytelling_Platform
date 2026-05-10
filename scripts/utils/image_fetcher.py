"""Fetch hero images for athletes from multiple free public sources.

Priority order:
1. Wikipedia (official, high quality)
2. Wikimedia Commons (licensed images)
3. Olympics/Paralympics official photos
4. Fallback placeholder

Saves to data/images/<slug>.jpg and returns URL for /media/<slug>.jpg.
"""
from __future__ import annotations
import re
import io
from pathlib import Path
import requests
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
IMG_DIR = ROOT / "data" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

UA = "NeverQuitBot/1.0 (https://neverquit.in)"


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")


def _wiki_thumb(name: str) -> str | None:
    """Wikipedia REST API: page summary returns thumbnail/originalimage."""
    try:
        title = name.replace(" ", "_")
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
            headers={"User-Agent": UA, "accept": "application/json"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        j = r.json()
        # Prefer original, fall back to thumbnail
        for key in ("originalimage", "thumbnail"):
            img = j.get(key)
            if img and img.get("source"):
                return img["source"]
    except Exception:
        return None
    return None


def _wiki_search_then_thumb(name: str) -> str | None:
    """Search Wikipedia for the name, take top hit, fetch its summary image."""
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": name,
                    "format": "json", "srlimit": 1},
            headers={"User-Agent": UA},
            timeout=10,
        )
        hits = (r.json().get("query") or {}).get("search") or []
        if not hits:
            return None
        return _wiki_thumb(hits[0]["title"])
    except Exception:
        return None


def _wikimedia_search(name: str) -> str | None:
    """Search Wikimedia Commons for athlete images."""
    try:
        # Wikimedia Commons REST API
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": name,
                "srnamespace": "6",  # File namespace
                "format": "json",
                "srlimit": 5,
            },
            headers={"User-Agent": UA},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        
        results = (r.json().get("query") or {}).get("search") or []
        for result in results:
            # Skip non-image files
            if not any(ext in result["title"].lower() for ext in [".jpg", ".png", ".webp"]):
                continue
            
            # Fetch the file info to get the actual image URL
            file_title = result["title"].replace("File:", "")
            file_r = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": result["title"],
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "format": "json",
                },
                headers={"User-Agent": UA},
                timeout=10,
            )
            if file_r.status_code == 200:
                pages = (file_r.json().get("query") or {}).get("pages") or {}
                for page in pages.values():
                    imageinfo = (page.get("imageinfo") or [{}])[0]
                    url = imageinfo.get("url")
                    if url and "commons.wikimedia.org" in url:
                        return url
    except Exception:
        return None
    return None


def _olympics_athlete_image(name: str, is_paralympics: bool = False) -> str | None:
    """Try to fetch from Olympics.com or Paralympics.com databases."""
    try:
        # Olympics.com search (basic approach - may vary by site structure)
        domain = "paralympics.com" if is_paralympics else "olympics.com"
        # Most Olympics athlete pages follow pattern: /en/athletes/<slug>
        name_slug = _slug(name)
        urls_to_try = [
            f"https://{domain}/en/athletes/{name_slug}",
        ]
        
        for url in urls_to_try:
            r = requests.head(url, headers={"User-Agent": UA}, timeout=5, allow_redirects=True)
            if r.status_code == 200:
                # Page exists, image likely embedded. This is a hint more than a guarantee.
                # For now, we mark this as attempted but don't parse HTML.
                pass
    except Exception:
        return None
    return None


def _google_images_fallback(name: str) -> str | None:
    """Last resort: Google Custom Search (requires API key, very limited)."""
    try:
        # This would require Google Custom Search API key
        # Skipping for now as most deployments won't have this
        pass
    except Exception:
        return None
    return None


def fetch(athlete_name: str, slug: str | None = None, is_paralympics: bool = False) -> dict | None:
    """Find a hero image for the athlete, save locally, return metadata.

    Search order:
    1. Wikipedia original image
    2. Wikipedia search then thumbnail
    3. Wikimedia Commons
    4. Olympics/Paralympics official sources
    5. Return None if not found

    Returns: {
        "local_path": str,
        "url": str,           # relative URL for Flask serving
        "source": str,        # "wikipedia", "commons", "cache", etc.
        "remote_url": str,    # original remote URL
        "athlete_name": str,
        "width": int or None, # image dimensions if available
        "height": int or None,
    } or None.
    """
    slug = slug or _slug(athlete_name)
    out = IMG_DIR / f"{slug}.jpg"
    miss_marker = IMG_DIR / f"{slug}.miss"

    # If we already tried and failed within the last 24h, skip the network entirely
    if miss_marker.exists():
        import time as _t
        if _t.time() - miss_marker.stat().st_mtime < 86400:
            return None

    # Check cache first
    if out.exists():
        return {
            "local_path": str(out),
            "url": f"/media/{slug}.jpg",
            "source": "cache",
            "remote_url": "",
            "athlete_name": athlete_name,
            "width": None,
            "height": None,
        }

    # Try image sources in priority order
    candidates = [
        (_wiki_thumb(athlete_name), "wikipedia"),
        (_wiki_search_then_thumb(athlete_name), "wikipedia_search"),
        (_wikimedia_search(athlete_name), "commons"),
        (_olympics_athlete_image(athlete_name, is_paralympics), "olympics"),
    ]

    for remote, source in candidates:
        if not remote:
            continue

        try:
            # Validate image URL before downloading
            if not any(domain in remote for domain in ["wikimedia", "wikipedia", "commons", "olympics", "paralympics"]):
                continue  # Only trust known image hosts

            r = requests.get(remote, headers={"User-Agent": UA}, timeout=15)
            r.raise_for_status()
            
            # Validate it's actually an image
            if not r.headers.get("content-type", "").startswith("image/"):
                continue

            # Check minimum file size (avoid tiny/corrupted images)
            if len(r.content) < 5000:  # At least 5KB
                continue

            # Save the image
            out.write_bytes(r.content)
            
            return {
                "local_path": str(out),
                "url": f"/media/{slug}.jpg",
                "source": source,
                "remote_url": remote,
                "athlete_name": athlete_name,
                "width": None,  # Could parse headers, but optional
                "height": None,
            }
        except Exception as e:
            continue  # Try next source

    # No image found — write a marker so we don't retry this name for 24h
    try:
        miss_marker.write_text("")
    except Exception:
        pass
    return None
