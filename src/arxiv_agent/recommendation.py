from __future__ import annotations

from .models import ScoredPaper


def recommendation_code_from_score(scored: ScoredPaper) -> str:
    if scored.impact_source == "none":
        if scored.base_score >= 10:
            return "must_read"
        if scored.base_score >= 5:
            return "worth_reading"
        return "skip_for_now"

    if scored.score >= 16 or (scored.heat_score >= 4 and scored.contribution_score >= 5):
        return "must_read"
    if scored.score >= 8 or scored.contribution_score >= 4:
        return "worth_reading"
    return "skip_for_now"


def localize_recommendation(code: str, language: str) -> str:
    lang = "en" if language.lower().startswith("en") else "zh"
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
    if lang == "en":
        return en_map.get(code, "Optional")
    return zh_map.get(code, "可选阅读")
