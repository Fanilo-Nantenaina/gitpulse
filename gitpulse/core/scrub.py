from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

RedactPolicy = Literal["cloud", "always", "off"]

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?"
            r"(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
        ),
    ),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "github-token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b"),
    ),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    (
        "slack-webhook",
        re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+"),
    ),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe-key", re.compile(r"\b[rs]k_(?:live|test)_[0-9A-Za-z]{16,}\b")),
    ("telegram-token", re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    ),
    ("url-credentials", re.compile(r"(?<=://)[^/\s:@'\"]+:[^/\s@'\"]{3,}(?=@)")),
)

_ASSIGNMENT = re.compile(
    r"(?i)(?P<key>[\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|"
    r"access[_-]?key|private[_-]?key|client[_-]?secret)[\w.-]*)"
    r"(?P<sep>[\"']?\s*[:=]\s*)(?P<q>[\"']?)(?P<val>[^\s\"',;]{8,})(?P=q)"
)

_PLACEHOLDER = re.compile(
    r"(?i)^(?:x+|\*+|\.+|changeme|change_me|example|placeholder|your[_-]?\w*|"
    r"dummy|test|secret|password|null|none|true|false|undefined|redacted)$"
    r"|^\$|^<|^\{|^%|\(|\[REDACTED"
)


@dataclass
class ScrubResult:
    text: str
    findings: Counter[str] = field(default_factory=Counter[str])

    @property
    def count(self) -> int:
        return sum(self.findings.values())


def policy() -> RedactPolicy:
    value = os.environ.get("GITPULSE_REDACT", "cloud").strip().lower()
    if value in ("always", "off"):
        return value
    return "cloud"


def should_redact(provider_kind: str) -> bool:
    p = policy()
    if p == "off":
        return False
    return p == "always" or provider_kind == "cloud"


def entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    n = len(value)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


_IDENTIFIER_PATH = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+|[a-z_]+")
_FILE_PATH = re.compile(r"^[./~]|\.[A-Za-z]{2,5}$")


def _looks_secret(value: str) -> bool:
    if _PLACEHOLDER.search(value) or _IDENTIFIER_PATH.fullmatch(value):
        return False
    if _FILE_PATH.search(value):
        return False
    if value.isdigit():
        return False
    if not any(ch.isdigit() for ch in value):
        return len(value) >= 24 and entropy(value) >= 3.5
    return entropy(value) >= 3.0


def scrub(text: str) -> ScrubResult:
    result = ScrubResult(text)
    out = text
    for kind, pattern in _PATTERNS:

        def _sub(_m: re.Match[str], kind: str = kind) -> str:
            result.findings[kind] += 1
            return f"[REDACTED:{kind}]"

        out = pattern.sub(_sub, out)

    def _assign(m: re.Match[str]) -> str:
        val = m.group("val")
        if not _looks_secret(val):
            return m.group(0)
        result.findings["assigned-secret"] += 1
        q = m.group("q")
        return f"{m.group('key')}{m.group('sep')}{q}[REDACTED:assigned-secret]{q}"

    result.text = _ASSIGNMENT.sub(_assign, out)
    return result


def scan(text: str) -> Counter[str]:
    return scrub(text).findings
