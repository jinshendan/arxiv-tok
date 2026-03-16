from datetime import UTC, datetime

from arxiv_agent.config import KeywordProfile, KeywordRules, Settings
from arxiv_agent.models import Paper, SummaryResult
from arxiv_agent.search_service import run_search


def _sample_paper() -> Paper:
    now = datetime.now(UTC)
    return Paper(
        paper_id="2603.00001v1",
        title="Agentic Methods",
        summary="agent llm tool use",
        authors=["a"],
        categories=["cs.AI"],
        published=now,
        updated=now,
        url="https://arxiv.org/abs/2603.00001",
    )


def test_run_search_respects_stop_signal(monkeypatch) -> None:
    monkeypatch.setattr(
        "arxiv_agent.arxiv_client.ArxivClient.fetch_recent",
        lambda self, categories, max_results_per_category, lookback_hours, page_size, should_stop, progress_callback: [
            _sample_paper()
        ],
    )
    monkeypatch.setattr(
        "arxiv_agent.semantic.SemanticMatcher.score_papers",
        lambda self, papers, semantic_queries: {},
    )
    monkeypatch.setattr(
        "arxiv_agent.summarizer.Summarizer.summarize",
        lambda self, paper: SummaryResult(summary_cn="x", highlights=["h1", "h2", "h3"], recommendation="可选阅读"),
    )

    settings = Settings()
    rules = KeywordRules(
        categories=["cs.AI"],
        profiles=[KeywordProfile(name="p1", include_any=["agent"], max_items_per_run=5)],
    )

    result = run_search(
        settings,
        rules,
        should_stop=lambda: True,
        top_k=5,
        max_results_per_category=50,
    )

    assert result.stopped is True
    assert result.fetched == 1
    assert result.matched == 0
