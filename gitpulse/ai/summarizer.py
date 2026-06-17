from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass

from ..core.models import RepoActivity

DEFAULT_MODEL = os.environ.get("GITPULSE_MODEL", "claude-sonnet-4-6")

_SYSTEM = textwrap.dedent(
    """\
    You are a senior engineer writing a concise activity digest for a developer
    reviewing their own recent git history. Group related commits into themes
    (e.g. "Authentication", "CI/CD", "Bug fixes") rather than listing commits
    one by one. Be specific and technical but readable. Infer intent from commit
    messages and the files touched. Never invent work that isn't in the data.

    Respond ONLY with valid JSON, no markdown fences, in this exact shape:
    {
      "headline": "one-sentence summary of the period",
      "themes": [
        {"title": "Theme name", "narrative": "2-3 sentence description",
         "commits": ["short_sha", ...]}
      ],
      "observations": ["notable pattern or risk", ...]
    }
    """
)


@dataclass
class Summary:
    headline: str
    themes: list[dict]
    observations: list[str]
    raw: str = ""
    source: str = "local"  # "claude" | "local" | "local(truncated)"
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    stop_reason: str = ""

    @property
    def cost_note(self) -> str:
        if self.source.startswith("local") and self.cost_usd == 0:
            return "local fallback (no API call, $0.00)"
        return (
            f"{self.source} · {self.input_tokens}+{self.output_tokens} tok "
            f"· ${self.cost_usd:.4f}"
        )

    @classmethod
    def from_json(cls, text: str) -> "Summary":
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        return cls(
            headline=data.get("headline", ""),
            themes=data.get("themes", []),
            observations=data.get("observations", []),
            raw=text,
        )


def _build_payload(activity: RepoActivity) -> str:
    """Compact, token-efficient representation of the activity for the model."""
    lines = [
        f"Repository: {activity.repo_name}",
        f"Window: {activity.since:%Y-%m-%d} to {activity.until:%Y-%m-%d}",
        f"Commits: {activity.commit_count}  "
        f"(+{activity.total_additions} / -{activity.total_deletions} lines)",
        "",
        "Commits (newest first):",
    ]
    for c in activity.commits:
        files = ", ".join(
            f"{f.path}(+{f.additions}/-{f.deletions})" for f in c.files[:8]
        )
        lines.append(f"- [{c.short_sha}] {c.when:%m-%d %H:%M} {c.summary}")
        if c.body:
            lines.append(f"    note: {c.body.splitlines()[0][:120]}")
        if files:
            lines.append(f"    files: {files}")
    return "\n".join(lines)


def _local_fallback(activity: RepoActivity) -> Summary:
    """Deterministic summary when no API key is present."""
    by_prefix: dict[str, list[str]] = {}
    for c in activity.commits:
        prefix = c.summary.split(":", 1)[0] if ":" in c.summary[:12] else "other"
        by_prefix.setdefault(prefix, []).append(c.short_sha)
    themes = [
        {"title": k, "narrative": f"{len(v)} commit(s).", "commits": v}
        for k, v in by_prefix.items()
    ]
    obs = []
    late = [c for c in activity.commits if c.hour >= 22 or c.hour < 6]
    if late:
        obs.append(f"{len(late)} commit(s) outside working hours.")
    top = next(iter(activity.hotspots.items()), None)
    if top and top[1] > 1:
        obs.append(f"Hotspot: {top[0]} changed {top[1]}x (possible churn).")
    return Summary(
        headline=f"{activity.commit_count} commits on {activity.repo_name}.",
        themes=themes,
        observations=obs,
    )


def summarize(activity: RepoActivity, model: str = DEFAULT_MODEL) -> Summary:
    """Produce a semantic summary, using Claude if available else local fallback."""
    if activity.commit_count == 0:
        return Summary(
            headline="No activity in this window.", themes=[], observations=[]
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _local_fallback(activity)

    try:
        import anthropic
    except ImportError:
        return _local_fallback(activity)

    # Sonnet 4.6 pricing (USD per token). Update if pricing changes.
    PRICE_IN = 3.0 / 1_000_000
    PRICE_OUT = 15.0 / 1_000_000

    # Scale output budget with commit count: ~80 tokens of JSON per theme,
    # and themes roughly track commit volume. Clamp to a sane ceiling.
    max_tokens = min(8000, max(2000, activity.commit_count * 90))

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _build_payload(activity)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    in_tok = msg.usage.input_tokens
    out_tok = msg.usage.output_tokens
    cost = in_tok * PRICE_IN + out_tok * PRICE_OUT

    # If the model hit the token ceiling, the JSON is almost certainly cut off.
    if msg.stop_reason == "max_tokens":
        fb = _local_fallback(activity)
        fb.raw = text
        fb.source = "local(truncated)"
        fb.input_tokens, fb.output_tokens, fb.cost_usd = in_tok, out_tok, cost
        fb.stop_reason = "max_tokens"
        return fb

    try:
        summ = Summary.from_json(text)
        summ.source = "claude"
        summ.input_tokens, summ.output_tokens, summ.cost_usd = in_tok, out_tok, cost
        summ.stop_reason = msg.stop_reason or ""
        return summ
    except (json.JSONDecodeError, KeyError):
        fb = _local_fallback(activity)
        fb.raw = text
        fb.source = "local(parse-failed)"
        fb.input_tokens, fb.output_tokens, fb.cost_usd = in_tok, out_tok, cost
        return fb
