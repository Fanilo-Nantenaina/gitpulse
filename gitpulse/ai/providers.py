from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field


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

    def available(self) -> bool:
        raise NotImplementedError

    def list_models(self) -> list[str]:
        return []

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        raise NotImplementedError


_CLAUDE_PRICES = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


@dataclass
class ClaudeProvider(Provider):
    name: str = "claude"
    model: str = field(default_factory=lambda: os.environ.get("GITPULSE_MODEL", "claude-sonnet-4-6"))

    def available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def list_models(self) -> list[str]:
        return list(_CLAUDE_PRICES.keys())

    def _price(self) -> tuple[float, float]:
        for key, p in _CLAUDE_PRICES.items():
            if self.model.startswith(key):
                return p
        return _CLAUDE_PRICES["claude-sonnet-4-6"]

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        pin, pout = self._price()
        cost = msg.usage.input_tokens * pin / 1e6 + msg.usage.output_tokens * pout / 1e6
        return GenResult(
            text=text,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            cost_usd=cost,
            truncated=(msg.stop_reason == "max_tokens"),
            model=self.model,
        )


@dataclass
class OllamaProvider(Provider):
    name: str = "ollama"
    host: str = field(default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    model: str = field(default_factory=lambda: os.environ.get("GITPULSE_OLLAMA_MODEL", ""))

    def _get(self, path: str, timeout: float = 2.0) -> dict | None:
        try:
            with urllib.request.urlopen(self.host.rstrip("/") + path, timeout=timeout) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None

    def available(self) -> bool:
        return self._get("/api/tags") is not None

    def list_models(self) -> list[str]:
        data = self._get("/api/tags")
        if not data:
            return []
        return [m["name"] for m in data.get("models", [])]

    def resolve_model(self) -> str | None:
        if self.model:
            return self.model
        models = self.list_models()
        return models[0] if models else None

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        model = self.resolve_model()
        if not model:
            raise RuntimeError("No Ollama model installed. Run `ollama pull llama3.1`.")
        body = json.dumps({
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"num_predict": max_tokens, "temperature": 0.2},
        }).encode()
        req = urllib.request.Request(
            self.host.rstrip("/") + "/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
        return GenResult(
            text=data.get("response", ""),
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            cost_usd=0.0,
            truncated=(data.get("done_reason") == "length"),
            model=model,
        )


def get_provider(name: str) -> Provider:
    if name == "claude":
        return ClaudeProvider()
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unknown provider: {name!r}")


def detect(preferred: str = "auto") -> Provider | None:
    if preferred == "claude":
        p = ClaudeProvider()
        return p if p.available() else None
    if preferred == "ollama":
        p = OllamaProvider()
        return p if p.available() else None
    if preferred == "local":
        return None
    for cls in (ClaudeProvider, OllamaProvider):
        p = cls()
        if p.available():
            return p
    return None


def status() -> list[tuple[str, bool, list[str]]]:
    out = []
    for cls in (ClaudeProvider, OllamaProvider):
        p = cls()
        ok = p.available()
        models = p.list_models() if ok else []
        out.append((p.name, ok, models))
    return out
