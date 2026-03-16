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
    ) -> list[Paper]:
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        papers: dict[str, Paper] = {}

        for cat in categories:
            query = f"cat:{cat.strip()}"
            url = (
                "https://export.arxiv.org/api/query?"
                f"search_query={quote_plus(query)}"
                f"&start=0&max_results={max_results_per_category}"
                "&sortBy=submittedDate&sortOrder=descending"
            )
            headers = {"User-Agent": self.user_agent}
            with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
                response = client.get(url)
                response.raise_for_status()

            feed = feedparser.parse(response.text)
            for entry in feed.entries:
                published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                if published < cutoff:
                    continue
                updated = datetime(*entry.updated_parsed[:6], tzinfo=UTC)
                paper_id = entry.id.rsplit("/", 1)[-1]
                paper = Paper(
                    paper_id=paper_id,
                    title=" ".join(entry.title.split()),
                    summary=" ".join(entry.summary.split()),
                    authors=[a.name for a in entry.authors],
                    categories=[t["term"] for t in entry.tags],
                    published=published,
                    updated=updated,
                    url=entry.id,
                )
                papers[paper_id] = paper

        return sorted(papers.values(), key=lambda p: p.published, reverse=True)
