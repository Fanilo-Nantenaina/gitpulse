from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class FileChange:
    """A single file touched within a commit."""
    path: str
    additions: int
    deletions: int
    status: str  # "added" | "modified" | "deleted" | "renamed"

    @property
    def churn(self) -> int:
        return self.additions + self.deletions


@dataclass
class Commit:
    """A normalized git commit, independent of pygit2 internals."""
    sha: str
    author_name: str
    author_email: str
    when: datetime
    summary: str          # first line of the message
    body: str             # rest of the message
    files: list[FileChange] = field(default_factory=list)
    branch: Optional[str] = None

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
    """Aggregated activity for one repository over a time window."""
    repo_name: str
    repo_path: str
    since: datetime
    until: datetime
    commits: list[Commit] = field(default_factory=list)

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
        """Files touched most often = likely tech-debt magnets."""
        counts: dict[str, int] = {}
        for c in self.commits:
            for f in c.files:
                counts[f.path] = counts.get(f.path, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))

    @property
    def hour_histogram(self) -> dict[int, int]:
        """Commits per hour of day (0-23) for the productivity heatmap."""
        hist = {h: 0 for h in range(24)}
        for c in self.commits:
            hist[c.hour] += 1
        return hist
