from __future__ import annotations

from .config import KeywordProfile
from .models import Paper, ScoredPaper


def _contains(text: str, token: str) -> bool:
    return token.lower() in text


def score_paper(paper: Paper, profile: KeywordProfile) -> int:
    haystack = f"{paper.title}\n{paper.summary}".lower()

    if any(_contains(haystack, t.lower()) for t in profile.exclude_any):
        return -1

    score = 0
    for token in profile.include_all:
        if not _contains(haystack, token.lower()):
            return -1
        score += 2

    if profile.include_any:
        any_hits = [t for t in profile.include_any if _contains(haystack, t.lower())]
        if not any_hits:
            return -1
        score += len(any_hits)

    return score


def filter_and_rank(papers: list[Paper], profile: KeywordProfile) -> list[ScoredPaper]:
    scored: list[ScoredPaper] = []
    for paper in papers:
        score = score_paper(paper, profile)
        if score >= profile.min_score:
            scored.append(ScoredPaper(paper=paper, profile_name=profile.name, score=score))
    scored.sort(key=lambda x: (x.score, x.paper.published), reverse=True)
    return scored[: profile.max_items_per_run]
