from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SummaryReq(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None
    when: str = "7d"
    branch: Optional[str] = None
    provider: str = "auto"
    model: Optional[str] = None
    lang: Optional[str] = None
    refresh: bool = True
    insecure: bool = False


class LogReq(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None
    when: str = "7d"
    branch: Optional[str] = None
    refresh: bool = True
    insecure: bool = False


class CompareReq(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None
    period: str = "7d"
    periods: int = 4
    branch: Optional[str] = None
    refresh: bool = True
    insecure: bool = False


class GraphReq(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None
    limit: int = 150
    offset: int = 0
    all_commits: bool = False
    branch: Optional[str] = None
    refresh: bool = True
    insecure: bool = False


class TrackReq(BaseModel):
    url: str
    label: Optional[str] = None


class DashboardReq(BaseModel):
    when: str = "7d"
    summarize: bool = False
    provider: str = "auto"
    model: Optional[str] = None
    lang: Optional[str] = None
    refresh: bool = True
    insecure: bool = False


class CommitMsgReq(BaseModel):
    path: str
    scope: str = "all"                   # "all" | "staged"
    force_type: Optional[str] = None     # feat | fix | refactor | ...
    provider: str = "auto"
    model: Optional[str] = None
    lang: Optional[str] = None
