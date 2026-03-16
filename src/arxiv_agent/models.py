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
class ImpactSignal:
    heat_score: int = 0
    contribution_score: int = 0
    citation_count: int = 0
    influential_citation_count: int = 0
    reference_count: int = 0
    citation_velocity: float = 0.0
    source: str = "none"


@dataclass(slots=True)
class ScoredPaper:
    paper: Paper
    profile_name: str
    score: int
    base_score: int = 0
    heat_score: int = 0
    contribution_score: int = 0
    citation_count: int = 0
    influential_citation_count: int = 0
    reference_count: int = 0
    citation_velocity: float = 0.0
    impact_source: str = "none"
    semantic_similarity: float | None = None


@dataclass(slots=True)
class SummaryResult:
    summary_cn: str
    highlights: list[str]
    recommendation: str
