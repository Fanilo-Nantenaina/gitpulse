from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass

from ..core.models import RepoActivity
from . import providers

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
        if self.source.startswith("local"):
            if self.input_tokens or self.output_tokens:
                return (
                    f"{self.source} · {self.input_tokens}+{self.output_tokens} tok "
                    f"· $0.0000"
                )
            return "local fallback (no model call, $0.00)"
        cost = f"${self.cost_usd:.4f}" if self.cost_usd else "free"
        return (
            f"{self.source} · {self.input_tokens}+{self.output_tokens} tok " f"· {cost}"
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


def summarize(
    activity: RepoActivity, provider: str = "auto", model: str | None = None
) -> Summary:
    if activity.commit_count == 0:
        return Summary(
            headline="No activity in this window.", themes=[], observations=[]
        )

    prov = providers.detect(provider)
    if prov is None:
        return _local_fallback(activity)

    if model:
        setattr(prov, "model", model)

    max_tokens = min(8000, max(2000, activity.commit_count * 90))
    try:
        result = prov.generate(_SYSTEM, _build_payload(activity), max_tokens)
    except Exception as e:
        fb = _local_fallback(activity)
        fb.source = f"local({prov.name}-error)"
        fb.raw = str(e)
        return fb

    if result.truncated:
        fb = _local_fallback(activity)
        fb.raw = result.text
        fb.source = f"local({prov.name}-truncated)"
        fb.input_tokens, fb.output_tokens, fb.cost_usd = (
            result.input_tokens,
            result.output_tokens,
            result.cost_usd,
        )
        return fb

    try:
        summ = Summary.from_json(result.text)
        summ.source = f"{prov.name}:{result.model}"
        summ.input_tokens, summ.output_tokens, summ.cost_usd = (
            result.input_tokens,
            result.output_tokens,
            result.cost_usd,
        )
        return summ
    except (json.JSONDecodeError, KeyError):
        fb = _local_fallback(activity)
        fb.raw = result.text
        fb.source = f"local({prov.name}-parse-failed)"
        fb.input_tokens, fb.output_tokens, fb.cost_usd = (
            result.input_tokens,
            result.output_tokens,
            result.cost_usd,
        )
        return fb
