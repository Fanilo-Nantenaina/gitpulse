from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field

from ..core import config as _config


@dataclass
class GenResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    truncated: bool = False
    model: str = ""


@dataclass
class Provider:
    name: str
    kind: str = "local"          # "cloud" | "local"

    def available(self) -> bool:
        raise NotImplementedError

    def detail(self) -> str:
        return ""

    def list_models(self) -> list[str]:
        return []

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        raise NotImplementedError


_CLAUDE_PRICES = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
_OPENAI_PRICES = {
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.4, 1.6),
}
_GEMINI_PRICES = {
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.3, 2.5),
    "gemini-2.0-flash": (0.1, 0.4),
}


@dataclass
class ClaudeProvider(Provider):
    name: str = "claude"
    kind: str = "cloud"
    model: str = field(default_factory=lambda: os.environ.get("GITPULSE_MODEL", "claude-sonnet-4-6"))

    def _key(self):
        return _config.get_api_key("claude")

    def available(self) -> bool:
        if not self._key():
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def detail(self) -> str:
        if not self._key():
            return "no API key"
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return "package 'anthropic' not installed"
        return "ready"

    def list_models(self) -> list[str]:
        return list(_CLAUDE_PRICES.keys())

    def _price(self):
        for key, p in _CLAUDE_PRICES.items():
            if self.model.startswith(key):
                return p
        return _CLAUDE_PRICES["claude-sonnet-4-6"]

    def generate(self, system, prompt, max_tokens):
        import anthropic
        client = anthropic.Anthropic(api_key=self._key())
        msg = client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        pin, pout = self._price()
        cost = msg.usage.input_tokens * pin / 1e6 + msg.usage.output_tokens * pout / 1e6
        return GenResult(text, msg.usage.input_tokens, msg.usage.output_tokens,
                         cost, msg.stop_reason == "max_tokens", self.model)


@dataclass
class OpenAIProvider(Provider):
    name: str = "openai"
    kind: str = "cloud"
    model: str = field(default_factory=lambda: os.environ.get("GITPULSE_OPENAI_MODEL", "gpt-4o-mini"))

    def _key(self):
        return _config.get_api_key("openai")

    def available(self) -> bool:
        return bool(self._key())

    def detail(self) -> str:
        return "ready" if self._key() else "no API key"

    def list_models(self) -> list[str]:
        return list(_OPENAI_PRICES.keys())

    def _price(self):
        for key, p in _OPENAI_PRICES.items():
            if self.model.startswith(key):
                return p
        return _OPENAI_PRICES["gpt-4o-mini"]

    def generate(self, system, prompt, max_tokens):
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._key()}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage = data.get("usage", {})
        pin, pout = self._price()
        it, ot = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        cost = it * pin / 1e6 + ot * pout / 1e6
        return GenResult(text, it, ot, cost,
                         choice.get("finish_reason") == "length", self.model)


@dataclass
class GeminiProvider(Provider):
    name: str = "gemini"
    kind: str = "cloud"
    model: str = field(default_factory=lambda: os.environ.get("GITPULSE_GEMINI_MODEL", "gemini-2.5-flash"))

    def _key(self):
        return _config.get_api_key("gemini")

    def available(self) -> bool:
        return bool(self._key())

    def detail(self) -> str:
        return "ready" if self._key() else "no API key"

    def list_models(self) -> list[str]:
        return list(_GEMINI_PRICES.keys())

    def _price(self):
        for key, p in _GEMINI_PRICES.items():
            if self.model.startswith(key):
                return p
        return _GEMINI_PRICES["gemini-2.5-flash"]

    def generate(self, system, prompt, max_tokens):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self._key()}")
        body = json.dumps({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens,
                                 "responseMimeType": "application/json"},
        }).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        cand = data["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        usage = data.get("usageMetadata", {})
        pin, pout = self._price()
        it = usage.get("promptTokenCount", 0)
        ot = usage.get("candidatesTokenCount", 0)
        cost = it * pin / 1e6 + ot * pout / 1e6
        return GenResult(text, it, ot, cost,
                         cand.get("finishReason") == "MAX_TOKENS", self.model)


@dataclass
class OllamaProvider(Provider):
    name: str = "ollama"
    kind: str = "local"
    host: str = field(default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    model: str = field(default_factory=lambda: os.environ.get("GITPULSE_OLLAMA_MODEL", ""))

    def _get(self, path, timeout=2.0):
        try:
            with urllib.request.urlopen(self.host.rstrip("/") + path, timeout=timeout) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None

    def available(self) -> bool:
        return self._get("/api/tags") is not None

    def detail(self) -> str:
        if self._get("/api/tags") is None:
            return "server not running"
        if not self.list_models():
            return "running, no models pulled"
        return "ready"

    def list_models(self) -> list[str]:
        data = self._get("/api/tags")
        return [m["name"] for m in data.get("models", [])] if data else []

    def resolve_model(self):
        if self.model:
            return self.model
        models = self.list_models()
        return models[0] if models else None

    def generate(self, system, prompt, max_tokens):
        model = self.resolve_model()
        if not model:
            raise RuntimeError("No Ollama model installed. Run `ollama pull qwen2.5-coder:7b`.")
        body = json.dumps({
            "model": model, "system": system, "prompt": prompt, "stream": False,
            "format": "json", "options": {"num_predict": max_tokens, "temperature": 0.2},
        }).encode()
        req = urllib.request.Request(self.host.rstrip("/") + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.loads(r.read())
        return GenResult(data.get("response", ""), data.get("prompt_eval_count", 0),
                         data.get("eval_count", 0), 0.0,
                         data.get("done_reason") == "length", model)


_REGISTRY = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}
# auto-detection order: local first (free), then cloud
_AUTO_ORDER = ["ollama", "claude", "openai", "gemini"]


def get_provider(name: str) -> Provider:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown provider: {name!r}")
    return _REGISTRY[name]()


def detect(preferred: str = "auto") -> Provider | None:
    if preferred == "local":
        return None
    if preferred in _REGISTRY:
        p = _REGISTRY[preferred]()
        return p if p.available() else None
    for name in _AUTO_ORDER:
        p = _REGISTRY[name]()
        if p.available():
            return p
    return None


def status() -> list[dict]:
    out = []
    for name, cls in _REGISTRY.items():
        p = cls()
        ok = p.available()
        out.append({
            "name": name, "kind": p.kind, "available": ok,
            "detail": p.detail(), "models": p.list_models() if ok else [],
            "has_key": _config.has_stored_key(name) if p.kind == "cloud" else None,
        })
    return out


def measure_cloud_latency(timeout: float = 3.0) -> dict:
    """Ping a lightweight cloud endpoint to gauge connectivity/latency."""
    targets = {
        "claude": "https://api.anthropic.com",
        "openai": "https://api.openai.com",
        "gemini": "https://generativelanguage.googleapis.com",
    }
    online = False
    latency_ms = None
    for url in targets.values():
        try:
            t0 = time.time()
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=timeout)
            latency_ms = round((time.time() - t0) * 1000)
            online = True
            break
        except urllib.error.HTTPError:
            latency_ms = round((time.time() - t0) * 1000)
            online = True
            break
        except (urllib.error.URLError, OSError):
            continue
    return {"online": online, "latency_ms": latency_ms}
