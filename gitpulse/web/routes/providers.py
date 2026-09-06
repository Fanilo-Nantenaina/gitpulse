from __future__ import annotations

from typing import TypedDict

from fastapi import APIRouter, HTTPException

from ...ai import providers as ai_providers
from ...core import config as gp_config

router = APIRouter(prefix="/api")

_KEYED_PROVIDERS = ("claude", "openai", "gemini")


class KeyStatus(TypedDict):
    set: bool
    masked: str | None


def _ollama_available() -> bool:
    return ai_providers.OllamaProvider().available()


@router.get("/providers")
def api_providers():
    return ai_providers.status()


@router.get("/latency")
def api_latency():
    return ai_providers.measure_cloud_latency()


@router.get("/keys")
def api_keys():
    out: dict[str, KeyStatus] = {}
    for prov in _KEYED_PROVIDERS:
        k = gp_config.get_api_key(prov)
        out[prov] = {
            "set": bool(k),
            "masked": (
                (k[:6] + "…" + k[-4:]) if k and len(k) > 12 else ("set" if k else None)
            ),
        }
    return out


@router.post("/keys")
def api_set_key(body: dict[str, object]):
    prov = body.get("provider")
    if not isinstance(prov, str) or prov not in _KEYED_PROVIDERS:
        raise HTTPException(400, "Unknown provider")
    key = body.get("key", "")
    gp_config.set_api_key(prov, key.strip() if isinstance(key, str) else "")
    return {"ok": True}


@router.post("/ollama/start")
def api_ollama_start():
    import shutil
    import subprocess
    import time

    if not shutil.which("ollama"):
        return {
            "started": False,
            "error": "Ollama is not installed. See https://ollama.com/download",
        }
    try:
        if _ollama_available():
            return {"started": True, "already": True}
        from ...core.procutil import popen as _ppopen

        _ppopen(
            ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        for _ in range(10):
            time.sleep(0.6)
            if _ollama_available():
                return {"started": True}
        return {"started": False, "error": "Ollama did not become ready in time."}
    except Exception as e:
        return {"started": False, "error": str(e)}
