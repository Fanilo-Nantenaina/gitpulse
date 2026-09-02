
from __future__ import annotations

import smtplib
import urllib.error
from unittest import mock

import pytest

from gitpulse.notifiers import dispatch as D

MD = "# Digest\n\nsome work happened"


@pytest.fixture(autouse=True)
def no_channel_env(monkeypatch):
    for var in (
        "GITPULSE_SLACK_WEBHOOK",
        "GITPULSE_TELEGRAM_TOKEN",
        "GITPULSE_TELEGRAM_CHAT_ID",
        "GITPULSE_SMTP_HOST",
        "GITPULSE_SMTP_TO",
        "GITPULSE_SMTP_PORT",
    ):
        monkeypatch.delenv(var, raising=False)




@pytest.mark.parametrize("channel", ["slack", "telegram", "email"])
def test_unconfigured_channel_is_skipped_with_a_hint(channel):
    r = D.NOTIFIERS[channel](MD)
    assert not r
    assert r.status == "skipped"
    assert r.configured is False
    assert "GITPULSE_" in r.reason


def test_failed_channel_is_distinguished_from_skipped(monkeypatch):
    monkeypatch.setenv("GITPULSE_SLACK_WEBHOOK", "https://hooks.example/x")
    with mock.patch(
        "urllib.request.urlopen", side_effect=urllib.error.URLError("no route")
    ):
        r = D.notify_slack(MD)
    assert not r
    assert r.status == "failed"
    assert r.configured is True
    assert "no route" in r.reason


def test_successful_delivery(monkeypatch):
    monkeypatch.setenv("GITPULSE_SLACK_WEBHOOK", "https://hooks.example/x")

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with mock.patch("urllib.request.urlopen", return_value=Resp()):
        r = D.notify_slack(MD)
    assert r and r.status == "ok" and r.reason == ""


def test_http_error_body_is_reported(monkeypatch):
    monkeypatch.setenv("GITPULSE_SLACK_WEBHOOK", "https://hooks.example/x")
    err = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err):
        r = D.notify_slack(MD)
    assert not r and "403" in r.reason


def test_smtp_failure_reports_the_reason(monkeypatch):
    monkeypatch.setenv("GITPULSE_SMTP_HOST", "smtp.example")
    monkeypatch.setenv("GITPULSE_SMTP_TO", "a@b.c")
    with mock.patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "busy")):
        r = D.notify_email(MD)
    assert not r and r.status == "failed" and "421" in r.reason


def test_bad_smtp_port_is_reported_not_crashed(monkeypatch):
    monkeypatch.setenv("GITPULSE_SMTP_HOST", "smtp.example")
    monkeypatch.setenv("GITPULSE_SMTP_TO", "a@b.c")
    monkeypatch.setenv("GITPULSE_SMTP_PORT", "not-a-port")
    r = D.notify_email(MD)
    assert not r and "not a number" in r.reason


def test_telegram_token_is_scrubbed_from_the_reason(monkeypatch):
    token = "123456:AAHsecrettokenvalue"
    monkeypatch.setenv("GITPULSE_TELEGRAM_TOKEN", token)
    monkeypatch.setenv("GITPULSE_TELEGRAM_CHAT_ID", "42")
    err = urllib.error.HTTPError(
        f"https://api.telegram.org/bot{token}/sendMessage", 401, "no", {}, None
    )
    with mock.patch("urllib.request.urlopen", side_effect=err):
        r = D.notify_telegram(MD)
    assert token not in r.reason




def test_unknown_channel_is_reported_not_dropped():
    results = D.dispatch(["nope"], MD)
    assert set(results) == {"nope"}
    assert not results["nope"]
    assert "unknown channel" in results["nope"].reason


def test_one_raising_notifier_does_not_abort_the_others(monkeypatch):
    monkeypatch.setitem(
        D.NOTIFIERS, "slack", lambda md: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    results = D.dispatch(["slack", "email"], MD)
    assert set(results) == {"slack", "email"}
    assert "boom" in results["slack"].reason
    assert results["email"].status == "skipped"


def test_results_stay_truthy_falsy_for_existing_callers():
    results = D.dispatch(["slack"], MD)
    for _ch, ok in results.items():
        assert bool(ok) is False


def test_summarize_results_mentions_every_channel():
    text = D.summarize_results(D.dispatch(["slack", "email"], MD))
    assert "slack" in text and "email" in text
