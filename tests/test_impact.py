from datetime import UTC, datetime

from arxiv_agent.config import ImpactConfig
from arxiv_agent.impact import ImpactScorer, _RawImpact
from arxiv_agent.models import Paper


def _paper(pid: str) -> Paper:
    now = datetime.now(UTC)
    return Paper(
        paper_id=pid,
        title=f"Paper {pid}",
        summary="summary",
        authors=["a", "b"],
        categories=["cs.AI"],
        published=now,
        updated=now,
        url=f"https://arxiv.org/abs/{pid}",
    )


def test_impact_scores_are_built_from_external_raw(monkeypatch) -> None:
    cfg = ImpactConfig(enabled=True, max_papers_per_run=10, max_workers=2, timeout_seconds=1)
    scorer = ImpactScorer(cfg)

    def fake_fetch_batch(self, client, papers):
        out = {}
        for paper in papers:
            if paper.paper_id.startswith("2603.1"):
                out[paper.paper_id] = _RawImpact(
                    citation_count=120,
                    influential_citation_count=20,
                    reference_count=40,
                    citation_velocity=60.0,
                )
            else:
                out[paper.paper_id] = _RawImpact(
                    citation_count=5,
                    influential_citation_count=0,
                    reference_count=30,
                    citation_velocity=2.0,
                )
        return out

    monkeypatch.setattr("arxiv_agent.impact.ImpactScorer._fetch_batch_raw_impact", fake_fetch_batch)

    papers = [_paper("2603.10001v1"), _paper("2603.00002v1")]
    result = scorer.score_papers(papers)

    assert result["2603.10001v1"].heat_score > result["2603.00002v1"].heat_score
    assert result["2603.10001v1"].contribution_score > result["2603.00002v1"].contribution_score
    assert result["2603.10001v1"].citation_count == 120
    assert result["2603.10001v1"].source == "semantic_scholar"
