from __future__ import annotations

import uuid
from dataclasses import dataclass

from .arxiv_client import ArxivClient
from .config import KeywordRules, Settings
from .db import Database
from .filtering import filter_and_rank
from .impact import ImpactScorer
from .models import ScoredPaper, SummaryResult
from .notifier import Notifier
from .recommendation import localize_recommendation, recommendation_code_from_score
from .semantic import SemanticMatcher
from .summarizer import Summarizer


@dataclass
class RunResult:
    run_id: str
    fetched: int
    matched: int
    notified_channels: list[str]


def run_once(settings: Settings, rules: KeywordRules) -> RunResult:
    db = Database(settings.database_path)
    db.init_schema()

    run_id = uuid.uuid4().hex
    db.start_run(run_id)

    try:
        client = ArxivClient(
            user_agent=settings.user_agent,
            timeout_seconds=settings.request_timeout_seconds,
            min_request_interval_seconds=settings.arxiv_min_request_interval_seconds,
            max_retries=settings.arxiv_max_retries,
        )
        papers = client.fetch_recent(
            categories=rules.categories,
            max_results_per_category=settings.max_results_per_category,
            lookback_hours=settings.lookback_hours,
            page_size=settings.arxiv_page_size,
        )
        db.upsert_papers(papers)

        summarizer = Summarizer(settings.model)
        semantic_matcher = SemanticMatcher(settings.model)
        impact_scorer = ImpactScorer(settings.impact)
        impact_scores = impact_scorer.score_papers(papers)
        notifier = Notifier(settings.notify)

        items: list[tuple[ScoredPaper, SummaryResult]] = []
        for profile in rules.profiles:
            semantic_scores = semantic_matcher.score_papers(papers, profile.semantic_queries)
            ranked = filter_and_rank(
                papers,
                profile,
                semantic_scores=semantic_scores,
                impact_scores=impact_scores,
            )
            for scored in ranked:
                summary = summarizer.summarize(scored.paper)
                summary.recommendation = localize_recommendation(
                    recommendation_code_from_score(scored),
                    "zh",
                )
                db.record_match(
                    run_id=run_id,
                    paper_id=scored.paper.paper_id,
                    profile_name=profile.name,
                    score=scored.score,
                    summary_cn=summary.summary_cn,
                    highlights=summary.highlights,
                    recommendation=summary.recommendation,
                )
                items.append((scored, summary))

        items.sort(
            key=lambda x: (
                x[0].score,
                x[0].heat_score,
                x[0].contribution_score,
                x[0].citation_count,
                x[0].semantic_similarity or 0.0,
                x[0].paper.published,
            ),
            reverse=True,
        )

        digest = notifier.format_digest(items)
        channels = notifier.send(digest)

        for channel in channels:
            for scored, _ in items:
                if not db.already_notified(scored.paper.paper_id, scored.profile_name, channel):
                    db.record_notification(scored.paper.paper_id, scored.profile_name, channel)

        db.finish_run(run_id, status="success")
        return RunResult(run_id=run_id, fetched=len(papers), matched=len(items), notified_channels=channels)

    except Exception as e:
        db.finish_run(run_id, status="failed", error=str(e))
        raise
