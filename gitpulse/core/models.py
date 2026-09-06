from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FileChange:
    path: str
    additions: int
    deletions: int
    status: str

    @property
    def churn(self) -> int:
        return self.additions + self.deletions


@dataclass
class Commit:
    sha: str
    author_name: str
    author_email: str
    when: datetime
    summary: str
    body: str
    files: list[FileChange] = field(default_factory=list[FileChange])
    branch: str | None = None
    is_merge: bool = False

    @property
    def short_sha(self) -> str:
        return self.sha[:8]

    @property
    def additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def deletions(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def churn(self) -> int:
        return self.additions + self.deletions

    @property
    def hour(self) -> int:
        return self.when.hour


@dataclass
class RepoActivity:
    repo_name: str
    repo_path: str
    since: datetime
    until: datetime
    commits: list[Commit] = field(default_factory=list[Commit])

    @property
    def commit_count(self) -> int:
        return len(self.commits)

    @property
    def total_additions(self) -> int:
        return sum(c.additions for c in self.commits)

    @property
    def total_deletions(self) -> int:
        return sum(c.deletions for c in self.commits)

    @property
    def authors(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.commits:
            counts[c.author_name] = counts.get(c.author_name, 0) + 1
        return counts

    @property
    def hotspots(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.commits:
            for f in c.files:
                counts[f.path] = counts.get(f.path, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))

    @property
    def hour_histogram(self) -> dict[int, int]:
        hist = dict.fromkeys(range(24), 0)
        for c in self.commits:
            hist[c.hour] += 1
        return hist

    @property
    def files_touched(self) -> int:
        seen: set[str] = set()
        for c in self.commits:
            for f in c.files:
                seen.add(f.path)
        return len(seen)

    @property
    def active_days(self) -> int:
        return len({c.when.date() for c in self.commits})
