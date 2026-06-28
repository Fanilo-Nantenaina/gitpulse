from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass

from ..core.models import RepoActivity
from ..core import config
from . import providers

DEFAULT_MODEL = os.environ.get("GITPULSE_MODEL", "claude-sonnet-4-6")


def _system_prompt(lang_code: str) -> str:
    base = textwrap.dedent(
        """\
        You are a senior engineer writing an activity digest of recent git history.
        The goal is to SUMMARIZE the work clearly first, and only then note anything
        worth flagging. This is a recap, not a performance review.

        NARRATIVE ORDER (important):
        - Tell the story in CHRONOLOGICAL order: oldest first, ending with the most
          recent work. Never narrate backwards. The commit list is given oldest
          first; follow that order.
        - Anchor the story in TIME, not in commit IDs. Refer to days and dates
          ("On the 12th", "early in the week", "the next day", "by Friday") rather
          than to commit SHAs. Do NOT say "commit abc1234 did X" in the prose.

        ATTRIBUTION:
        - Refer to the people by their actual author NAME (given per commit and in
          "Author(s) in this window"). When one author dominates, use their name.
          When several contributed, attribute work to the right person by name.
        - NEVER use generic placeholders like "the developer", "the author", "he",
          "she", or "they" as a stand-in for a named person. Use the real name(s).

        Rules for THEMES:
        - Group related commits into themes by what they actually change.
        - In each narrative, name the concrete artifacts involved: file paths,
          functions, classes, endpoints, dependencies, config keys. Cite the work,
          do not paraphrase it generically. Attribute by author name where relevant.
        - Explain WHY, not just what: the apparent intent and the engineering effect.

        Rules for SYNTHESIS:
        - A thorough, detailed prose overview of the period told as a chronological
          story: what was worked on first, how it progressed day by day, how the
          pieces connect, and where the bulk of the work went. Use author names and
          dates/days. Use as many sentences as the activity warrants. Name concrete
          areas (modules, features, files). Neutral and descriptive.

        Rules for OBSERVATIONS:
        - Optional and secondary. Include only genuinely useful, evidence-backed
          notes, each tied to concrete data: a named file, a count, a sequence, a
          date. (A short_sha may be cited here as evidence, but not in the prose.)
          Neutral facts, positives, or risks - not only criticism.
        - BANNED: vague filler like "may require additional testing", "could
          introduce issues", "consider reviewing". If you cannot tie a note to
          specific evidence, omit it. Zero observations is fine.
        - At most 5 observations.

        Respond ONLY with valid JSON, no markdown fences, in this exact shape:
        {
          "headline": "one sentence naming the main thrust of the period",
          "synthesis": "detailed neutral chronological prose, naming authors and dates",
          "themes": [
            {"title": "Theme name",
             "narrative": "3-5 sentences citing concrete files/symbols, dates, and author names",
             "commits": ["short_sha", ...]}
          ],
          "observations": ["specific, evidence-backed note (optional)", ...]
        }
        """
    )
    name = config.lang_name(lang_code)
    if lang_code != "en":
        base += (
            f"\nWrite all values (headline, synthesis, theme titles, "
            f"narratives, and observations) in {name}. Keep commit "
            f"identifiers, file paths, code symbols, author names, and branch "
            f"names unchanged."
        )
    return base


@dataclass
class Summary:
    headline: str
    themes: list[dict]
    observations: list[str]
    synthesis: str = ""
    raw: str = ""
    source: str = "local"
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
            synthesis=data.get("synthesis", ""),
            themes=data.get("themes", []),
            observations=data.get("observations", []),
            raw=text,
        )


def _build_payload(activity: RepoActivity) -> str:
    seen = []
    for c in activity.commits:
        if c.author_name and c.author_name not in seen:
            seen.append(c.author_name)
    who = ", ".join(seen) if seen else "unknown"

    lines = [
        f"Repository: {activity.repo_name}",
        f"Window: {activity.since:%Y-%m-%d} to {activity.until:%Y-%m-%d}",
        f"Commits: {activity.commit_count}  "
        f"(+{activity.total_additions} / -{activity.total_deletions} lines)",
        f"Author(s) in this window: {who}",
        "",
        "Commits (OLDEST first — narrate the story in THIS order, "
        "from the start of the period to the end):",
    ]
    for c in reversed(activity.commits):
        lines.append(
            f"- [{c.short_sha}] {c.when:%Y-%m-%d %H:%M} "
            f"by {c.author_name}: {c.summary}"
        )
        if c.body:
            for bl in c.body.splitlines():
                bl = bl.strip()
                if bl:
                    lines.append(f"    {bl}")
        if c.files:
            shown = c.files[:15]
            files = ", ".join(f"{f.path}(+{f.additions}/-{f.deletions})" for f in shown)
            extra = f" +{len(c.files) - 15} more" if len(c.files) > 15 else ""
            lines.append(f"    files: {files}{extra}")

    signals = _signals(activity)
    if signals:
        lines.append("")
        lines.append("Precomputed signals (use as evidence; verify against commits):")
        lines.extend(f"- {s}" for s in signals)

    return "\n".join(lines)


