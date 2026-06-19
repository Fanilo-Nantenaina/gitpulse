from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import providers
from ..core import config
from ..core.diffstage import WorkingChanges


@dataclass
class CommitMessage:
    subject: str                          # one-line Conventional Commits summary
    bullets: list[str] = field(default_factory=list)
    source: str = "local"
    raw: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def full_text(self) -> str:
        body = "\n".join(f"- {b}" for b in self.bullets)
        return f"{self.subject}\n\n{body}" if body else self.subject


_TYPES = "feat, fix, refactor, docs, style, test, chore, perf, build, ci"


def _system_prompt(lang: str) -> str:
    base = (
        "You write git commit messages from a diff. Output STRICT JSON only, no "
        "markdown, no prose around it. Schema:\n"
        '{"subject": "<type>(<optional scope>): <imperative summary, <=72 chars>", '
        '"bullets": ["concise change 1", "concise change 2", ...]}\n'
        f"Use Conventional Commits types: {_TYPES}. The subject is ONE line, "
        "imperative mood ('add', not 'added'), no trailing period. Each bullet "
        "describes one concrete change, grounded in the diff — never invent "
        "changes that aren't present. 2-6 bullets typically; fewer for small "
        "diffs. Be specific (mention files/functions/behavior) but concise."
    )
    if lang == "fr":
        base += ("\nWrite the subject and bullets in French (imperative: "
                 "'ajoute', 'corrige', 'refactorise'). Keep the Conventional "
                 "Commits type in English (feat, fix, ...).")
    return base


def _build_payload(changes: WorkingChanges) -> str:
    lines = [f"Repository: {changes.repo_name}",
             f"Scope: {changes.scope}",
             f"Files changed ({len(changes.files)}):"]
    for f in changes.files:
        lines.append(f"  {f.status}: {f.path} (+{f.additions}/-{f.deletions})")
    lines.append("\nDiff:\n")
    lines.append(changes.diff_text)
    if changes.truncated:
        lines.append("\n[Note: diff was truncated; summarize what is visible.]")
    return "\n".join(lines)


def _local_fallback(changes: WorkingChanges, lang: str) -> CommitMessage:
    # Heuristic message when no model is available.
    n = len(changes.files)
    by_status: dict[str, int] = {}
    for f in changes.files:
        by_status[f.status] = by_status.get(f.status, 0) + 1
    if lang == "fr":
        subject = f"chore: mise à jour de {n} fichier{'s' if n > 1 else ''}"
        verbs = {"added": "ajout", "modified": "modification",
                 "deleted": "suppression", "untracked": "nouveau",
                 "renamed": "renommage"}
    else:
        subject = f"chore: update {n} file{'s' if n > 1 else ''}"
        verbs = {"added": "add", "modified": "modify", "deleted": "delete",
                 "untracked": "new", "renamed": "rename"}
    bullets = [f"{f.path} ({verbs.get(f.status, f.status)}, +{f.additions}/-{f.deletions})"
               for f in changes.files[:8]]
    return CommitMessage(subject=subject, bullets=bullets, source="local")


def _parse(text: str) -> CommitMessage:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if "```" in cleaned[3:] else cleaned[3:]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]
    data = json.loads(cleaned)
    subject = str(data["subject"]).strip()
    bullets = [str(b).strip().lstrip("-• ").strip() for b in data.get("bullets", [])]
    return CommitMessage(subject=subject, bullets=[b for b in bullets if b])


def generate_commit_message(changes: WorkingChanges, provider: str = "auto",
                            model: str | None = None, lang: str | None = None,
                            force_type: str | None = None) -> CommitMessage:
    lang = config.resolve_lang(lang)
    if not changes.has_changes:
        return CommitMessage(subject="", bullets=[], source="none")

    prov = providers.detect(provider)
    if prov is None:
        msg = _local_fallback(changes, lang)
        if force_type:
            msg.subject = _apply_type(msg.subject, force_type)
        return msg
    if model:
        setattr(prov, "model", model)

    system = _system_prompt(lang)
    if force_type:
        system += (f"\nThe commit type MUST be '{force_type}'. Start the subject "
                   f"with '{force_type}'.")

    max_tokens = 1200
    try:
        result = prov.generate(system, _build_payload(changes), max_tokens)
    except Exception as e:
        fb = _local_fallback(changes, lang)
        if force_type:
            fb.subject = _apply_type(fb.subject, force_type)
        fb.source = f"local({prov.name}-error)"
        fb.raw = str(e)
        return fb

    try:
        msg = _parse(result.text)
        if force_type:
            msg.subject = _apply_type(msg.subject, force_type)
        msg.source = f"{prov.name}:{result.model}"
        msg.input_tokens, msg.output_tokens, msg.cost_usd = (
            result.input_tokens, result.output_tokens, result.cost_usd)
        return msg
    except (json.JSONDecodeError, KeyError, ValueError):
        fb = _local_fallback(changes, lang)
        if force_type:
            fb.subject = _apply_type(fb.subject, force_type)
        fb.raw = result.text
        fb.source = f"local({prov.name}-parse-failed)"
        return fb


def _apply_type(subject: str, force_type: str) -> str:
    """Rewrite the subject's type prefix to force_type, preserving scope/text."""
    rest = subject
    # strip an existing "type(scope): " or "type: " prefix
    if ":" in subject:
        head, tail = subject.split(":", 1)
        head = head.strip()
        # head looks like a conventional type (optionally with scope)
        base = head.split("(")[0].strip()
        known = {t.strip() for t in _TYPES.split(",")}
        if base in known:
            scope = ""
            if "(" in head and ")" in head:
                scope = head[head.find("("):head.find(")") + 1]
            return f"{force_type}{scope}: {tail.strip()}"
    return f"{force_type}: {rest.strip()}"
