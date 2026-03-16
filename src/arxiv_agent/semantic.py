from __future__ import annotations

import math
import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import OpenAIConfig
from .models import Paper


class SemanticMatcher:
    def __init__(self, config: OpenAIConfig) -> None:
        self.config = config
        self._api_key = os.getenv(config.api_key_env, "")
        self._enabled = bool(config.enabled and self._api_key)
        self._query_cache: dict[tuple[str, ...], list[list[float]]] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def score_papers(self, papers: list[Paper], semantic_queries: list[str]) -> dict[str, float]:
        if not self.enabled or not papers:
            return {}

        query_key = tuple(q.strip() for q in semantic_queries if q.strip())
        if not query_key:
            return {}

        query_vectors = self._query_cache.get(query_key)
        if query_vectors is None:
            query_vectors = self._embed_texts(list(query_key))
            self._query_cache[query_key] = query_vectors

        paper_texts = [f"{p.title}\n{p.summary}" for p in papers]
        paper_vectors = self._embed_texts(paper_texts)

        scores: dict[str, float] = {}
        for paper, paper_vec in zip(papers, paper_vectors):
            scores[paper.paper_id] = max(_cosine_similarity(paper_vec, q_vec) for q_vec in query_vectors)
        return scores

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.config.embedding_model, "input": texts}
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post("https://api.openai.com/v1/embeddings", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        items = data.get("data", [])
        if len(items) != len(texts):
            raise ValueError("Unexpected embedding response size")
        return [item["embedding"] for item in items]


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