def _signals(activity: RepoActivity) -> list[str]:
    out: list[str] = []
    n = activity.commit_count

    hot = [(p, cnt) for p, cnt in activity.hotspots.items() if cnt > 1]
    for path, cnt in hot[:5]:
        shas = [
            c.short_sha
            for c in activity.commits
            if any(f.path == path for f in c.files)
        ]
        out.append(
            f"File {path} changed in {cnt} of {n} commits ({' '.join(shas[:10])})."
        )

    late = [c for c in activity.commits if c.hour >= 22 or c.hour < 6]
    if late:
        out.append(
            f"{len(late)} commit(s) outside working hours: "
            + ", ".join(f"{c.short_sha}@{c.hour:02d}h" for c in late[:8])
            + "."
        )

    fixes = [
        c
        for c in activity.commits
        if c.summary.lower().startswith(("fix", "hotfix", "revert"))
    ]
    if fixes:
        out.append(
            f"{len(fixes)} fix/revert commit(s): "
            + ", ".join(c.short_sha for c in fixes[:10])
            + "."
        )

    big = sorted(activity.commits, key=lambda c: c.churn, reverse=True)[:3]
    big = [c for c in big if c.churn > 200]
    for c in big:
        out.append(
            f"Large commit {c.short_sha} (+{c.additions}/-{c.deletions}, "
            f"{len(c.files)} files): {c.summary}"
        )

    return out


_FALLBACK_STRINGS = {
    "en": {
        "commits_on": "{n} commits on {repo}.",
        "n_commits": "{n} commit(s).",
        "off_hours": "{n} commit(s) outside working hours.",
        "hotspot": "Hotspot: {path} changed {n}x (possible churn).",
        "no_activity": "No activity in this window.",
        "synthesis": "{n} commits across {f} file(s), +{add}/-{dele} lines, "
        "led by {kinds}.",
    },
    "fr": {
        "commits_on": "{n} commits sur {repo}.",
        "n_commits": "{n} commit(s).",
        "off_hours": "{n} commit(s) en dehors des heures de travail.",
        "hotspot": "Point chaud : {path} modifié {n}x (possible instabilité).",
        "no_activity": "Aucune activité sur cette période.",
        "synthesis": "{n} commits sur {f} fichier(s), +{add}/-{dele} lignes, "
        "principalement {kinds}.",
    },
}


def _fb_str(lang: str, key: str, **kw) -> str:
    table = _FALLBACK_STRINGS.get(lang, _FALLBACK_STRINGS["en"])
    return table.get(key, _FALLBACK_STRINGS["en"][key]).format(**kw)


def _local_fallback(activity: RepoActivity, lang: str = "en") -> Summary:
    by_prefix: dict[str, list[str]] = {}
    for c in activity.commits:
        prefix = c.summary.split(":", 1)[0] if ":" in c.summary[:12] else "other"
        by_prefix.setdefault(prefix, []).append(c.short_sha)
    themes = [
        {"title": k, "narrative": _fb_str(lang, "n_commits", n=len(v)), "commits": v}
        for k, v in by_prefix.items()
    ]
    obs = []
    late = [c for c in activity.commits if c.hour >= 22 or c.hour < 6]
    if late:
        obs.append(_fb_str(lang, "off_hours", n=len(late)))
    top = next(iter(activity.hotspots.items()), None)
    if top and top[1] > 1:
        obs.append(_fb_str(lang, "hotspot", path=top[0], n=top[1]))
    kinds = (
        ", ".join(sorted(by_prefix, key=lambda k: len(by_prefix[k]), reverse=True)[:3])
        or "-"
    )
    synthesis = _fb_str(
        lang,
        "synthesis",
        n=activity.commit_count,
        f=activity.files_touched,
        add=activity.total_additions,
        dele=activity.total_deletions,
        kinds=kinds,
    )
    return Summary(
        headline=_fb_str(
            lang, "commits_on", n=activity.commit_count, repo=activity.repo_name
        ),
        synthesis=synthesis,
        themes=themes,
        observations=obs,
    )


def summarize(
    activity: RepoActivity,
    provider: str = "auto",
    model: str | None = None,
    lang: str | None = None,
) -> Summary:
    lang = config.resolve_lang(lang)
    if activity.commit_count == 0:
        return Summary(
            headline=_fb_str(lang, "no_activity"), themes=[], observations=[]
        )

    prov = providers.detect(provider)
    if prov is None:
        return _local_fallback(activity, lang)

    if model:
        setattr(prov, "model", model)

    max_tokens = min(16000, max(4000, activity.commit_count * 170))
    try:
        result = prov.generate(
            _system_prompt(lang), _build_payload(activity), max_tokens
        )
    except Exception as e:
        fb = _local_fallback(activity, lang)
        fb.source = f"local({prov.name}-error)"
        fb.raw = str(e)
        return fb

    if result.truncated:
        fb = _local_fallback(activity, lang)
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
        fb = _local_fallback(activity, lang)
        fb.raw = result.text
        fb.source = f"local({prov.name}-parse-failed)"
        fb.input_tokens, fb.output_tokens, fb.cost_usd = (
            result.input_tokens,
            result.output_tokens,
            result.cost_usd,
        )
        return fb
