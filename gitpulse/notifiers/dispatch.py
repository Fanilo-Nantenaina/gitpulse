from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from email.mime.text import MIMEText

NOT_CONFIGURED = "not configured"


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    ok: bool
    reason: str = ""
    configured: bool = True

    def __bool__(self) -> bool:
        return self.ok

    @property
    def status(self) -> str:
        if self.ok:
            return "ok"
        return "skipped" if not self.configured else "failed"

    def describe(self) -> str:
        return f"{self.channel}: {self.status}" + (
            f" ({self.reason})" if self.reason else ""
        )


def _skip(channel: str, detail: str) -> DeliveryResult:
    return DeliveryResult(channel, False, f"{NOT_CONFIGURED} - {detail}", False)


def _fail(channel: str, exc: BaseException) -> DeliveryResult:
    return DeliveryResult(channel, False, f"{type(exc).__name__}: {exc}")


def _post_json(channel: str, url: str, payload: dict[str, str]) -> DeliveryResult:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                return DeliveryResult(channel, True)
            return DeliveryResult(channel, False, f"HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except OSError:
            pass
        return DeliveryResult(channel, False, f"HTTP {e.code} {body}".strip())
    except (urllib.error.URLError, OSError, ValueError) as e:
        return _fail(channel, e)


def notify_slack(markdown: str) -> DeliveryResult:
    url = os.environ.get("GITPULSE_SLACK_WEBHOOK")
    if not url:
        return _skip("slack", "set GITPULSE_SLACK_WEBHOOK")
    return _post_json("slack", url, {"text": markdown})


def notify_telegram(markdown: str) -> DeliveryResult:
    token = os.environ.get("GITPULSE_TELEGRAM_TOKEN")
    chat = os.environ.get("GITPULSE_TELEGRAM_CHAT_ID")
    if not (token and chat):
        return _skip(
            "telegram", "set GITPULSE_TELEGRAM_TOKEN and GITPULSE_TELEGRAM_CHAT_ID"
        )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    result = _post_json(
        "telegram", url, {"chat_id": chat, "text": markdown, "parse_mode": "Markdown"}
    )
    if result.reason and token in result.reason:
        result = DeliveryResult(
            result.channel, result.ok, result.reason.replace(token, "***")
        )
    return result


def notify_email(markdown: str) -> DeliveryResult:
    host = os.environ.get("GITPULSE_SMTP_HOST")
    to = os.environ.get("GITPULSE_SMTP_TO")
    if not (host and to):
        return _skip("email", "set GITPULSE_SMTP_HOST and GITPULSE_SMTP_TO")
    msg = MIMEText(markdown, "plain", "utf-8")
    msg["Subject"] = "GitPulse digest"
    msg["From"] = os.environ.get("GITPULSE_SMTP_FROM", to)
    msg["To"] = to
    try:
        port = int(os.environ.get("GITPULSE_SMTP_PORT", "587"))
    except ValueError:
        return _skip("email", "GITPULSE_SMTP_PORT is not a number")
    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls()
            user = os.environ.get("GITPULSE_SMTP_USER")
            pw = os.environ.get("GITPULSE_SMTP_PASS")
            if user and pw:
                s.login(user, pw)
            s.send_message(msg)
        return DeliveryResult("email", True)
    except (smtplib.SMTPException, OSError) as e:
        return _fail("email", e)


def notify_desktop(markdown: str) -> DeliveryResult:
    try:
        from plyer import notification  # pyright: ignore[reportMissingTypeStubs]
    except ImportError:
        return _skip("desktop", "install the 'desktop' extra (plyer)")
    try:
        first = markdown.splitlines()[0] if markdown.splitlines() else "GitPulse"
        title = first.lstrip("# ").strip()
        # through a __getattribute__ proxy, which pyright can only type as
        notification.notify(  # pyright: ignore[reportOptionalCall]
            title="GitPulse", message=title[:200], timeout=10
        )
        return DeliveryResult("desktop", True)
    except Exception as e:
        return _fail("desktop", e)


NOTIFIERS: dict[str, Callable[[str], DeliveryResult]] = {
    "slack": notify_slack,
    "telegram": notify_telegram,
    "email": notify_email,
    "desktop": notify_desktop,
}


def dispatch(channels: list[str], markdown: str) -> dict[str, DeliveryResult]:
    results: dict[str, DeliveryResult] = {}
    for ch in channels:
        notifier = NOTIFIERS.get(ch)
        if notifier is None:
            known = ", ".join(sorted(NOTIFIERS))
            results[ch] = DeliveryResult(
                ch, False, f"unknown channel (known: {known})", configured=False
            )
            continue
        try:
            results[ch] = notifier(markdown)
        except Exception as e:
            results[ch] = _fail(ch, e)
    return results


def summarize_results(results: dict[str, DeliveryResult]) -> str:
    return "; ".join(r.describe() for r in results.values())
