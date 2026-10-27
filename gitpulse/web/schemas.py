from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..core.workspace import DEFAULT_DEPTH


class SummaryReq(BaseModel):
    path: str | None = None
    url: str | None = None
    when: str = "7d"
    branch: str | None = None
    authors: list[str] | None = None
    author_scope: Literal["window", "all"] = "window"
    depth: int = DEFAULT_DEPTH
    provider: str = "auto"
    model: str | None = None
    lang: str | None = None
    refresh: bool = True
    insecure: bool = False
    use_cache: bool = True
    risks: bool = True


class LogReq(BaseModel):
    path: str | None = None
    url: str | None = None
    when: str = "7d"
    branch: str | None = None
    authors: list[str] | None = None
    author_scope: Literal["window", "all"] = "window"
    depth: int = DEFAULT_DEPTH
    refresh: bool = True
    insecure: bool = False


class CompareReq(BaseModel):
    path: str | None = None
    url: str | None = None
    period: str = "7d"
    periods: int = 4
    branch: str | None = None
    authors: list[str] | None = None
    author_scope: Literal["window", "all"] = "window"
    depth: int = DEFAULT_DEPTH
    refresh: bool = True
    insecure: bool = False


class GraphReq(BaseModel):
    path: str | None = None
    url: str | None = None
    limit: int = 150
    offset: int = 0
    all_commits: bool = False
    branch: str | None = None
    refresh: bool = True
    insecure: bool = False


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


class SshBrowseReq(BaseModel):
    host: str
    path: str | None = None


class TimesheetReq(BaseModel):
    path: str | None = None
    url: str | None = None
    when: str = "this-week"
    authors: list[str] | None = None
    depth: int = DEFAULT_DEPTH
    gap: int = 120
    warmup: int = 30
    refresh: bool = True
    insecure: bool = False


class WorkspaceReq(BaseModel):
    name: str
    members: list[str]
