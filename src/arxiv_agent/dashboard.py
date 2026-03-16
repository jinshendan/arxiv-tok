from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import httpx
import streamlit as st

from arxiv_agent.config import KeywordProfile, KeywordRules, Settings, load_settings
from arxiv_agent.search_service import SearchResult, run_search


DEFAULT_SETTINGS_PATH = Path("config/settings.yaml")
ALL_DOMAIN_CATEGORY_WILDCARDS = [
    "cs.*",
    "math.*",
    "stat.*",
    "physics.*",
    "q-bio.*",
    "q-fin.*",
    "econ.*",
    "eess.*",
]

COMMON_DOMAIN_PRESETS: dict[str, list[str]] = {
    "人工智能与机器学习": ["cs.AI", "cs.LG", "stat.ML"],
    "自然语言处理": ["cs.CL", "cs.AI"],
    "计算机视觉": ["cs.CV", "eess.IV", "cs.AI"],
    "多模态与语音": ["cs.CV", "cs.CL", "eess.AS"],
    "推荐与检索": ["cs.IR", "cs.LG", "cs.AI"],
    "强化学习与机器人": ["cs.RO", "cs.LG", "cs.AI", "cs.SY"],
    "软件工程与系统": ["cs.SE", "cs.DC", "cs.OS", "cs.DB"],
    "数学与优化": ["math.OC", "math.PR", "math.ST", "cs.LG"],
    "统计与计量": ["stat.ML", "stat.AP", "stat.TH", "econ.EM"],
    "物理与材料": ["physics.*", "cond-mat.*", "quant-ph"],
    "生物与医学": ["q-bio.*", "q-bio.BM", "stat.ML"],
    "金融与经济": ["q-fin.*", "econ.*", "stat.AP"],
}


st.set_page_config(page_title="arxiv-tok 仪表盘", page_icon="📚", layout="wide")

