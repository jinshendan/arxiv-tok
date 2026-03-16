from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Paper:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    published: datetime
    updated: datetime
    url: str


@dataclass(slots=True)
class ScoredPaper:
    paper: Paper
    profile_name: str
    score: int


@dataclass(slots=True)
class SummaryResult:
    summary_cn: str
    highlights: list[str]
    recommendation: str
