"""Mailchimp campaign creator."""
from __future__ import annotations
import os
import requests
from requests.auth import HTTPBasicAuth


def send_campaign(subject: str, html: str) -> dict | None:
    key = os.getenv("MAILCHIMP_API_KEY")
    audience = os.getenv("MAILCHIMP_AUDIENCE_ID")
    prefix = os.getenv("MAILCHIMP_SERVER_PREFIX", "us1")
    if not (key and audience):
        return None
    base = f"https://{prefix}.api.mailchimp.com/3.0"
    auth = HTTPBasicAuth("anystring", key)
    cmp = requests.post(
        f"{base}/campaigns",
        auth=auth,
        json={
            "type": "regular",
            "recipients": {"list_id": audience},
            "settings": {"subject_line": subject, "from_name": "NeverQuit", "reply_to": "hello@neverquit.in", "title": subject},
        },
        timeout=30,
    ).json()
    cid = cmp["id"]
    requests.put(f"{base}/campaigns/{cid}/content", auth=auth, json={"html": html}, timeout=30).raise_for_status()
    requests.post(f"{base}/campaigns/{cid}/actions/send", auth=auth, timeout=30).raise_for_status()
    return cmp
