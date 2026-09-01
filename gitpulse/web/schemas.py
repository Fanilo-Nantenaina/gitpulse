from __future__ import annotations

from pydantic import BaseModel


class SummaryReq(BaseModel):
    path: str | None = None
    url: str | None = None
    when: str = "7d"
    branch: str | None = None
    authors: list[str] | None = None
    provider: str = "auto"
    model: str | None = None
    lang: str | None = None
    refresh: bool = True
    insecure: bool = False


class LogReq(BaseModel):
    path: str | None = None
    url: str | None = None
    when: str = "7d"
    branch: str | None = None
    authors: list[str] | None = None
    refresh: bool = True
    insecure: bool = False


class CompareReq(BaseModel):
    path: str | None = None
    url: str | None = None
    period: str = "7d"
    periods: int = 4
    branch: str | None = None
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
