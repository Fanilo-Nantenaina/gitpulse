from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...core import config as gp_config
from ...ai import providers as ai_providers

router = APIRouter(prefix="/api")


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
    out = {}
    for prov in ("claude", "openai", "gemini"):
        k = gp_config.get_api_key(prov)
        out[prov] = {
            "set": bool(k),
            "masked": (
                (k[:6] + "…" + k[-4:]) if k and len(k) > 12 else ("set" if k else None)
            ),
        }
    return out


@router.post("/keys")
def api_set_key(body: dict):
    prov = body.get("provider")
    if prov not in ("claude", "openai", "gemini"):
        raise HTTPException(400, "Unknown provider")
    gp_config.set_api_key(prov, body.get("key", "").strip())
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
