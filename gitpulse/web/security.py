
from __future__ import annotations

import ipaddress
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain", ""})


def _is_loopback_host(hostname: str) -> bool:
    if hostname.lower() in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _split_host(value: str) -> str:
    value = value.strip()
    if value.startswith("["):
        return value[1 : value.index("]")] if "]" in value else value[1:]
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


def allowed_hostnames(bind_host: str | None = None) -> set[str]:
    names = {"localhost", "localhost.localdomain", "127.0.0.1", "::1", "[::1]"}
    if bind_host:
        names.add(bind_host.strip().lower())
    extra = os.environ.get("GITPULSE_ALLOWED_HOSTS", "")
    names.update(h.strip().lower() for h in extra.split(",") if h.strip())
    names.discard("")
    return names


class LocalOriginGuard(BaseHTTPMiddleware):

    def __init__(self, app, bind_host: str | None = None):
        super().__init__(app)
        self._bind_host = bind_host
        self._allowed = allowed_hostnames(bind_host)

    def _host_ok(self, header: str | None) -> bool:
        if not header:
            return True
        hostname = _split_host(header).lower()
        return hostname in self._allowed or _is_loopback_host(hostname)

    def _origin_ok(self, origin: str | None) -> bool:
        if not origin:
            return True
        if origin == "null":
            return False
        authority = origin.split("://", 1)[-1]
        hostname = _split_host(authority).lower()
        return hostname in self._allowed or _is_loopback_host(hostname)

    async def dispatch(self, request, call_next):
        if not self._host_ok(request.headers.get("host")):
            return JSONResponse(
                {
                    "detail": (
                        "Rejected: unrecognised Host header. GitPulse only "
                        "answers to localhost. Set GITPULSE_ALLOWED_HOSTS to "
                        "add a hostname."
                    )
                },
                status_code=421,
            )
        origin = request.headers.get("origin")
        if not self._origin_ok(origin):
            return JSONResponse(
                {"detail": "Rejected: cross-origin request."}, status_code=403
            )
        if request.method not in SAFE_METHODS:
            site = request.headers.get("sec-fetch-site")
            if site and site not in ("same-origin", "none"):
                return JSONResponse(
                    {"detail": "Rejected: cross-site state change."},
                    status_code=403,
                )
        return await call_next(request)
