from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import Paper


class ArxivClient:
    def __init__(self, user_agent: str, timeout_seconds: int = 30) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    def fetch_recent(
        self,
        categories: list[str],
        max_results_per_category: int,
        lookback_hours: int,
        page_size: int = 100,
    ) -> list[Paper]:
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        papers: dict[str, Paper] = {}
        page_size = max(1, page_size)
        max_results_per_category = max(1, max_results_per_category)
        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
            for cat in categories:
                category = cat.strip()
                if not category:
                    continue

                start = 0
                reached_cutoff = False
                while start < max_results_per_category and not reached_cutoff:
                    batch_size = min(page_size, max_results_per_category - start)
                    url = self._build_query_url(category=category, start=start, max_results=batch_size)
                    response = client.get(url)
                    response.raise_for_status()

                    feed = feedparser.parse(response.text)
                    if not feed.entries:
                        break

                    for entry in feed.entries:
                        published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                        if published < cutoff:
                            reached_cutoff = True
                            break
                        paper = self._entry_to_paper(entry)
                        papers[paper.paper_id] = paper

                    start += len(feed.entries)
                    if len(feed.entries) < batch_size:
                        break

        return sorted(papers.values(), key=lambda p: p.published, reverse=True)

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
