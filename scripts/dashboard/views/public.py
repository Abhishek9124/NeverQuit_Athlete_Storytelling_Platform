"""Public-facing pages: home, story reader, saved, submit, feeds, media, health."""
from __future__ import annotations
from xml.sax.saxutils import escape as _xml_escape

from flask import (
    Blueprint, render_template, request, url_for, abort,
    Response, send_from_directory,
)

from scripts.utils import storage
from scripts.dashboard import config
from scripts.dashboard.seed_stories import SEED_STORIES
from scripts.dashboard.helpers import (
    _is_admin, _card, _all_published_cards, _abs_url, _site_url, _excerpt,
)

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    cards = _all_published_cards()
    showing_examples = not storage.list_stories("published")

    by_sport: dict = {}
    for c in cards:
        by_sport.setdefault(c.get("sport") or "Other", []).append(c)

    counts = {
        "total": len(cards),
        "athletes": sum(1 for c in cards if c.get("type") == "athlete"),
        "para": sum(1 for c in cards if c.get("type") == "para"),
        "sports": len(by_sport),
        "countries": len({c.get("country") for c in cards if c.get("country")}),
    }
    return render_template(
        "public_home.html",
        cards=cards, sports=sorted(by_sport.keys()), by_sport=by_sport,
        counts=counts, langs=config.LANGS, site=config.SITE_NAME,
        is_admin=_is_admin(), showing_examples=showing_examples,
    )


@bp.route("/story/<sid>")
def public_story(sid):
    if sid in SEED_STORIES:
        s = SEED_STORIES[sid]
    else:
        try:
            s = storage.load_story(sid)
        except FileNotFoundError:
            abort(404)
        if s.get("status") != "published" and not _is_admin():
            abort(404)
    all_pub = [_card(x) for x in storage.list_stories("published") if x.get("story_id") != sid]
    if not all_pub:
        all_pub = [_card(x) for k, x in SEED_STORIES.items() if k != sid]
    same_sport = [c for c in all_pub if c["sport"].lower() == (s.get("sport") or "").lower()]
    related = (same_sport + [c for c in all_pub if c not in same_sport])[:3]

    sections = s.get("sections") or {}
    desc = _excerpt(sections.get("hook") or sections.get("into_you") or s.get("pull_quote") or config.SITE_TAGLINE)
    meta = {
        "title": f"{s.get('athlete_name','')} · {config.SITE_NAME}",
        "description": desc,
        "image": _abs_url(s.get("image_url") or (s.get("dossier") or {}).get("image_url") or ""),
        "url": _abs_url(url_for("public.public_story", sid=sid)),
        "type": "article",
        "athlete": s.get("athlete_name", ""),
        "sport": s.get("sport", ""),
    }
    return render_template(
        "public_story.html",
        s=s, sections=s["sections"], lang="en", langs=config.LANGS, site=config.SITE_NAME,
        is_admin=_is_admin(), related=related, meta=meta,
    )


@bp.route("/saved")
def saved_page():
    return render_template("saved.html", site=config.SITE_NAME, is_admin=_is_admin())


@bp.route("/submit")
def submit_page():
    return render_template("submit.html", site=config.SITE_NAME, is_admin=_is_admin())


# ---------- SEO / syndication ----------

@bp.route("/feed.xml")
@bp.route("/rss")
def rss_feed():
    """RSS 2.0 feed of the most recent published stories."""
    cards = list(reversed(_all_published_cards()))[:30]
    base = _site_url()
    items = []
    for c in cards:
        link = _abs_url(url_for("public.public_story", sid=c["id"]))
        title = _xml_escape(f'{c["athlete_name"]} — {c.get("sport","")}'.strip(" —"))
        desc = _xml_escape(_excerpt(c.get("hook") or c.get("pull_quote") or "", 300))
        img = _abs_url(c.get("image_url") or "")
        enclosure = f'<enclosure url="{_xml_escape(img)}" type="image/jpeg" />' if img else ""
        items.append(
            f"<item><title>{title}</title><link>{link}</link>"
            f"<guid isPermaLink=\"true\">{link}</guid>"
            f"<description>{desc}</description>{enclosure}</item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{_xml_escape(config.SITE_NAME)}</title>"
        f"<link>{_xml_escape(base)}</link>"
        f"<description>{_xml_escape(config.SITE_TAGLINE)}</description>"
        "<language>en</language>"
        + "".join(items)
        + "</channel></rss>"
    )
    return Response(xml, mimetype="application/rss+xml")


@bp.route("/sitemap.xml")
def sitemap():
    """XML sitemap covering static pages + every published story."""
    base = _site_url()
    urls = [f"{base}/", f"{base}/saved", f"{base}/submit"]
    urls += [_abs_url(url_for("public.public_story", sid=c["id"])) for c in _all_published_cards()]
    body = "".join(f"<url><loc>{_xml_escape(u)}</loc></url>" for u in urls)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           f"{body}</urlset>")
    return Response(xml, mimetype="application/xml")


@bp.route("/robots.txt")
def robots():
    base = _site_url()
    txt = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /api\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(txt, mimetype="text/plain")


# ---------- Media ----------

@bp.route("/media/<path:filename>")
def media(filename):
    resp = send_from_directory(config.IMAGES, filename)
    # Athlete photos rarely change — cache aggressively at the browser & CDN.
    resp.headers["Cache-Control"] = "public, max-age=2592000, immutable"  # 30 days
    return resp


@bp.route("/healthz")
def healthz():
    return {"ok": True, "site": config.SITE_NAME}
