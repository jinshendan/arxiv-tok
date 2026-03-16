from datetime import UTC, datetime

from arxiv_agent.config import ModelConfig
from arxiv_agent.models import Paper
from arxiv_agent.summarizer import Summarizer


def _paper() -> Paper:
    now = datetime.now(UTC)
    return Paper(
        paper_id="2603.00001v1",
        title="Fast Agent Discovery",
        summary="This paper studies efficient agent search under constrained budget.",
        authors=["a", "b"],
        categories=["cs.AI"],
        published=now,
        updated=now,
        url="https://arxiv.org/abs/2603.00001",
    )


def test_fallback_summary_english_when_model_disabled() -> None:
    summarizer = Summarizer(ModelConfig(enabled=False))
    result = summarizer.summarize(_paper(), output_language="en")

    assert result.recommendation == "Optional"
    assert result.highlights[0].startswith("Topic:")


def test_fallback_summary_chinese_when_model_disabled() -> None:
    summarizer = Summarizer(ModelConfig(enabled=False))
    result = summarizer.summarize(_paper(), output_language="zh")

    assert result.recommendation == "可选阅读"
    assert result.highlights[0].startswith("主题:")
