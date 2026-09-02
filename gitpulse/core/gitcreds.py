
from __future__ import annotations

import base64
import re

_URL_USERINFO = re.compile(r"(?P<scheme>[a-zA-Z][\w+.-]*://)(?P<userinfo>[^/@\s]+)@")
_TOKEN_LIKE = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{16,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|glpat-[A-Za-z0-9_-]{16,}"
    r"|sk-ant-[A-Za-z0-9_-]{16,}"
    r"|sk-[A-Za-z0-9]{32,}"
    r"|AIza[A-Za-z0-9_-]{30,})"
)
_AUTH_HEADER = re.compile(
    r"(Authorization\s*:\s*)(?:Basic|Bearer)\s+[A-Za-z0-9+/=._-]+", re.I
)
REDACTED = "***"


def redact(text: str | None, *extra_secrets: str | None) -> str:
    if not text:
        return ""
    out = str(text)
    for secret in extra_secrets:
        if secret and len(secret) >= 8:
            out = out.replace(secret, REDACTED)
    out = _AUTH_HEADER.sub(lambda m: f"{m.group(1)}{REDACTED}", out)
    out = _URL_USERINFO.sub(lambda m: f"{m.group('scheme')}{REDACTED}@", out)
    return _TOKEN_LIKE.sub(REDACTED, out)


def base64_basic(username: str, token: str) -> str:
    return base64.b64encode(f"{username}:{token}".encode()).decode()


def git_config_env(
    token: str | None = None,
    username: str | None = None,
    insecure: bool = False,
    for_url: str | None = None,
) -> dict[str, str]:
    entries: list[tuple[str, str]] = []
    is_http = bool(for_url) and for_url.lower().startswith(("http://", "https://"))
    if token and is_http:
        basic = base64_basic(username or "x-access-token", token)
        entries.append(("http.extraHeader", f"Authorization: Basic {basic}"))
    if insecure:
        entries.append(("http.sslVerify", "false"))

    env = {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "GIT_CONFIG_COUNT": "0"}
    if not entries:
        return env
    env["GIT_CONFIG_COUNT"] = str(len(entries))
    for i, (key, value) in enumerate(entries):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    return env
