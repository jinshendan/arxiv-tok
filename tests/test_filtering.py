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


def test_filter_rank_semantic_hit_without_lexical_match() -> None:
    profile = KeywordProfile(
        name="multilingual-rag",
        include_all=[],
        include_any=["retrieval augmented generation"],
        exclude_any=[],
        semantic_queries=["多语言检索增强生成"],
        semantic_min_similarity=0.33,
        semantic_weight=2,
        min_score=1,
        max_items_per_run=5,
    )
    p1 = _paper("Cross-lingual Context Fusion", "A method for multilingual QA over documents")
    p2 = _paper("Graph Sampling Methods", "Pure graph theory with no retrieval setup")

    semantic_scores = {
        p1.paper_id: 0.41,
        p2.paper_id: 0.18,
    }
    ranked = filter_and_rank([p1, p2], profile, semantic_scores=semantic_scores)
    assert len(ranked) == 1
    assert ranked[0].paper.paper_id == p1.paper_id
    assert ranked[0].semantic_similarity == 0.41
    assert ranked[0].score >= ranked[0].base_score
    assert ranked[0].heat_score >= 0
    assert ranked[0].contribution_score >= 0
