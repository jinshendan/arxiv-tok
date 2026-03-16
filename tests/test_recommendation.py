from datetime import UTC, datetime

from arxiv_agent.models import Paper, ScoredPaper
from arxiv_agent.recommendation import localize_recommendation, recommendation_code_from_score


def _paper() -> Paper:
    now = datetime.now(UTC)
    return Paper(
        paper_id="2603.00001v1",
        title="A Paper",
        summary="abstract",
        authors=["a"],
        categories=["cs.AI"],
        published=now,
        updated=now,
        url="https://arxiv.org/abs/2603.00001",
    )


def test_recommendation_must_read_for_high_score() -> None:
    scored = ScoredPaper(
        paper=_paper(),
        profile_name="p",
        score=18,
        base_score=8,
        heat_score=4,
        contribution_score=6,
        impact_source="semantic_scholar",
    )
    code = recommendation_code_from_score(scored)
    assert code == "must_read"
    assert localize_recommendation(code, "zh") == "建议阅读"


def test_recommendation_skip_for_low_score() -> None:
    scored = ScoredPaper(
        paper=_paper(),
        profile_name="p",
        score=3,
        base_score=2,
        heat_score=1,
        contribution_score=1,
        impact_source="semantic_scholar",
    )
    code = recommendation_code_from_score(scored)
    assert code == "skip_for_now"
    assert localize_recommendation(code, "en") == "Skip for now"
