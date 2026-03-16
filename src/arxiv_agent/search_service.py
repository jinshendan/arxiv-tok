from __future__ import annotations

from dataclasses import dataclass, replace

from .arxiv_client import ArxivClient
from .config import KeywordRules, Settings
from .filtering import filter_and_rank
from .models import ScoredPaper, SummaryResult
from .semantic import SemanticMatcher
from .summarizer import Summarizer


@dataclass(slots=True)
class SearchResult:
    lookback_hours: int
    fetched: int
    matched: int
    selected_profiles: list[str]
    items: list[tuple[ScoredPaper, SummaryResult]]


def resolve_lookback_hours(default_hours: int, days: int, months: int, years: float) -> int:
    if days < 0 or months < 0 or years < 0:
        raise ValueError("days/months/years must be non-negative")
    if days == 0 and months == 0 and years == 0:
        return default_hours

    total_days = days + months * 30 + years * 365
    return max(1, int(total_days * 24))


def run_search(
    settings: Settings,
    rules: KeywordRules,
    *,
    days: int = 0,
    months: int = 0,
    years: float = 0.0,
    profile_names: list[str] | None = None,
    top_k: int = 10,
    max_results_per_category: int = 600,
) -> SearchResult:
    if not rules.profiles:
        raise ValueError("No profiles found in keyword rules")

    selected_profiles = rules.profiles
    if profile_names:
        target = set(profile_names)
        selected_profiles = [p for p in rules.profiles if p.name in target]
        missing = sorted(target - {p.name for p in selected_profiles})
        if missing:
            raise ValueError(f"Unknown profile(s): {', '.join(missing)}")

    lookback_hours = resolve_lookback_hours(settings.lookback_hours, days=days, months=months, years=years)

    client = ArxivClient(
        user_agent=settings.user_agent,
        timeout_seconds=settings.request_timeout_seconds,
        min_request_interval_seconds=settings.arxiv_min_request_interval_seconds,
        max_retries=settings.arxiv_max_retries,
    )
    papers = client.fetch_recent(
        categories=rules.categories,
        max_results_per_category=max_results_per_category,
        lookback_hours=lookback_hours,
        page_size=settings.arxiv_page_size,
    )

    summarizer = Summarizer(settings.openai)
    semantic_matcher = SemanticMatcher(settings.openai)

    items: list[tuple[ScoredPaper, SummaryResult]] = []
    for profile in selected_profiles:
        profile_for_search = replace(profile, max_items_per_run=top_k)
        semantic_scores = semantic_matcher.score_papers(papers, profile_for_search.semantic_queries)
        ranked = filter_and_rank(papers, profile_for_search, semantic_scores=semantic_scores)
        for scored in ranked:
            summary = summarizer.summarize(scored.paper)
            items.append((scored, summary))

    return SearchResult(
        lookback_hours=lookback_hours,
        fetched=len(papers),
        matched=len(items),
        selected_profiles=[p.name for p in selected_profiles],
        items=items,
    )
