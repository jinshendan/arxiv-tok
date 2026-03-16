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


_PROGRESS_MESSAGES = {
    "start": {
        "zh": "准备开始搜索...",
        "en": "Preparing search...",
    },
    "fetching": {
        "zh": "抓取中: {category} ({idx}/{total}), fetched {fetched}",
        "en": "Fetching: {category} ({idx}/{total}), fetched {fetched}",
    },
    "fetched_done": {
        "zh": "抓取完成，共 {count} 篇，开始过滤...",
        "en": "Fetch complete: {count} papers, now filtering...",
    },
    "filtered": {
        "zh": "过滤完成: {profile} ({idx}/{total}), 命中 {count}",
        "en": "Filtered: {profile} ({idx}/{total}), matched {count}",
    },
    "summarizing": {
        "zh": "总结中: {profile} ({done}/{total})",
        "en": "Summarizing: {profile} ({done}/{total})",
    },
    "done_empty": {
        "zh": "已完成搜索。",
        "en": "Search completed.",
    },
    "done_with_count": {
        "zh": "已完成搜索，返回 {count} 条结果。",
        "en": "Search completed, returning {count} results.",
    },
}


def _msg(lang: str, key: str, **kwargs) -> str:
    lang_key = "en" if lang.lower().startswith("en") else "zh"
    template = _PROGRESS_MESSAGES[key][lang_key]
    return template.format(**kwargs)


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
    language: str = "zh",
    summary_language: str = "zh",
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

    emit(_msg(language, "start"), 0.02)

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
            _msg(
                language,
                "fetching",
                category=category,
                idx=category_index,
                total=num_categories,
                fetched=fetched,
            ),
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
    emit(_msg(language, "fetched_done", count=len(papers)), 0.62)

    summarizer = Summarizer(settings.model)
    semantic_matcher = SemanticMatcher(settings.model)

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
            _msg(
                language,
                "filtered",
                profile=profile_for_search.name,
                idx=idx,
                total=len(selected_profiles),
                count=len(ranked),
            ),
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
            summary = summarizer.summarize(scored.paper, output_language=summary_language)
            items.append((scored, summary))
            summarized += 1
            tail_progress = summarized / max(1, total_to_summarize)
            emit(
                _msg(
                    language,
                    "summarizing",
                    profile=profile_name,
                    done=summarized,
                    total=max(1, total_to_summarize),
                ),
                0.65 + 0.35 * tail_progress,
            )

    if not items:
        emit(_msg(language, "done_empty"), 1.0)
    else:
        emit(_msg(language, "done_with_count", count=len(items)), 1.0)

    return SearchResult(
        lookback_hours=lookback_hours,
        fetched=len(papers),
        matched=len(items),
        selected_profiles=[p.name for p in selected_profiles],
        items=items,
        stopped=stopped,
    )
