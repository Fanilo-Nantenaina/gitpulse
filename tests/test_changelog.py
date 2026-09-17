from __future__ import annotations

from pathlib import Path

import pytest

from gitpulse.core.changelog import generate_changelog


def test_generate_changelog_linear(linear_repo: Path) -> None:
    text = generate_changelog(str(linear_repo), from_ref=None, to_ref="HEAD")
    assert "## HEAD" in text


def test_generate_changelog_conventional(tmp_path: Path) -> None:
    import subprocess

    repo = tmp_path / "conv_repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], check=True)

    def commit(msg: str, filename: str) -> None:
        (repo / filename).write_text("content\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "commit",
                "-m",
                msg,
                "--author=Tester <t@example.com>",
            ],
            check=True,
            capture_output=True,
        )

    commit("feat(auth): add login flow", "file1.txt")
    p = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    from_ref = p.stdout.strip()

    commit("fix(api): handle 404 errors properly", "file2.txt")
    commit(
        "feat!: redesign core architecture\n\nBREAKING CHANGE: api altered", "file3.txt"
    )

    cl = generate_changelog(str(repo), from_ref=from_ref, to_ref="HEAD")
    assert "### Features" in cl
    assert "add login flow" not in cl
    assert "### Bug Fixes" in cl
    assert "handle 404 errors properly" in cl
    assert "### ⚠ BREAKING CHANGES" in cl
    assert "redesign core architecture" in cl


def test_generate_changelog_invalid_repo(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No git repository found"):
        generate_changelog(str(tmp_path / "does_not_exist"), from_ref=None)
