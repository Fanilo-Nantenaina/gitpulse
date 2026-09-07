from __future__ import annotations

import abc
import importlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypedDict

from ..core import config as _config
from ..core.jsonio import JsonValue, as_array, as_int, as_object, as_str


@dataclass
class GenResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    truncated: bool = False
    model: str = ""


class ProviderStatus(TypedDict):
    name: str
    kind: str
    available: bool
    detail: str
    models: list[str]
    has_key: bool | None


class CloudLatency(TypedDict):
    online: bool
    latency_ms: int | None


@dataclass
class Provider(abc.ABC):
    name: str
    kind: str = "local"
    model: str = ""

    @abc.abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    def detail(self) -> str:
        return ""

    def list_models(self) -> list[str]:
        return []

    @abc.abstractmethod
    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        raise NotImplementedError


def _lookup_price(
    model: str, prices: dict[str, tuple[float, float]], default: str
) -> tuple[float, float]:
    if model in prices:
        return prices[model]
    matches = [k for k in prices if model.startswith(k)]
    if matches:
        return prices[max(matches, key=len)]
    return prices[default]


_CLAUDE_PRICES = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
DEFAULT_CLAUDE_MODEL = "claude-opus-5"
_OPENAI_PRICES = {
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.4, 1.6),
}
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
_GEMINI_PRICES = {
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.3, 2.5),
    "gemini-2.0-flash": (0.1, 0.4),
}
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

OLLAMA_MIN_CTX = 4096
OLLAMA_CTX_FALLBACK = 8192
OLLAMA_MAX_CTX = int(os.environ.get("GITPULSE_OLLAMA_MAX_CTX", "32768"))


def _anthropic_installed() -> bool:
    try:
        importlib.import_module("anthropic")
    except ImportError:
        return False
    return True


@dataclass
class ClaudeProvider(Provider):
    name: str = "claude"
    kind: str = "cloud"
    model: str = field(
        default_factory=lambda: os.environ.get("GITPULSE_MODEL", DEFAULT_CLAUDE_MODEL)
    )

    def _key(self) -> str | None:
        return _config.get_api_key("claude")

    def available(self) -> bool:
        if not self._key():
            return False
        return _anthropic_installed()

    def detail(self) -> str:
        if not self._key():
            return "no API key"
        if not _anthropic_installed():
            return "package 'anthropic' not installed"
        return "ready"

    def list_models(self) -> list[str]:
        return list(_CLAUDE_PRICES.keys())

    def _price(self) -> tuple[float, float]:
        return _lookup_price(self.model, _CLAUDE_PRICES, DEFAULT_CLAUDE_MODEL)

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        import anthropic

        client = anthropic.Anthropic(api_key=self._key())
        extra_headers: dict[str, str] = {}
        workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        if workspace_id:
            extra_headers["anthropic-workspace-id"] = workspace_id
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                extra_headers=extra_headers or None,
            )
        except anthropic.BadRequestError as e:
            if "workspace" in str(e).lower() and not workspace_id:
                raise RuntimeError(
                    "This Claude API key requires a workspace: set the "
                    "ANTHROPIC_WORKSPACE_ID environment variable, or use a "
                    "standard API key from console.anthropic.com instead."
                ) from e
            raise
        text = "".join(b.text for b in msg.content if b.type == "text")
        pin, pout = self._price()
        cost = msg.usage.input_tokens * pin / 1e6 + msg.usage.output_tokens * pout / 1e6
        return GenResult(
            text,
            msg.usage.input_tokens,
            msg.usage.output_tokens,
            cost,
            msg.stop_reason == "max_tokens",
            self.model,
        )


@dataclass
class OpenAIProvider(Provider):
    name: str = "openai"
    kind: str = "cloud"
    model: str = field(
        default_factory=lambda: os.environ.get(
            "GITPULSE_OPENAI_MODEL", DEFAULT_OPENAI_MODEL
        )
    )

    def _key(self) -> str | None:
        return _config.get_api_key("openai")

    def available(self) -> bool:
        return bool(self._key())

    def detail(self) -> str:
        return "ready" if self._key() else "no API key"

    def list_models(self) -> list[str]:
        return list(_OPENAI_PRICES.keys())

    def _price(self) -> tuple[float, float]:
        return _lookup_price(self.model, _OPENAI_PRICES, DEFAULT_OPENAI_MODEL)

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._key()}",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            payload: JsonValue = json.loads(r.read())
        data = as_object(payload)
        choices = as_array(data.get("choices"))
        if not choices:
            raise RuntimeError("OpenAI response contained no choices")
        choice = as_object(choices[0])
        text = as_str(as_object(choice.get("message")).get("content"))
        usage = as_object(data.get("usage"))
        pin, pout = self._price()
        it = as_int(usage.get("prompt_tokens"))
        ot = as_int(usage.get("completion_tokens"))
        cost = it * pin / 1e6 + ot * pout / 1e6
        return GenResult(
            text, it, ot, cost, choice.get("finish_reason") == "length", self.model
        )


