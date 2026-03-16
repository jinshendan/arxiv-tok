from __future__ import annotations

import json
import os
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import OpenAIConfig
from .models import Paper, SummaryResult


@dataclass
class Summarizer:
    config: OpenAIConfig

    def summarize(self, paper: Paper) -> SummaryResult:
        if not self.config.enabled:
            return self._fallback(paper)

        api_key = os.getenv(self.config.api_key_env, "")
        if not api_key:
            return self._fallback(paper)

        try:
            return self._call_openai(paper, api_key)
        except Exception:
            return self._fallback(paper)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _call_openai(self, paper: Paper, api_key: str) -> SummaryResult:
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

        payload = {
            "model": self.config.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        }

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            resp = client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = (data.get("output_text") or "").strip()
        if not text:
            text = self._extract_output_text(data)
        if not text:
            raise ValueError("empty model output")

        parsed = json.loads(text)
        return SummaryResult(
            summary_cn=str(parsed.get("summary_cn", "")).strip() or "模型未返回摘要",
            highlights=[str(x).strip() for x in parsed.get("highlights", [])][:3],
            recommendation=str(parsed.get("recommendation", "可选阅读")).strip(),
        )

    def _extract_output_text(self, data: dict) -> str:
        output = data.get("output", [])
        for item in output:
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "")
        return ""

    def _fallback(self, paper: Paper) -> SummaryResult:
        short = paper.summary[:280] + ("..." if len(paper.summary) > 280 else "")
        highlights = [
            f"主题: {paper.title[:80]}",
            f"作者: {', '.join(paper.authors[:3])}",
            f"分类: {', '.join(paper.categories[:3])}",
        ]
        return SummaryResult(summary_cn=short, highlights=highlights, recommendation="可选阅读")
