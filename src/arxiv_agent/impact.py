from __future__ import annotations

import math
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

import httpx

from .config import ImpactConfig
from .models import ImpactSignal, Paper


@dataclass(slots=True)
class _RawImpact:
    citation_count: int
    influential_citation_count: int
    reference_count: int
    citation_velocity: float


class ImpactScorer:
    def __init__(self, config: ImpactConfig) -> None:
        self.config = config
        self.provider = config.provider.strip().lower()
        self.base_url = config.base_url.rstrip("/")
        self.api_key = os.getenv(config.api_key_env, "").strip()

    @property
    def enabled(self) -> bool:
        if not self.config.enabled:
            return False
        return self.provider == "semantic_scholar"

    def score_papers(
        self,
        papers: list[Paper],
        *,
        should_stop: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, ImpactSignal]:
        if not self.enabled or not papers:
            return {}

        ordered = sorted(papers, key=lambda p: p.published, reverse=True)
        targets = ordered[: max(1, self.config.max_papers_per_run)]
        total = len(targets)
        if total == 0:
            return {}

        raw_by_id: dict[str, _RawImpact] = {}
        done = 0
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            for batch in _chunked(targets, size=min(100, max(1, self.config.max_workers * 10))):
                if should_stop and should_stop():
                    break
                try:
                    raw_by_id.update(self._fetch_batch_raw_impact(client, batch))
                except Exception:
                    # External impact is best-effort: keep lexical/semantic ranking available.
                    pass
                done += len(batch)
                if progress_callback:
                    progress_callback(min(done, total), total)

        return {
            paper_id: ImpactSignal(
                heat_score=_scale_to_10(raw.citation_count + raw.influential_citation_count * 3 + raw.citation_velocity * 2, 120.0),
                contribution_score=_scale_to_10(
                    raw.influential_citation_count * 4 + (raw.citation_count / max(1, raw.reference_count)) * 60,
                    100.0,
                ),
                citation_count=raw.citation_count,
                influential_citation_count=raw.influential_citation_count,
                reference_count=raw.reference_count,
                citation_velocity=raw.citation_velocity,
                source="semantic_scholar",
            )
            for paper_id, raw in raw_by_id.items()
        }

    def _fetch_batch_raw_impact(self, client: httpx.Client, papers: list[Paper]) -> dict[str, _RawImpact]:
        if not papers:
            return {}
        arxiv_ids = [_normalize_arxiv_id(p.paper_id) for p in papers]
        url = f"{self.base_url}/graph/v1/paper/batch"
        params = {"fields": "citationCount,influentialCitationCount,referenceCount"}
        payload = {"ids": [f"ARXIV:{pid}" for pid in arxiv_ids]}
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        response_data: list | None = None
        for attempt in range(3):
            response = client.post(url, params=params, json=payload, headers=headers)
            if response.status_code in {429, 503}:
                time.sleep(min(2**attempt, 4))
                continue
            if response.status_code in {400, 404}:
                return {}
            response.raise_for_status()
            parsed = response.json()
            response_data = parsed if isinstance(parsed, list) else []
            break
        if response_data is None:
            return {}

        out: dict[str, _RawImpact] = {}
        for paper, item in zip(papers, response_data):
            if not isinstance(item, dict):
                continue
            citation_count = max(0, int(item.get("citationCount", 0) or 0))
            influential = max(0, int(item.get("influentialCitationCount", 0) or 0))
            reference_count = max(1, int(item.get("referenceCount", 0) or 0))
            age_years = max(0.25, (datetime.now(UTC) - paper.published.astimezone(UTC)).total_seconds() / (365 * 24 * 3600))
            velocity = citation_count / age_years
            out[paper.paper_id] = _RawImpact(
                citation_count=citation_count,
                influential_citation_count=influential,
                reference_count=reference_count,
                citation_velocity=velocity,
            )
        return out


def _normalize_arxiv_id(paper_id: str) -> str:
    token = paper_id.strip()
    m = re.match(r"^(.+?)v\d+$", token, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return token


def _scale_to_10(raw_value: float, cap: float) -> int:
    if raw_value <= 0:
        return 0
    if cap <= 0:
        return 0
    normalized = math.log1p(raw_value) / math.log1p(cap) * 10.0
    return int(round(max(0.0, min(10.0, normalized))))


def _chunked(items: list[Paper], size: int) -> list[list[Paper]]:
    return [items[i : i + size] for i in range(0, len(items), max(1, size))]
