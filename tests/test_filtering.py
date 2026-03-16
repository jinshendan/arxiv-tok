from datetime import UTC, datetime

from arxiv_agent.config import KeywordProfile
from arxiv_agent.filtering import filter_and_rank
from arxiv_agent.models import Paper


def _paper(title: str, summary: str) -> Paper:
    now = datetime.now(UTC)
    return Paper(
        paper_id=title[:10],
        title=title,
        summary=summary,
        authors=["a"],
        categories=["cs.CL"],
        published=now,
        updated=now,
        url="https://arxiv.org/abs/0000.00000",
    )


def test_filter_rank_hits() -> None:
    profile = KeywordProfile(
        name="agent",
        include_all=["agent"],
        include_any=["llm", "tool use"],
        exclude_any=["survey"],
        min_score=3,
        max_items_per_run=5,
    )
    papers = [
        _paper("Agentic LLM with Tool Use", "This agent system uses llm and tool use"),
        _paper("Survey on Agents", "A broad survey"),
    ]
    ranked = filter_and_rank(papers, profile)
    assert len(ranked) == 1
    assert ranked[0].paper.title == "Agentic LLM with Tool Use"
