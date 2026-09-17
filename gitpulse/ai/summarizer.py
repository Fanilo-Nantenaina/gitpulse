from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass
from typing import TypedDict

from ..core import collector, config
from ..core.jsonio import JsonValue
from ..core.models import Commit, RepoActivity, qualified_path
from . import providers

DEFAULT_MODEL = os.environ.get("GITPULSE_MODEL", providers.DEFAULT_CLAUDE_MODEL)


def _system_prompt(lang_code: str) -> str:
    base = textwrap.dedent(
        """\
        You are a senior engineer writing an activity digest of recent git history.
        The goal is to SUMMARIZE the work clearly first, and only then note anything
        worth flagging. This is a recap, not a performance review.

        DEPTH — this is what separates a good digest from a useless one:
        - Describe the ENGINEERING SUBSTANCE: the capabilities, subsystems and
          mechanisms that were built or changed, in the project's own domain
          terms. Name them the way the codebase names them.
        - Read the commit bodies, file paths and (when given) the diff excerpts,
          and extract the specific things introduced: the new fields, functions,
          classes, schemas, endpoints, config keys, validation rules, data flows.
        - BANNED as a description of work: bare conventional-commit labels and
          empty umbrella words — "feat work", "several refactors", "various
          improvements", "code cleanup", "better structure", "enhanced quality".
          These say nothing. Every clause must carry a fact a reader could not
          have guessed from the commit count alone.
        - Weak (do not write this): "Several feat and refactor commits improved
          the API and cleaned up the code."
          Strong (write like this): "Schema drift detection was reworked to emit
          human-readable field paths, keep a history of previous versions, and
          mark schemas as applied; route handlers moved to typed
          ApiResponse[T] envelopes and DELETE endpoints gained structured
          response models."

        MULTIPLE REPOSITORIES:
        - The payload may cover a WORKSPACE: several independent repositories
          analysed together. When it does, each commit line is tagged with its
          repository in parentheses.
        - Never blend them into one imaginary project. Say which repository
          each piece of work happened in, and name the repositories.
        - Organise themes by repository when the work is unrelated across
          them; use a cross-repo theme only when the same effort genuinely
          spans several (a shared API contract, a coordinated rename).
        - The synthesis should say where the effort concentrated — which
          repositories were busy, which were quiet, and whether anything
          connects them.

        NARRATIVE ORDER:
        - The commit list is given oldest first; follow that order when the
          sequence matters. Anchor the story in TIME, not in commit IDs — refer
          to days and dates rather than SHAs. Do NOT say "commit abc1234 did X"
          in the prose.
        - Chronology is scaffolding, not the point: never let a date-by-date
          walkthrough replace the technical substance above.

        ATTRIBUTION:
        - Refer to people by their actual author NAME (given per commit and in
          "Author(s) in this window"), not "the developer" or "they". When a
          single author wrote everything, name them once — do not repeat the
          name in every sentence at the expense of content.

        Rules for THEMES:
        - Group related commits into themes by the capability or subsystem they
          change — name the theme after that ("Schema drift tracking", "Auth
          token rotation"), not after a commit type ("feat", "refactor").
        - In each narrative, name the concrete artifacts involved: file paths,
          functions, classes, endpoints, dependencies, config keys, and what
          they now do differently. Cite the work, do not paraphrase it
          generically.
        - Explain WHY, not just what: the apparent intent and the engineering
          effect (what got built, safer, faster, simpler).

        Rules for SYNTHESIS:
        - A thorough, detailed prose overview of the period: which capabilities
          and subsystems the work centred on, what was actually introduced or
          reworked inside them, how the pieces connect, and where the bulk of
          the effort went. Lead with the substance; weave in sequence and author
          names where they add information.
        - Use as many sentences as the activity warrants — a busy period
          deserves a full paragraph or more. Neutral and descriptive.

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
          "headline": "one sentence naming the specific capability or subsystem the period centred on",
          "synthesis": "detailed prose: the capabilities and subsystems worked on and what was concretely introduced or reworked inside them",
          "themes": [
            {"title": "Capability or subsystem name, not a commit type",
             "narrative": "3-5 sentences citing concrete files/symbols/fields and what they now do differently",
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


class Theme(TypedDict):
    title: str
    narrative: str
    commits: list[str]


def _coerce_theme(value: JsonValue) -> Theme | None:
    if isinstance(value, str):
        return {"title": value, "narrative": "", "commits": []} if value else None
    if not isinstance(value, dict):
        return None
    title = value.get("title")
    if not isinstance(title, str) or not title:
        return None
    narrative = value.get("narrative")
    commits = value.get("commits")
    return {
        "title": title,
        "narrative": narrative if isinstance(narrative, str) else "",
        "commits": (
            [c for c in commits if isinstance(c, str)]
            if isinstance(commits, list)
            else []
        ),
    }


@dataclass
class Summary:
    headline: str
    themes: list[Theme]
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
        return f"{self.source} · {self.input_tokens}+{self.output_tokens} tok · {cost}"

    @classmethod
    def from_json(cls, text: str) -> Summary:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            text = text.removeprefix("json")
        data: JsonValue = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("summary response was not a JSON object")
        headline = data.get("headline")
        synthesis = data.get("synthesis")
        raw_themes = data.get("themes")
        themes: list[Theme] = []
        themes_valid = isinstance(raw_themes, list)
        for x in raw_themes if isinstance(raw_themes, list) else []:
            theme = _coerce_theme(x)
            if theme is None:
                themes_valid = False
                break
            themes.append(theme)
        if (
            not isinstance(headline, str)
            or not headline
            or not isinstance(synthesis, str)
            or not synthesis
            or not themes_valid
        ):
            raise ValueError(
                "summary response did not match the expected schema "
                "(missing headline/synthesis, or themes are not "
                "{title, narrative, commits} objects)"
            )
        raw_observations = data.get("observations")
        observations: list[str] = []
        if isinstance(raw_observations, list):
            strings = [o for o in raw_observations if isinstance(o, str)]
            if len(strings) == len(raw_observations):
                observations = strings
        return cls(
            headline=headline,
            synthesis=synthesis,
            themes=themes,
            observations=observations,
            raw=text,
        )


MAX_PAYLOAD_COMMITS = 300
DIFF_EXCERPT_COMMITS = 6
DIFF_EXCERPT_CHARS = 2000


def _build_payload(activity: RepoActivity) -> str:
    seen: list[str] = []
    for c in activity.commits:
        if c.author_name and c.author_name not in seen:
            seen.append(c.author_name)
    who = ", ".join(seen) if seen else "unknown"

    commits = activity.commits
    omitted = max(0, len(commits) - MAX_PAYLOAD_COMMITS)
    if omitted:
        commits = commits[:MAX_PAYLOAD_COMMITS]

    if activity.is_workspace:
        per_repo = activity.commits_per_repo
        listed = ", ".join(f"{name} ({n})" for name, n in per_repo.items())
        lines = [
            f"Workspace: {activity.repo_name} — {len(activity.repos)} repositories "
            "analysed together, NOT one project.",
            f"Repositories (commits in window): {listed}",
        ]
    else:
        lines = [f"Repository: {activity.repo_name}"]
    lines += [
        f"Window: {activity.since:%Y-%m-%d} to {activity.until:%Y-%m-%d}",
        f"Commits: {activity.commit_count}  "
        f"(+{activity.total_additions} / -{activity.total_deletions} lines)",
        f"Author(s) in this window: {who}",
    ]
    if omitted:
        lines.append(
            f"(Showing the {MAX_PAYLOAD_COMMITS} most recent commits below; "
            f"{omitted} older commit(s) from this window are not listed "
            "individually, but are included in the totals above.)"
        )
    lines.append("")
    lines.append(
        "Commits (OLDEST first — narrate the story in THIS order, "
        "from the start of the period to the end):"
    )
    for c in reversed(commits):
        where = f" ({c.repo})" if c.repo else ""
        lines.append(
            f"- [{c.short_sha}]{where} {c.when:%Y-%m-%d %H:%M} "
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
        lines.append(
            "Precomputed signals (cite as evidence inside your narrative; "
            "do not return this list itself, and do not invent your own "
            "data fields from it):"
        )
        lines.extend(f"- {s}" for s in signals)

    lines.extend(_diff_section(activity, commits))

    lines.append("")
    lines.append(
        "Reminder: reply with ONLY the JSON object from the system prompt "
        "(the headline/synthesis/themes/observations shape) — prose "
        "written from everything above, not a restatement of the commits "
        "or signals in a different structure."
    )

    return "\n".join(lines)


def _diff_section(activity: RepoActivity, commits: list[Commit]) -> list[str]:
    candidates = [c for c in commits if not c.is_merge and c.churn > 0]
    notable = sorted(candidates, key=lambda c: c.churn, reverse=True)[
        :DIFF_EXCERPT_COMMITS
    ]
    if not notable or not activity.repo_path:
        return []

    by_repo: dict[str, list[str]] = {}
    for c in notable:
        by_repo.setdefault(c.repo_path or activity.repo_path, []).append(c.sha)

    excerpts: dict[str, str] = {}
    for repo_path, shas in by_repo.items():
        try:
            excerpts.update(
                collector.diff_excerpts(
                    repo_path, shas, max_chars_each=DIFF_EXCERPT_CHARS
                )
            )
        except Exception:
            continue
    if not excerpts:
        return []

    out = [
        "",
        "Diff excerpts from the largest commits. Mine these for the CONCRETE "
        "technical substance of the work — the actual function, class, field, "
        "schema, endpoint and config names being introduced or changed. Your "
        "themes and synthesis must describe what these changes DO, in domain "
        "terms, not restate the commit subjects and not settle for generic "
        "labels like 'refactoring' or 'improvements':",
    ]
    for c in notable:
        text = excerpts.get(c.sha)
        if not text:
            continue
        where = f" ({c.repo})" if c.repo else ""
        out.append(f"--- [{c.short_sha}]{where} {c.summary} ---")
        out.append(text)
    return out if len(out) > 1 else []


def _signals(activity: RepoActivity) -> list[str]:
    out: list[str] = []
    n = activity.commit_count

    hot = [(p, cnt) for p, cnt in activity.hotspots.items() if cnt > 1]
    for path, cnt in hot[:5]:
        shas = [
            c.short_sha
            for c in activity.commits
            if any(qualified_path(c, f) == path for f in c.files)
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
        "commits_across": "{n} commits across {r} repo(s) in {repo}.",
        "n_commits": "{n} commit(s).",
        "off_hours": "{n} commit(s) outside working hours.",
        "hotspot": "Hotspot: {path} changed {n}x (possible churn).",
        "no_activity": "No activity in this window.",
        "synthesis": "{n} commits across {f} file(s), +{add}/-{dele} lines, "
        "led by {kinds}.",
    },
    "fr": {
        "commits_on": "{n} commits sur {repo}.",
        "commits_across": "{n} commits répartis sur {r} dépôt(s) dans {repo}.",
        "n_commits": "{n} commit(s).",
        "off_hours": "{n} commit(s) en dehors des heures de travail.",
        "hotspot": "Point chaud : {path} modifié {n}x (possible instabilité).",
        "no_activity": "Aucune activité sur cette période.",
        "synthesis": "{n} commits sur {f} fichier(s), +{add}/-{dele} lignes, "
        "principalement {kinds}.",
    },
}


def _fb_str(lang: str, key: str, **kw: object) -> str:
    table = _FALLBACK_STRINGS.get(lang, _FALLBACK_STRINGS["en"])
    return table.get(key, _FALLBACK_STRINGS["en"][key]).format(**kw)


def _local_fallback(activity: RepoActivity, lang: str = "en") -> Summary:
    by_prefix: dict[str, list[str]] = {}
    for c in activity.commits:
        prefix = c.summary.split(":", 1)[0] if ":" in c.summary[:12] else "other"
        by_prefix.setdefault(prefix, []).append(c.short_sha)
    if activity.is_workspace:
        by_repo: dict[str, list[str]] = {}
        for c in activity.commits:
            by_repo.setdefault(c.repo or activity.repo_name, []).append(c.short_sha)
        themes: list[Theme] = [
            {
                "title": k,
                "narrative": _fb_str(lang, "n_commits", n=len(v)),
                "commits": v,
            }
            for k, v in sorted(by_repo.items(), key=lambda kv: -len(kv[1]))
        ]
    else:
        themes = [
            {
                "title": k,
                "narrative": _fb_str(lang, "n_commits", n=len(v)),
                "commits": v,
            }
            for k, v in by_prefix.items()
        ]
    obs: list[str] = []
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
    if activity.is_workspace:
        headline = _fb_str(
            lang,
            "commits_across",
            n=activity.commit_count,
            r=len(activity.active_repos) or len(activity.repos),
            repo=activity.repo_name,
        )
    else:
        headline = _fb_str(
            lang, "commits_on", n=activity.commit_count, repo=activity.repo_name
        )
    return Summary(
        headline=headline,
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
        prov.model = model

    max_tokens = min(16000, max(4000, activity.commit_count * 170))
    system = _system_prompt(lang)
    payload = _build_payload(activity)

    for attempt in range(2):
        try:
            result = prov.generate(system, payload, max_tokens)
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
        except (ValueError, KeyError):
            if attempt == 0:
                payload += (
                    "\n\nYour previous reply did not match the required "
                    "JSON shape. It started with:\n"
                    f"{result.text[:300]}\n\n"
                    "Reply again with ONLY the JSON object described above "
                    "(headline, synthesis, themes: "
                    "[{title, narrative, commits}], observations) - no other "
                    "structure, no markdown fences."
                )
                continue
            fb = _local_fallback(activity, lang)
            fb.raw = result.text
            fb.source = f"local({prov.name}-parse-failed)"
            fb.input_tokens, fb.output_tokens, fb.cost_usd = (
                result.input_tokens,
                result.output_tokens,
                result.cost_usd,
            )
            return fb

    raise AssertionError("summarize() retry loop completed without a result")
