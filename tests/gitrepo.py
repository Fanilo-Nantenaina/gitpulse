
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str, date: str | None = None) -> str:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Tester",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Tester",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


class Repo:

    def __init__(self, path: Path) -> None:
        self.path = path
        path.mkdir()
        _git(path, "init", "-q")
        _git(path, "symbolic-ref", "HEAD", "refs/heads/main")
        self.hour = 0

    def _date(self, hour: int | None) -> str:
        if hour is None:
            self.hour += 1
            hour = self.hour
        return f"2026-01-{1 + hour // 24:02d}T{hour % 24:02d}:00:00+00:00"

    def __call__(self, *args: str) -> str:
        return _git(self.path, *args)

    def commit(self, msg: str, hour: int | None = None) -> str:
        _git(
            self.path,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            msg,
            date=self._date(hour),
        )
        return self("rev-parse", "HEAD")

    def merge(self, *revs: str, msg: str = "merge", hour: int | None = None) -> str:
        _git(
            self.path, "merge", "-q", "--no-ff", "-m", msg, *revs, date=self._date(hour)
        )
        return self("rev-parse", "HEAD")
