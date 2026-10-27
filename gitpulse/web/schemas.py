from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..core.refs import ALL_BRANCHES, BranchSpec
from ..core.workspace import DEFAULT_DEPTH


class SourceReq(BaseModel):

    path: str | None = None
    url: str | None = None
    refresh: bool = True
    force: bool = False
    insecure: bool = False


class ScopeReq(SourceReq):

    when: str = "7d"
    branches: list[str] | None = None
    branch: str | None = None
    authors: list[str] | None = None
    author_scope: Literal["window", "all"] = "window"
    depth: int = DEFAULT_DEPTH

    def branch_spec(self) -> BranchSpec:
        if self.branches is not None:
            return self.branches
        return self.branch


class SummaryReq(ScopeReq):
    provider: str = "auto"
    model: str | None = None
    lang: str | None = None
    use_cache: bool = True
    risks: bool = True


class LogReq(ScopeReq):
    pass


class CompareReq(ScopeReq):
    period: str = "7d"
    periods: int = 4


class GraphReq(SourceReq):
    limit: int = 150
    offset: int = 0
    branches: list[str] | None = None
    branch: str | None = None
    uncommitted: bool = False
    version: str | None = None
    refresh: bool = False


class CommitReq(SourceReq):
    sha: str
    refresh: bool = False


class CommitDiffReq(CommitReq):
    file: str


class TrackReq(BaseModel):
    url: str
    label: str | None = None


class DashboardReq(BaseModel):
    when: str = "7d"
    summarize: bool = False
    provider: str = "auto"
    model: str | None = None
    lang: str | None = None
    refresh: bool = True
    insecure: bool = False


class CommitMsgReq(BaseModel):
    path: str
    scope: str = "all"
    force_type: str | None = None
    provider: str = "auto"
    model: str | None = None
    lang: str | None = None


class ChangesCountReq(BaseModel):
    path: str | None = None


class BranchesReq(SourceReq):
    include_remote: bool = False
    refresh: bool = False


class LangReq(BaseModel):
    lang: str | None = None


class KeyReq(BaseModel):
    provider: str
    key: str = ""


class SshBrowseReq(BaseModel):
    host: str
    path: str | None = None


class TimesheetReq(ScopeReq):
    when: str = "this-week"
    gap: int = 120
    warmup: int = 30

    def branch_spec(self) -> BranchSpec:
        spec = super().branch_spec()
        return ALL_BRANCHES if spec is None else spec


class WorkspaceReq(BaseModel):
    name: str
    members: list[str]
