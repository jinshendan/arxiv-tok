from __future__ import annotations

from dataclasses import dataclass

from tenacity import retry, stop_after_attempt, wait_exponential

from .config import ModelConfig
from .llm_provider import LLMProviderClient
from .models import Paper, SummaryResult


@dataclass
class Summarizer:
    config: ModelConfig

    def summarize(self, paper: Paper, output_language: str = "zh") -> SummaryResult:
        client = LLMProviderClient(self.config)
        if not client.chat_enabled:
            return self._fallback(paper, output_language)

        try:
            return self._call_model(paper, client, output_language)
        except Exception:
            return self._fallback(paper, output_language)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _call_model(self, paper: Paper, client: LLMProviderClient, output_language: str) -> SummaryResult:
        lang_code, lang_label = _normalize_language(output_language)
        system_prompt = (
            "You are a research paper assistant. "
            f"Return strict JSON only, in {lang_label}. "
            "Required fields: "
            "summary (2-3 concise sentences), "
            "highlights (array of 3 short strings), "
            "recommendation (one of: must_read, worth_reading, skip_for_now)."
        )
        user_prompt = (
            f"Title: {paper.title}\n"
            f"Abstract: {paper.summary}\n"
            f"Authors: {', '.join(paper.authors)}\n"
            f"Categories: {', '.join(paper.categories)}"
        )
        parsed = client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
        summary_text = (
            str(parsed.get("summary", "")).strip()
            or str(parsed.get("summary_cn", "")).strip()
            or _empty_summary(lang_code)
        )
        highlights = [str(x).strip() for x in parsed.get("highlights", []) if str(x).strip()][:3]
        if not highlights:
            highlights = _fallback_highlights(paper, lang_code)
        recommendation = _localize_recommendation(
            str(parsed.get("recommendation", "")).strip(),
            lang_code,
        )
        return SummaryResult(
            summary_cn=summary_text,
            highlights=highlights,
            recommendation=recommendation,
        )

    def _fallback(self, paper: Paper, output_language: str) -> SummaryResult:
        lang_code, _ = _normalize_language(output_language)
        short = paper.summary[:280] + ("..." if len(paper.summary) > 280 else "")
        return SummaryResult(
            summary_cn=short,
            highlights=_fallback_highlights(paper, lang_code),
            recommendation=_localize_recommendation("worth_reading", lang_code),
        )


def _normalize_language(output_language: str) -> tuple[str, str]:
    token = output_language.strip()
    if not token:
        return "zh", "Chinese"
    low = token.lower()
    if low.startswith("zh") or "中文" in token or "chinese" in low:
        return "zh", "Chinese"
    if low.startswith("en") or "english" in low:
        return "en", "English"
    return "other", token


def _empty_summary(lang_code: str) -> str:
    if lang_code == "zh":
        return "模型未返回摘要。"
    return "No summary returned by the model."


def _fallback_highlights(paper: Paper, lang_code: str) -> list[str]:
    if lang_code == "zh":
        return [
            f"主题: {paper.title[:80]}",
            f"作者: {', '.join(paper.authors[:3])}",
            f"分类: {', '.join(paper.categories[:3])}",
        ]
    return [
        f"Topic: {paper.title[:80]}",
        f"Authors: {', '.join(paper.authors[:3])}",
        f"Categories: {', '.join(paper.categories[:3])}",
    ]


def _localize_recommendation(raw: str, lang_code: str) -> str:
    code = _normalize_recommendation_code(raw)
    zh_map = {
        "must_read": "建议阅读",
        "worth_reading": "可选阅读",
        "skip_for_now": "暂不阅读",
    }
    en_map = {
        "must_read": "Recommended",
        "worth_reading": "Optional",
        "skip_for_now": "Skip for now",
    }
    if lang_code == "zh":
        return zh_map[code]
    return en_map[code]


def _normalize_recommendation_code(raw: str) -> str:
    token = raw.strip().lower().replace(" ", "_")
    if token in {"must_read", "recommended", "strongly_recommended", "建议阅读"}:
        return "must_read"
    if token in {"skip", "skip_for_now", "暂不阅读", "not_recommended"}:
        return "skip_for_now"
    if token in {"worth_reading", "optional", "可选阅读"}:
        return "worth_reading"
    return "worth_reading"
