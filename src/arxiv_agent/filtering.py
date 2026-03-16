from __future__ import annotations

from .config import KeywordProfile
from .models import ImpactSignal, Paper, ScoredPaper


def _contains(text: str, token: str) -> bool:
    return token.lower() in text


def score_paper(paper: Paper, profile: KeywordProfile) -> tuple[int, bool]:
    haystack = f"{paper.title}\n{paper.summary}".lower()

    if any(_contains(haystack, t.lower()) for t in profile.exclude_any):
        return -1, False

    score = 0
    for token in profile.include_all:
        if not _contains(haystack, token.lower()):
            return 0, False
        score += 2

    if profile.include_any:
        any_hits = [t for t in profile.include_any if _contains(haystack, t.lower())]
        if not any_hits:
            return 0, False
        score += len(any_hits)

    return score, True


def filter_and_rank(
    papers: list[Paper],
    profile: KeywordProfile,
    semantic_scores: dict[str, float] | None = None,
    impact_scores: dict[str, ImpactSignal] | None = None,
) -> list[ScoredPaper]:
    semantic_scores = semantic_scores or {}
    impact_scores = impact_scores or {}
    scored: list[ScoredPaper] = []
    for paper in papers:
        score, lexical_ok = score_paper(paper, profile)
        if score < 0:
            continue

        similarity = semantic_scores.get(paper.paper_id)
        semantic_ok = similarity is not None and similarity >= profile.semantic_min_similarity
        if not lexical_ok and not semantic_ok:
            continue

        if semantic_ok:
            score += int(round(similarity * 10 * profile.semantic_weight))

        base_score = score
        impact = impact_scores.get(paper.paper_id, ImpactSignal())
        score += int(round(impact.heat_score * profile.heat_weight + impact.contribution_score * profile.contribution_weight))

        if score >= profile.min_score:
            scored.append(
                ScoredPaper(
                    paper=paper,
                    profile_name=profile.name,
                    score=score,
                    base_score=base_score,
                    heat_score=impact.heat_score,
                    contribution_score=impact.contribution_score,
                    citation_count=impact.citation_count,
                    influential_citation_count=impact.influential_citation_count,
                    reference_count=impact.reference_count,
                    citation_velocity=impact.citation_velocity,
                    impact_source=impact.source,
                    semantic_similarity=similarity if semantic_ok else None,
                )
            )

    scored.sort(
        key=lambda x: (x.score, x.semantic_similarity or 0.0, x.paper.published),
        reverse=True,
    )
    return scored[: profile.max_items_per_run]
