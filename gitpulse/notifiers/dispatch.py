from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText
from typing import Callable


def _post_json(url: str, payload: dict) -> bool:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def notify_slack(markdown: str) -> bool:
    url = os.environ.get("GITPULSE_SLACK_WEBHOOK")
    if not url:
        return False
    return _post_json(url, {"text": markdown})


def notify_telegram(markdown: str) -> bool:
    token = os.environ.get("GITPULSE_TELEGRAM_TOKEN")
    chat = os.environ.get("GITPULSE_TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return _post_json(
        url, {"chat_id": chat, "text": markdown, "parse_mode": "Markdown"}
    )


def notify_email(markdown: str) -> bool:
    host = os.environ.get("GITPULSE_SMTP_HOST")
    to = os.environ.get("GITPULSE_SMTP_TO")
    if not (host and to):
        return False
    msg = MIMEText(markdown, "plain", "utf-8")
    msg["Subject"] = "GitPulse digest"
    msg["From"] = os.environ.get("GITPULSE_SMTP_FROM", to)
    msg["To"] = to
    try:
        port = int(os.environ.get("GITPULSE_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls()
            user = os.environ.get("GITPULSE_SMTP_USER")
            pw = os.environ.get("GITPULSE_SMTP_PASS")
            if user and pw:
                s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception:
        return False


def notify_desktop(markdown: str) -> bool:
    try:
        from plyer import notification

        title = markdown.splitlines()[0].lstrip("# ").strip()
        notification.notify(title="GitPulse", message=title[:200], timeout=10)
        return True
    except Exception:
        return False


NOTIFIERS: dict[str, Callable[[str], bool]] = {
    "slack": notify_slack,
    "telegram": notify_telegram,
    "email": notify_email,
    "desktop": notify_desktop,
}


def dispatch(channels: list[str], markdown: str) -> dict[str, bool]:
    return {ch: NOTIFIERS[ch](markdown) for ch in channels if ch in NOTIFIERS}
