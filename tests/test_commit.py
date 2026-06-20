from __future__ import annotations

from gitpulse.core.diffstage import collect_working_changes
from gitpulse.ai.commitmsg import generate_commit_message, _apply_type


def test_collect_all_scope_includes_staged_and_untracked(dirty_repo):
    wc = collect_working_changes(dirty_repo, scope="all")
    paths = {f.path for f in wc.files}
    assert "app.py" in paths
    assert "config.py" in paths
    assert "notes.md" in paths
    assert wc.has_changes


def test_collect_staged_scope_only_index(dirty_repo):
    wc = collect_working_changes(dirty_repo, scope="staged")
    paths = {f.path for f in wc.files}
    assert paths == {"app.py"}


def test_collect_tracks_line_counts(dirty_repo):
    wc = collect_working_changes(dirty_repo, scope="staged")
    app = next(f for f in wc.files if f.path == "app.py")
    assert app.status == "modified"
    assert app.additions >= 1


def test_commit_message_local_fallback(dirty_repo):
    wc = collect_working_changes(dirty_repo, scope="all")
    msg = generate_commit_message(wc, provider="local")
    assert msg.subject
    assert msg.bullets
    assert msg.source == "local"


def test_commit_message_force_type(dirty_repo):
    wc = collect_working_changes(dirty_repo, scope="all")
    msg = generate_commit_message(wc, provider="local", force_type="feat")
    assert msg.subject.startswith("feat")


def test_apply_type_preserves_scope():
    assert _apply_type("chore(api): update stuff", "feat") == "feat(api): update stuff"
    assert _apply_type("add a thing", "fix") == "fix: add a thing"


def test_no_changes_returns_empty(linear_repo):
    wc = collect_working_changes(linear_repo, scope="all")
    assert not wc.has_changes
    msg = generate_commit_message(wc, provider="local")
    assert msg.subject == ""
