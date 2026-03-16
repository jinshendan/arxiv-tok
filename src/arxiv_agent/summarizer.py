from __future__ import annotations

from dataclasses import dataclass

from tenacity import retry, stop_after_attempt, wait_exponential

from .config import ModelConfig
from .llm_provider import LLMProviderClient
from .models import Paper, SummaryResult


@dataclass
class Summarizer:
    config: ModelConfig

    def summarize(self, paper: Paper) -> SummaryResult:
        client = LLMProviderClient(self.config)
        if not client.chat_enabled:
            return self._fallback(paper)

        try:
            return self._call_model(paper, client)
        except Exception:
            return self._fallback(paper)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _call_model(self, paper: Paper, client: LLMProviderClient) -> SummaryResult:
        system_prompt = (
            "你是学术论文助手。请基于输入论文信息输出 JSON，包含字段: "
            "summary_cn(中文2-3句), highlights(长度3的字符串数组), recommendation("
            "建议阅读/可选阅读/暂不阅读 三选一)。不要输出 JSON 之外内容。"
        )
        user_prompt = (
            f"Title: {paper.title}\n"
            f"Abstract: {paper.summary}\n"
            f"Authors: {', '.join(paper.authors)}\n"
            f"Categories: {', '.join(paper.categories)}"
        )
        parsed = client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
        return SummaryResult(
            summary_cn=str(parsed.get("summary_cn", "")).strip() or "模型未返回摘要",
            highlights=[str(x).strip() for x in parsed.get("highlights", [])][:3],
            recommendation=str(parsed.get("recommendation", "可选阅读")).strip(),
        )

    def _fallback(self, paper: Paper) -> SummaryResult:
        short = paper.summary[:280] + ("..." if len(paper.summary) > 280 else "")
        highlights = [
            f"主题: {paper.title[:80]}",
            f"作者: {', '.join(paper.authors[:3])}",
            f"分类: {', '.join(paper.categories[:3])}",
        ]
        return SummaryResult(summary_cn=short, highlights=highlights, recommendation="可选阅读")