@dataclass
class GeminiProvider(Provider):
    name: str = "gemini"
    kind: str = "cloud"
    model: str = field(
        default_factory=lambda: os.environ.get(
            "GITPULSE_GEMINI_MODEL", DEFAULT_GEMINI_MODEL
        )
    )

    def _key(self) -> str | None:
        return _config.get_api_key("gemini")

    def available(self) -> bool:
        return bool(self._key())

    def detail(self) -> str:
        return "ready" if self._key() else "no API key"

    def list_models(self) -> list[str]:
        return list(_GEMINI_PRICES.keys())

    def _price(self) -> tuple[float, float]:
        return _lookup_price(self.model, _GEMINI_PRICES, DEFAULT_GEMINI_MODEL)

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        body = json.dumps(
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "responseMimeType": "application/json",
                },
            }
        ).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._key() or "",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            payload: JsonValue = json.loads(r.read())
        data = as_object(payload)
        candidates = as_array(data.get("candidates"))
        if not candidates:
            raise RuntimeError("Gemini response contained no candidates")
        cand = as_object(candidates[0])
        parts = as_array(as_object(cand.get("content")).get("parts"))
        text = "".join(as_str(as_object(p).get("text")) for p in parts)
        usage = as_object(data.get("usageMetadata"))
        pin, pout = self._price()
        it = as_int(usage.get("promptTokenCount"))
        ot = as_int(usage.get("candidatesTokenCount"))
        cost = it * pin / 1e6 + ot * pout / 1e6
        return GenResult(
            text, it, ot, cost, cand.get("finishReason") == "MAX_TOKENS", self.model
        )


class OllamaModel(TypedDict):
    name: str
    capabilities: list[str] | None
    context_length: int | None


def _parse_tags(payload: JsonValue) -> list[OllamaModel]:
    out: list[OllamaModel] = []
    for entry in as_array(as_object(payload).get("models")):
        model = as_object(entry)
        name = model.get("name")
        if not isinstance(name, str) or not name:
            continue
        caps = model.get("capabilities")
        limit = as_object(model.get("details")).get("context_length")
        out.append(
            {
                "name": name,
                "capabilities": (
                    [c for c in caps if isinstance(c, str)]
                    if isinstance(caps, list)
                    else None
                ),
                "context_length": (
                    limit if isinstance(limit, int) and limit > 0 else None
                ),
            }
        )
    return out


@dataclass
class OllamaProvider(Provider):
    name: str = "ollama"
    kind: str = "local"
    host: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    )
    model: str = field(
        default_factory=lambda: os.environ.get("GITPULSE_OLLAMA_MODEL", "")
    )

    def _get(self, path: str, timeout: float = 2.0) -> JsonValue | None:
        try:
            with urllib.request.urlopen(
                self.host.rstrip("/") + path, timeout=timeout
            ) as r:
                parsed: JsonValue = json.loads(r.read())
                return parsed
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None

    def _tags(self) -> list[OllamaModel]:
        return _parse_tags(self._get("/api/tags"))

    def available(self) -> bool:
        return self._get("/api/tags") is not None

    def detail(self) -> str:
        if self._get("/api/tags") is None:
            return "server not running"
        if not self.list_models():
            return "running, no models pulled"
        return "ready"

    def list_models(self) -> list[str]:
        return [
            m["name"]
            for m in self._tags()
            if m["capabilities"] is None or "completion" in m["capabilities"]
        ]

    def resolve_model(self) -> str | None:
        if self.model:
            return self.model
        models = self._tags()
        if not models:
            return None

        def rank(m: OllamaModel) -> tuple[bool, bool]:
            caps = m["capabilities"] or []
            return ("completion" not in caps, "thinking" in caps)

        return sorted(models, key=rank)[0]["name"]

    def model_context_limit(self, model: str) -> int:
        for m in self._tags():
            if m["name"] == model:
                limit = m["context_length"]
                if limit is not None:
                    return limit
        return OLLAMA_CTX_FALLBACK

    def _num_ctx(self, model: str, system: str, prompt: str, max_tokens: int) -> int:
        estimated = (len(system) + len(prompt)) // 3 + max_tokens + 512
        ceiling = min(self.model_context_limit(model), OLLAMA_MAX_CTX)
        return max(OLLAMA_MIN_CTX, min(estimated, ceiling))

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        model = self.resolve_model()
        if not model:
            raise RuntimeError(
                "No Ollama model installed. Run `ollama pull qwen2.5-coder:7b`."
            )
        body = json.dumps(
            {
                "model": model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "num_predict": max_tokens,
                    "num_ctx": self._num_ctx(model, system, prompt, max_tokens),
                    "temperature": 0.2,
                },
            }
        ).encode()
        req = urllib.request.Request(
            self.host.rstrip("/") + "/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            payload: JsonValue = json.loads(r.read())
        data = as_object(payload)
        return GenResult(
            as_str(data.get("response")),
            as_int(data.get("prompt_eval_count")),
            as_int(data.get("eval_count")),
            0.0,
            data.get("done_reason") == "length",
            model,
        )


_REGISTRY: dict[str, Callable[[], Provider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}
_AUTO_ORDER: list[str] = ["ollama", "claude", "openai", "gemini"]


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


def status() -> list[ProviderStatus]:
    out: list[ProviderStatus] = []
    for name, cls in _REGISTRY.items():
        p = cls()
        ok = p.available()
        out.append(
            {
                "name": name,
                "kind": p.kind,
                "available": ok,
                "detail": p.detail(),
                "models": p.list_models() if ok else [],
                "has_key": _config.has_stored_key(name) if p.kind == "cloud" else None,
            }
        )
    return out


def measure_cloud_latency(timeout: float = 3.0) -> CloudLatency:
    targets = {
        "claude": "https://api.anthropic.com",
        "openai": "https://api.openai.com",
        "gemini": "https://generativelanguage.googleapis.com",
    }
    online = False
    latency_ms: int | None = None
    for url in targets.values():
        t0 = time.time()
        try:
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
