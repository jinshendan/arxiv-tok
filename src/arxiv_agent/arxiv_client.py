from __future__ import annotations

from datetime import UTC, datetime, timedelta
import time
from typing import Callable
from urllib.parse import quote_plus

import feedparser
import httpx

from .models import Paper


class ArxivClient:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: int = 30,
        min_request_interval_seconds: float = 3.0,
        max_retries: int = 6,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.min_request_interval_seconds = max(0.0, float(min_request_interval_seconds))
        self.max_retries = max(1, int(max_retries))
        self._next_allowed_request_at = 0.0

    def fetch_recent(
        self,
        categories: list[str],
        max_results_per_category: int,
        lookback_hours: int,
        page_size: int = 200,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> list[Paper]:
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        papers: dict[str, Paper] = {}
        page_size = max(1, page_size)
        max_results_per_category = max(1, max_results_per_category)
        headers = {"User-Agent": self.user_agent}
        total_categories = len(categories)
        with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
            for cat_index, cat in enumerate(categories, start=1):
                if should_stop and should_stop():
                    break
                category = cat.strip()
                if not category:
                    continue

                start = 0
                reached_cutoff = False
                if progress_callback:
                    progress_callback(
                        {
                            "phase": "fetch",
                            "category": category,
                            "category_index": cat_index,
                            "category_total": total_categories,
                            "fetched": len(papers),
                            "start": start,
                            "max_results_per_category": max_results_per_category,
                        }
                    )
                while start < max_results_per_category and not reached_cutoff:
                    if should_stop and should_stop():
                        reached_cutoff = True
                        break
                    batch_size = min(page_size, max_results_per_category - start)
                    url = self._build_query_url(category=category, start=start, max_results=batch_size)
                    response = self._request_with_retry(client, url, should_stop=should_stop)
                    if response is None:
                        reached_cutoff = True
                        break

                    feed = feedparser.parse(response.text)
                    if not feed.entries:
                        break

                    for entry in feed.entries:
                        if should_stop and should_stop():
                            reached_cutoff = True
                            break
                        published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                        if published < cutoff:
                            reached_cutoff = True
                            break
                        paper = self._entry_to_paper(entry)
                        papers[paper.paper_id] = paper

                    start += len(feed.entries)
                    if progress_callback:
                        progress_callback(
                            {
                                "phase": "fetch",
                                "category": category,
                                "category_index": cat_index,
                                "category_total": total_categories,
                                "fetched": len(papers),
                                "start": start,
                                "max_results_per_category": max_results_per_category,
                            }
                        )
                    if len(feed.entries) < batch_size:
                        break

                if progress_callback:
                    progress_callback(
                        {
                            "phase": "category_done",
                            "category": category,
                            "category_index": cat_index,
                            "category_total": total_categories,
                            "fetched": len(papers),
                            "start": start,
                            "max_results_per_category": max_results_per_category,
                            "hit_fetch_cap": bool(start >= max_results_per_category and not reached_cutoff),
                        }
                    )

        return sorted(papers.values(), key=lambda p: p.published, reverse=True)

    def _request_with_retry(
        self,
        client: httpx.Client,
        url: str,
        should_stop: Callable[[], bool] | None = None,
    ) -> httpx.Response | None:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            if should_stop and should_stop():
                return None
            if not self._throttle(should_stop=should_stop):
                return None
            try:
                response = client.get(url)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise
                if not self._sleep_with_stop(
                    self._retry_delay_seconds(attempt=attempt),
                    should_stop=should_stop,
                ):
                    return None
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.max_retries:
                    response.raise_for_status()
                if not self._sleep_with_stop(
                    self._retry_delay_seconds(attempt=attempt, response=response),
                    should_stop=should_stop,
                ):
                    return None
                continue

            response.raise_for_status()
            return response

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Failed to fetch arXiv response after retries")

    def _throttle(self, should_stop: Callable[[], bool] | None = None) -> bool:
        if self.min_request_interval_seconds <= 0:
            return True
        now = time.monotonic()
        wait_seconds = self._next_allowed_request_at - now
        if wait_seconds > 0:
            if not self._sleep_with_stop(wait_seconds, should_stop=should_stop):
                return False
        self._next_allowed_request_at = time.monotonic() + self.min_request_interval_seconds
        return True

    def _retry_delay_seconds(self, attempt: int, response: httpx.Response | None = None) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After", "").strip()
            if retry_after:
                try:
                    parsed = float(retry_after)
                    if parsed > 0:
                        return min(parsed, 120.0)
                except ValueError:
                    pass

        exp = min(2**attempt, 60)
        if response is not None and response.status_code == 429:
            return max(3.0, float(exp))
        return float(exp)

    def _sleep_with_stop(
        self,
        seconds: float,
        should_stop: Callable[[], bool] | None = None,
        granularity_seconds: float = 0.2,
    ) -> bool:
        if seconds <= 0:
            return True
        end = time.monotonic() + seconds
        while True:
            if should_stop and should_stop():
                return False
            remain = end - time.monotonic()
            if remain <= 0:
                return True
            time.sleep(min(granularity_seconds, remain))

    def _build_query_url(self, category: str, start: int, max_results: int) -> str:
        query = f"cat:{category}"
        return (
            "https://export.arxiv.org/api/query?"
            f"search_query={quote_plus(query)}"
            f"&start={start}&max_results={max_results}"
            "&sortBy=submittedDate&sortOrder=descending"
        )

    def _entry_to_paper(self, entry) -> Paper:
        published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
        updated = datetime(*entry.updated_parsed[:6], tzinfo=UTC)
        paper_id = entry.id.rsplit("/", 1)[-1]
        return Paper(
            paper_id=paper_id,
            title=" ".join(entry.title.split()),
            summary=" ".join(entry.summary.split()),
            authors=[a.name for a in entry.authors],
            categories=[t["term"] for t in entry.tags],
            published=published,
            updated=updated,
            url=entry.id,
        )
