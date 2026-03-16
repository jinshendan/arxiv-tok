from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

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
    stopped: bool = False


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
    progress_callback: Callable[[str, float], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
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
    stopped = False

    def emit(message: str, progress: float) -> None:
        if progress_callback:
            progress_callback(message, max(0.0, min(1.0, progress)))

    emit("准备开始搜索...", 0.02)

    client = ArxivClient(
        user_agent=settings.user_agent,
        timeout_seconds=settings.request_timeout_seconds,
        min_request_interval_seconds=settings.arxiv_min_request_interval_seconds,
        max_retries=settings.arxiv_max_retries,
    )
    num_categories = max(1, len(rules.categories))

    def on_fetch_progress(payload: dict) -> None:
        category = str(payload.get("category", ""))
        category_index = int(payload.get("category_index", 1))
        start = int(payload.get("start", 0))
        max_per_cat = int(payload.get("max_results_per_category", max_results_per_category))
        fetched = int(payload.get("fetched", 0))
        category_fraction = min(1.0, start / max(1, max_per_cat))
        overall_fraction = ((category_index - 1) + category_fraction) / num_categories
        emit(
            f"抓取中: {category} ({category_index}/{num_categories})，已抓取 {fetched} 篇",
            0.05 + 0.55 * overall_fraction,
        )

    papers = client.fetch_recent(
        categories=rules.categories,
        max_results_per_category=max_results_per_category,
        lookback_hours=lookback_hours,
        page_size=settings.arxiv_page_size,
        should_stop=should_stop,
        progress_callback=on_fetch_progress,
    )
    if should_stop and should_stop():
        stopped = True
    emit(f"抓取完成，共 {len(papers)} 篇，开始过滤...", 0.62)

    summarizer = Summarizer(settings.openai)
    semantic_matcher = SemanticMatcher(settings.openai)

    ranked_by_profile: list[tuple[str, list[ScoredPaper]]] = []
    for idx, profile in enumerate(selected_profiles, start=1):
        if should_stop and should_stop():
            stopped = True
            break
        profile_for_search = replace(profile, max_items_per_run=top_k)
        semantic_scores = semantic_matcher.score_papers(papers, profile_for_search.semantic_queries)
        ranked = filter_and_rank(papers, profile_for_search, semantic_scores=semantic_scores)
        ranked_by_profile.append((profile_for_search.name, ranked))
        emit(
            f"过滤完成: {profile_for_search.name} ({idx}/{len(selected_profiles)})，命中 {len(ranked)} 篇",
            0.65,
        )

    total_to_summarize = sum(len(ranked) for _, ranked in ranked_by_profile)
    summarized = 0
    items: list[tuple[ScoredPaper, SummaryResult]] = []
    for profile_name, ranked in ranked_by_profile:
        if should_stop and should_stop():
            stopped = True
            break
        for scored in ranked:
            if should_stop and should_stop():
                stopped = True
                break
            summary = summarizer.summarize(scored.paper)
            items.append((scored, summary))
            summarized += 1
            tail_progress = summarized / max(1, total_to_summarize)
            emit(
                f"总结中: {profile_name} ({summarized}/{max(1, total_to_summarize)})",
                0.65 + 0.35 * tail_progress,
            )

    if not items:
        emit("已完成搜索。", 1.0)
    else:
        emit(f"已完成搜索，返回 {len(items)} 条结果。", 1.0)

    return SearchResult(
        lookback_hours=lookback_hours,
        fetched=len(papers),
        matched=len(items),
        selected_profiles=[p.name for p in selected_profiles],
        items=items,
        stopped=stopped,
    )