st.markdown(
    """
    <style>
      .stApp {
        background: radial-gradient(1200px 480px at 10% -10%, #f4f9ff 0%, #f8f7ef 35%, #fdfdfc 70%);
      }
      html, body, [class*="css"] {
        font-family: "IBM Plex Sans", "Avenir Next", "Segoe UI", sans-serif;
      }
      .hero-card {
        border: 1px solid #d8e5f4;
        background: linear-gradient(135deg, #ffffff 0%, #f3f8ff 100%);
        padding: 18px;
        border-radius: 16px;
        box-shadow: 0 10px 24px rgba(34, 79, 122, 0.08);
        margin-bottom: 12px;
      }
      .paper-card {
        border: 1px solid #dbe5d7;
        background: linear-gradient(180deg, #ffffff 0%, #f8fcf3 100%);
        border-radius: 14px;
        padding: 12px 14px;
        margin-bottom: 10px;
      }
      .pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        background: #e9f1ff;
        color: #184e91;
        font-size: 12px;
        margin-right: 8px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _parse_terms(raw: str) -> list[str]:
    normalized = raw.replace(",", "\n")
    return [x.strip() for x in normalized.splitlines() if x.strip()]


def _load_base_settings() -> Settings:
    if DEFAULT_SETTINGS_PATH.exists():
        return load_settings(DEFAULT_SETTINGS_PATH)
    return Settings()


def _build_window(mode: str, value: int) -> tuple[int, int, float]:
    if mode == "days":
        return value, 0, 0.0
    if mode == "months":
        return 0, value, 0.0
    return 0, 0, float(value)


def _render_results(result: SearchResult) -> None:
    m1, m2, m3 = st.columns(3)
    m1.metric("抓取论文数", result.fetched)
    m2.metric("命中结果数", result.matched)
    m3.metric("时间窗口（天）", f"{result.lookback_hours / 24:.1f}")

    if not result.items:
        st.info("该时间窗口内没有命中结果。你可以放宽关键词或扩大时间窗口。")
        return

    for idx, (scored, summary) in enumerate(result.items, start=1):
        paper = scored.paper
        sem = "无" if scored.semantic_similarity is None else f"{scored.semantic_similarity:.3f}"
        st.markdown('<div class="paper-card">', unsafe_allow_html=True)
        st.markdown(f"**{idx}. {paper.title}**")
        st.markdown(
            f'<span class="pill">评分 {scored.score}</span>'
            f'<span class="pill">语义 {sem}</span>'
            f'<span class="pill">{paper.published.date()}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"[arXiv 链接]({paper.url})")
        st.markdown(f"**摘要**: {summary.summary_cn}")
        st.markdown(f"**要点**: {' | '.join(summary.highlights)}")
        st.markdown(f"**建议**: {summary.recommendation}")
        st.markdown("</div>", unsafe_allow_html=True)


st.markdown(
    '<div class="hero-card"><h2>arxiv-tok 仪表盘</h2>'
    '<p>输入关键词与时间范围即可搜索。不会写 arXiv 分类代码也能直接用。</p></div>',
    unsafe_allow_html=True,
)

base_settings = _load_base_settings()
api_key_exists = bool(os.getenv(base_settings.openai.api_key_env, ""))

with st.sidebar:
    st.header("搜索参数")

    st.subheader("时间窗口")
    window_mode = st.selectbox(
        "时间单位",
        options=["days", "months", "years"],
        index=1,
        format_func=lambda x: {"days": "天", "months": "月", "years": "年"}[x],
    )
    max_value = 3650 if window_mode == "days" else 120 if window_mode == "months" else 10
    default_value = 30 if window_mode == "days" else 1
    window_value = st.number_input(
        "窗口数值（整数）", min_value=1, max_value=max_value, value=default_value, step=1
    )

    st.subheader("搜索范围")
    scope_mode = st.radio(
        "分类模式",
        options=["全领域", "常用方向", "高级自定义"],
        index=0,
        help="普通用户推荐“全领域”或“常用方向”。",
    )

    selected_domains: list[str] = []
    custom_categories_raw = ""
    if scope_mode == "常用方向":
        selected_domains = st.multiselect(
            "选择方向（中文）",
            options=list(COMMON_DOMAIN_PRESETS.keys()),
            default=["人工智能与机器学习", "自然语言处理"],
        )
        mapped_categories = sorted(
            {
                cat
                for domain in selected_domains
                for cat in COMMON_DOMAIN_PRESETS.get(domain, [])
            }
        )
        if mapped_categories:
            st.caption("自动映射分类：" + ", ".join(mapped_categories))
    elif scope_mode == "高级自定义":
        custom_categories_raw = st.text_area(
            "自定义 arXiv 分类（逗号或换行分隔）",
            value="cs.AI\ncs.LG\ncs.CL",
        )

    st.subheader("关键词规则")
    include_any_raw = st.text_area(
        "包含任一关键词 include_any（推荐填写，一行一个）",
        value="agent\nretrieval augmented generation",
    )
    include_all_raw = st.text_area("必须包含关键词 include_all（可选）", value="")
    exclude_any_raw = st.text_area("排除关键词 exclude_any（可选）", value="survey")

    st.subheader("语义匹配")
    semantic_on = st.checkbox("启用 OpenAI 语义匹配", value=api_key_exists)
    semantic_queries_raw = st.text_area(
        "语义查询 semantic_queries（一行一个）",
        value="multi-agent tool use\n跨语言检索增强生成",
        disabled=not semantic_on,
    )

    st.subheader("结果数量")
    top_k = st.slider("每次返回 top_k", min_value=1, max_value=100, value=15)
    max_results = st.slider("每个分类抓取上限", min_value=50, max_value=2000, value=300, step=50)
    st.caption("提示：这个值越大，请求越多，更容易触发 arXiv 限流。建议先从 200-400 开始。")

    run = st.button("开始搜索", type="primary", use_container_width=True)

if run:
    include_any = _parse_terms(include_any_raw)
    include_all = _parse_terms(include_all_raw)
    exclude_any = _parse_terms(exclude_any_raw)
    semantic_queries = _parse_terms(semantic_queries_raw)

    if not include_any and not include_all and not (semantic_on and semantic_queries):
        st.warning("请至少填写 include_any/include_all 或 semantic_queries 中的一种。")
        st.stop()

    if semantic_on and not api_key_exists:
        st.warning("未检测到 OPENAI_API_KEY，语义匹配已自动关闭。")
        semantic_on = False

    runtime_openai_cfg = replace(base_settings.openai, enabled=semantic_on and api_key_exists)
    runtime_settings = replace(base_settings, openai=runtime_openai_cfg)

    if scope_mode == "全领域":
        categories = ALL_DOMAIN_CATEGORY_WILDCARDS
    elif scope_mode == "常用方向":
        categories = sorted(
            {
                cat
                for domain in selected_domains
                for cat in COMMON_DOMAIN_PRESETS.get(domain, [])
            }
        )
    else:
        categories = _parse_terms(custom_categories_raw)

    if not categories:
        st.warning("请至少选择一个方向，或填写一个有效分类。")
        st.stop()

    custom_profile = KeywordProfile(
        name="custom-search",
        include_all=include_all,
        include_any=include_any,
        exclude_any=exclude_any,
        semantic_queries=semantic_queries if semantic_on else [],
        semantic_min_similarity=0.33,
        semantic_weight=2,
        min_score=1,
        max_items_per_run=int(top_k),
    )
    runtime_rules = KeywordRules(categories=categories, profiles=[custom_profile])

    d, m, y = _build_window(window_mode, window_value)

    try:
        with st.spinner("正在抓取并总结论文..."):
            result = run_search(
                runtime_settings,
                runtime_rules,
                days=d,
                months=m,
                years=y,
                profile_names=["custom-search"],
                top_k=int(top_k),
                max_results_per_category=int(max_results),
            )
        st.session_state["dashboard_result"] = result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            st.error(
                "arXiv 请求过于频繁（429）。请先降低“每个分类抓取上限”、缩短时间窗口，"
                "或减少分类后重试。"
            )
        else:
            st.error(f"搜索失败: {e}")
    except Exception as e:
        st.error(f"搜索失败: {e}")

if "dashboard_result" in st.session_state:
    _render_results(st.session_state["dashboard_result"])
else:
    st.info("在左侧设置参数后，点击“开始搜索”。")
