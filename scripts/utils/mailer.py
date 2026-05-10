"""SMTP mailer for welcome emails and admin broadcasts.

Configure via .env:
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587                       # 465 for SSL, 587 for STARTTLS
  SMTP_USER=you@gmail.com
  SMTP_PASS=app-password              # for Gmail use an App Password
  SMTP_FROM=NeverQuit <you@gmail.com>
  SITE_URL=https://neverquit.in       # used in unsubscribe link

If SMTP_HOST is not set, send_email() returns False without raising — the
subscribe flow still completes successfully, the welcome email is just skipped.
"""
from __future__ import annotations
import os
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

log = logging.getLogger("neverquit.mailer")


def _enabled() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER"))


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Send an HTML email. Returns True on success, False otherwise."""
    if not _enabled():
        log.info("SMTP disabled; skipping email to %s (subject=%r)", to, subject)
        return False

    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ.get("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM") or formataddr(("NeverQuit", user))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    if text:
        msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                s.login(user, password)
                s.sendmail(user, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
                s.login(user, password)
                s.sendmail(user, [to], msg.as_string())
        return True
    except Exception as e:
        log.warning("SMTP send to %s failed: %s", to, e)
        return False


# ---------- Templates ----------

def _site_url() -> str:
    return (os.getenv("SITE_URL") or "https://neverquit.in").rstrip("/")


def welcome_email(email: str) -> tuple[str, str, str]:
    """Returns (subject, html, text) for the welcome message."""
    site = _site_url()
    unsub = f"{site}/api/unsubscribe?email={email}"
    subject = "Welcome to NeverQuit — one comeback story every Monday"
    html = f"""\
<!doctype html>
<html><body style="margin:0;padding:0;background:#f7f6f3;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f7f6f3;padding:40px 20px;">
  <tr><td align="center">
    <table width="540" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:14px;border:1px solid #e8e6e1;overflow:hidden;">
      <tr><td style="padding:36px 40px 28px 40px;">
        <div style="display:inline-block;width:36px;height:36px;background:#D85A30;border-radius:8px;text-align:center;line-height:36px;color:#FAECE7;font-weight:600;font-size:18px;margin-bottom:18px;">N</div>
        <h1 style="font-family:Georgia,serif;font-size:30px;font-weight:500;line-height:1.2;letter-spacing:-.02em;margin:0 0 14px 0;color:#1a1a1a;">
          You're in.
          <span style="color:#D85A30;">Welcome to NeverQuit.</span>
        </h1>
        <p style="font-size:16px;line-height:1.65;color:#525252;margin:0 0 16px 0;">
          One comeback story. Every Monday morning.
        </p>
        <p style="font-size:15px;line-height:1.65;color:#525252;margin:0 0 16px 0;">
          No noise. No motivational posters. Just one specific, vivid, true story of an athlete,
          Paralympian, or differently-abled person who refused to stop — delivered straight to
          your inbox.
        </p>
        <p style="font-size:15px;line-height:1.65;color:#525252;margin:0 0 28px 0;">
          Want a head start? Read the most recent story:
        </p>
        <a href="{site}" style="display:inline-block;background:#D85A30;color:#fff;text-decoration:none;font-size:14px;font-weight:500;padding:12px 22px;border-radius:30px;">
          Read this week's story →
        </a>
      </td></tr>
      <tr><td style="border-top:1px solid #e8e6e1;padding:18px 40px;font-size:11px;color:#8a8a8a;line-height:1.5;">
        You're receiving this because you signed up at <a href="{site}" style="color:#525252;">NeverQuit</a>.
        Don't want these emails? <a href="{unsub}" style="color:#D85A30;">Unsubscribe</a>.
      </td></tr>
    </table>
    <p style="font-size:11px;color:#8a8a8a;margin:20px 0 0 0;">© NeverQuit · True comebacks, told well.</p>
  </td></tr>
</table>
</body></html>
"""
    text = (
        "Welcome to NeverQuit.\n\n"
        "One comeback story. Every Monday morning.\n\n"
        "No noise. No motivational posters. Just one specific, vivid, true story of someone who "
        "refused to stop — delivered to your inbox.\n\n"
        f"Read this week's story: {site}\n\n"
        "—\n"
        f"Unsubscribe: {unsub}\n"
    )
    return subject, html, text


def broadcast_email(subject: str, body_text: str, email: str) -> tuple[str, str, str]:
    """Returns (subject, html, text) for an admin broadcast."""
    site = _site_url()
    unsub = f"{site}/api/unsubscribe?email={email}"
    body_html = body_text.strip().replace("\n\n", "</p><p>").replace("\n", "<br>")
    html = f"""\
<!doctype html>
<html><body style="margin:0;padding:0;background:#f7f6f3;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f7f6f3;padding:40px 20px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:14px;border:1px solid #e8e6e1;overflow:hidden;">
      <tr><td style="padding:32px 40px;">
        <h1 style="font-family:Georgia,serif;font-size:26px;font-weight:500;line-height:1.25;letter-spacing:-.015em;margin:0 0 18px 0;color:#1a1a1a;">{subject}</h1>
        <div style="font-size:15px;line-height:1.7;color:#1a1a1a;"><p>{body_html}</p></div>
        <hr style="border:none;border-top:1px solid #e8e6e1;margin:28px 0 18px 0;">
        <a href="{site}" style="display:inline-block;background:#D85A30;color:#fff;text-decoration:none;font-size:13px;font-weight:500;padding:10px 18px;border-radius:30px;">Visit NeverQuit →</a>
      </td></tr>
      <tr><td style="border-top:1px solid #e8e6e1;padding:14px 40px;font-size:11px;color:#8a8a8a;">
        <a href="{unsub}" style="color:#D85A30;">Unsubscribe</a>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>
"""
    text = body_text + f"\n\n—\nUnsubscribe: {unsub}\n"
    return subject, html, text
