from __future__ import annotations

import os
import queue
import threading
import time
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

DOMAIN_PRESETS = {
    "ai_ml": {
        "categories": ["cs.AI", "cs.LG", "stat.ML"],
        "label": {"zh": "人工智能与机器学习", "en": "AI & Machine Learning"},
    },
    "nlp": {
        "categories": ["cs.CL", "cs.AI"],
        "label": {"zh": "自然语言处理", "en": "Natural Language Processing"},
    },
    "cv": {
        "categories": ["cs.CV", "eess.IV", "cs.AI"],
        "label": {"zh": "计算机视觉", "en": "Computer Vision"},
    },
    "multimodal": {
        "categories": ["cs.CV", "cs.CL", "eess.AS"],
        "label": {"zh": "多模态与语音", "en": "Multimodal & Speech"},
    },
    "ir_recsys": {
        "categories": ["cs.IR", "cs.LG", "cs.AI"],
        "label": {"zh": "推荐与检索", "en": "Retrieval & Recommender"},
    },
    "rl_robotics": {
        "categories": ["cs.RO", "cs.LG", "cs.AI", "cs.SY"],
        "label": {"zh": "强化学习与机器人", "en": "RL & Robotics"},
    },
    "systems": {
        "categories": ["cs.SE", "cs.DC", "cs.OS", "cs.DB"],
        "label": {"zh": "软件工程与系统", "en": "Software & Systems"},
    },
    "math_opt": {
        "categories": ["math.OC", "math.PR", "math.ST", "cs.LG"],
        "label": {"zh": "数学与优化", "en": "Math & Optimization"},
    },
    "stats_econometrics": {
        "categories": ["stat.ML", "stat.AP", "stat.TH", "econ.EM"],
        "label": {"zh": "统计与计量", "en": "Statistics & Econometrics"},
    },
    "physics": {
        "categories": ["physics.*", "cond-mat.*", "quant-ph"],
        "label": {"zh": "物理与材料", "en": "Physics & Materials"},
    },
    "biomed": {
        "categories": ["q-bio.*", "q-bio.BM", "stat.ML"],
        "label": {"zh": "生物与医学", "en": "Biology & Medicine"},
    },
    "finance": {
        "categories": ["q-fin.*", "econ.*", "stat.AP"],
        "label": {"zh": "金融与经济", "en": "Finance & Economics"},
    },
}


TEXT = {
    "hero_title": {"zh": "arxiv-tok 仪表盘", "en": "arxiv-tok Dashboard"},
    "hero_desc": {
        "zh": "输入关键词与时间范围即可搜索。不会写 arXiv 分类代码也能直接用。",
        "en": "Search with keywords and time window. No arXiv category code knowledge required.",
    },
    "lang_switch": {"zh": "界面语言", "en": "Interface Language"},
    "params": {"zh": "搜索参数", "en": "Search Parameters"},
    "time_window": {"zh": "时间窗口", "en": "Time Window"},
    "time_unit": {"zh": "时间单位", "en": "Time Unit"},
    "window_value": {"zh": "窗口数值（整数）", "en": "Window Value (Integer)"},
    "scope": {"zh": "搜索范围", "en": "Search Scope"},
    "scope_mode": {"zh": "分类模式", "en": "Category Mode"},
    "scope_mode_help": {
        "zh": "普通用户推荐“全领域”或“常用方向”。",
        "en": "For most users, use All Domains or Common Domains.",
    },
    "scope_all": {"zh": "全领域", "en": "All Domains"},
    "scope_preset": {"zh": "常用方向", "en": "Common Domains"},
    "scope_advanced": {"zh": "高级自定义", "en": "Advanced Custom"},
    "preset_select": {"zh": "选择方向", "en": "Select Domains"},
    "mapped_categories": {"zh": "自动映射分类", "en": "Mapped categories"},
    "custom_categories": {
        "zh": "自定义 arXiv 分类（逗号或换行分隔）",
        "en": "Custom arXiv categories (comma/newline separated)",
    },
    "keyword_rules": {"zh": "关键词规则", "en": "Keyword Rules"},
    "include_any": {
        "zh": "包含任一关键词 include_any（推荐填写，一行一个）",
        "en": "include_any (recommended, one per line)",
    },
    "include_all": {"zh": "必须包含关键词 include_all（可选）", "en": "include_all (optional)"},
    "exclude_any": {"zh": "排除关键词 exclude_any（可选）", "en": "exclude_any (optional)"},
    "semantic": {"zh": "语义匹配", "en": "Semantic Matching"},
    "semantic_on": {"zh": "启用语义匹配（模型 API）", "en": "Enable semantic matching (Model API)"},
    "semantic_provider": {"zh": "当前模型提供方", "en": "Current model provider"},
    "semantic_queries": {
        "zh": "语义查询 semantic_queries（一行一个）",
        "en": "semantic_queries (one per line)",
    },
    "result_size": {"zh": "结果数量", "en": "Result Size"},
    "top_k": {"zh": "每次返回 top_k", "en": "top_k per search"},
    "max_fetch": {"zh": "每个分类抓取上限", "en": "Fetch cap per category"},
    "max_fetch_tip": {
        "zh": "提示：这个值越大，请求越多，更容易触发 arXiv 限流。建议先从 200-400 开始。",
        "en": "Tip: larger values make more requests and may hit arXiv rate limits. Start with 200-400.",
    },
    "start": {"zh": "开始搜索", "en": "Start Search"},
    "stop": {"zh": "停止搜索并返回当前结果", "en": "Stop and Return Current Results"},
    "need_terms": {
        "zh": "请至少填写 include_any/include_all 或 semantic_queries 中的一种。",
        "en": "Please provide at least one of include_any/include_all/semantic_queries.",
    },
    "no_api_key": {
        "zh": "未检测到 {env_name}，语义匹配已自动关闭。",
        "en": "{env_name} not found. Semantic matching is disabled automatically.",
    },
    "no_categories": {
        "zh": "请至少选择一个方向，或填写一个有效分类。",
        "en": "Please select at least one domain or provide valid categories.",
    },
    "progress_hint": {
        "zh": "可随时点击“停止搜索并返回当前结果”。",
        "en": "You can click Stop at any time and keep current partial results.",
    },
    "running_fallback": {"zh": "搜索进行中...", "en": "Search is running..."},
    "waiting": {"zh": "等待开始", "en": "Waiting to start"},
    "started": {"zh": "任务已启动...", "en": "Search task started..."},
    "stopping": {
        "zh": "正在停止搜索并整理已获得结果...",
        "en": "Stopping search and preparing partial results...",
    },
    "done": {"zh": "搜索完成", "en": "Search completed"},
    "stopped_notice": {
        "zh": "搜索已手动停止，以下是停止前已获取到的结果。",
        "en": "Search stopped manually. Showing results collected before stopping.",
    },
    "metric_fetched": {"zh": "抓取论文数", "en": "Fetched"},
    "metric_matched": {"zh": "命中结果数", "en": "Matched"},
    "metric_window_days": {"zh": "时间窗口（天）", "en": "Window (days)"},
    "empty_result": {
        "zh": "该时间窗口内没有命中结果。你可以放宽关键词或扩大时间窗口。",
        "en": "No matches in this window. Try broader keywords or a longer window.",
    },
    "pill_score": {"zh": "评分", "en": "Score"},
    "pill_semantic": {"zh": "语义", "en": "Semantic"},
    "na": {"zh": "无", "en": "N/A"},
    "arxiv_link": {"zh": "arXiv 链接", "en": "Open on arXiv"},
    "summary": {"zh": "摘要", "en": "Summary"},
    "highlights": {"zh": "要点", "en": "Highlights"},
    "recommendation": {"zh": "建议", "en": "Recommendation"},
    "info_start": {"zh": "在左侧设置参数后，点击“开始搜索”。", "en": "Set parameters on the left, then click Start Search."},
    "error_429": {
        "zh": "arXiv 请求过于频繁（429）。请降低抓取上限、缩短时间窗口，或减少分类后重试。",
        "en": "arXiv rate limit hit (429). Lower fetch cap, shorten window, or reduce categories and retry.",
    },
    "error_generic": {"zh": "搜索失败: {error}", "en": "Search failed: {error}"},
}


LANG_LABELS = {"zh": "中文", "en": "English"}
WINDOW_MODE_OPTIONS = ["days", "months", "years"]
WINDOW_MODE_LABELS = {
    "days": {"zh": "天", "en": "Days"},
    "months": {"zh": "月", "en": "Months"},
    "years": {"zh": "年", "en": "Years"},
}
SCOPE_MODE_OPTIONS = ["all", "preset", "advanced"]


def t(lang: str, key: str, **kwargs) -> str:
    lang_key = "en" if lang.lower().startswith("en") else "zh"
    text = TEXT.get(key, {}).get(lang_key) or TEXT.get(key, {}).get("zh") or key
    return text.format(**kwargs)


def _scope_mode_label(lang: str, mode: str) -> str:
    if mode == "all":
        return t(lang, "scope_all")
    if mode == "preset":
        return t(lang, "scope_preset")
    return t(lang, "scope_advanced")


def _domain_label(lang: str, preset_key: str) -> str:
    lang_key = "en" if lang.lower().startswith("en") else "zh"
    return DOMAIN_PRESETS[preset_key]["label"][lang_key]


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


def _ensure_search_state(lang: str) -> None:
    st.session_state.setdefault("search_running", False)
    st.session_state.setdefault("search_progress_message", t(lang, "waiting"))
    st.session_state.setdefault("search_progress_value", 0.0)
    st.session_state.setdefault("search_events", None)
    st.session_state.setdefault("search_thread", None)
    st.session_state.setdefault("search_stop_event", None)
    st.session_state.setdefault("search_error", "")


def _drain_search_events(lang: str) -> None:
    events: queue.Queue | None = st.session_state.get("search_events")
    if events is None:
        return

    while True:
        try:
            event = events.get_nowait()
        except queue.Empty:
            break

        event_type = event.get("type")
        if event_type == "progress":
            st.session_state["search_progress_message"] = event.get("message", t(lang, "running_fallback"))
            st.session_state["search_progress_value"] = float(event.get("progress", 0.0))
        elif event_type == "result":
            result: SearchResult = event["result"]
            st.session_state["dashboard_result"] = result
            st.session_state["search_running"] = False
            st.session_state["search_progress_value"] = 1.0
            st.session_state["search_progress_message"] = t(lang, "done")
            st.session_state["search_error"] = ""
            st.session_state["search_events"] = None
            st.session_state["search_thread"] = None
            st.session_state["search_stop_event"] = None
        elif event_type == "error":
            st.session_state["search_running"] = False
            st.session_state["search_error"] = str(event.get("message", t(lang, "error_generic", error="unknown")))
            st.session_state["search_events"] = None
            st.session_state["search_thread"] = None
            st.session_state["search_stop_event"] = None


def _start_search_job(
    settings: Settings,
    rules: KeywordRules,
    *,
    days: int,
    months: int,
    years: float,
    top_k: int,
    max_results_per_category: int,
    language: str,
) -> None:
    events: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    def on_progress(message: str, progress: float) -> None:
        events.put({"type": "progress", "message": message, "progress": progress})

    def worker() -> None:
        try:
            result = run_search(
                settings,
                rules,
                days=days,
                months=months,
                years=years,
                profile_names=["custom-search"],
                top_k=top_k,
                max_results_per_category=max_results_per_category,
                progress_callback=on_progress,
                should_stop=stop_event.is_set,
                language=language,
            )
            events.put({"type": "result", "result": result})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                events.put({"type": "error", "message": t(language, "error_429")})
            else:
                events.put({"type": "error", "message": t(language, "error_generic", error=e)})
        except Exception as e:
            events.put({"type": "error", "message": t(language, "error_generic", error=e)})

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    st.session_state["search_running"] = True
    st.session_state["search_progress_message"] = t(language, "started")
    st.session_state["search_progress_value"] = 0.01
    st.session_state["search_error"] = ""
    st.session_state["search_events"] = events
    st.session_state["search_thread"] = thread
    st.session_state["search_stop_event"] = stop_event


def _request_stop(lang: str) -> None:
    stop_event: threading.Event | None = st.session_state.get("search_stop_event")
    if stop_event is not None:
        stop_event.set()
        st.session_state["search_progress_message"] = t(lang, "stopping")


def _render_results(lang: str, result: SearchResult) -> None:
    if result.stopped:
        st.warning(t(lang, "stopped_notice"))

    m1, m2, m3 = st.columns(3)
    m1.metric(t(lang, "metric_fetched"), result.fetched)
    m2.metric(t(lang, "metric_matched"), result.matched)
    m3.metric(t(lang, "metric_window_days"), f"{result.lookback_hours / 24:.1f}")

    if not result.items:
        st.info(t(lang, "empty_result"))
        return

    for idx, (scored, summary) in enumerate(result.items, start=1):
        paper = scored.paper
        sem = t(lang, "na") if scored.semantic_similarity is None else f"{scored.semantic_similarity:.3f}"
        st.markdown('<div class="paper-card">', unsafe_allow_html=True)
        st.markdown(f"**{idx}. {paper.title}**")
        st.markdown(
            f'<span class="pill">{t(lang, "pill_score")} {scored.score}</span>'
            f'<span class="pill">{t(lang, "pill_semantic")} {sem}</span>'
            f'<span class="pill">{paper.published.date()}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"[{t(lang, 'arxiv_link')}]({paper.url})")
        st.markdown(f"**{t(lang, 'summary')}**: {summary.summary_cn}")
        st.markdown(f"**{t(lang, 'highlights')}**: {' | '.join(summary.highlights)}")
        st.markdown(f"**{t(lang, 'recommendation')}**: {summary.recommendation}")
        st.markdown("</div>", unsafe_allow_html=True)


st.set_page_config(page_title="arxiv-tok dashboard", page_icon="📚", layout="wide")

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

if "ui_lang" not in st.session_state:
    st.session_state["ui_lang"] = "zh"

lang = st.session_state.get("ui_lang", "zh")
base_settings = _load_base_settings()
model_cfg = base_settings.model
provider = model_cfg.provider.strip().lower()
api_key_exists = bool(os.getenv(model_cfg.api_key_env, ""))
provider_requires_key = provider == "openai" or (model_cfg.require_api_key and provider != "ollama")
model_chat_ready = bool(model_cfg.enabled and model_cfg.model and ((not provider_requires_key) or api_key_exists))
embedding_ready = bool(model_cfg.embedding_model)

_ensure_search_state(lang)
_drain_search_events(lang)

st.markdown(
    f'<div class="hero-card"><h2>{t(lang, "hero_title")}</h2>'
    f'<p>{t(lang, "hero_desc")}</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header(t(lang, "lang_switch"))
    lang = st.radio(
        t(lang, "lang_switch"),
        options=["zh", "en"],
        format_func=lambda x: LANG_LABELS[x],
        horizontal=True,
        key="ui_lang",
        label_visibility="collapsed",
    )

    st.header(t(lang, "params"))

    st.subheader(t(lang, "time_window"))
    window_mode = st.selectbox(
        t(lang, "time_unit"),
        options=WINDOW_MODE_OPTIONS,
        index=1,
        format_func=lambda x: WINDOW_MODE_LABELS[x]["en" if lang == "en" else "zh"],
    )
    max_value = 3650 if window_mode == "days" else 120 if window_mode == "months" else 10
    default_value = 30 if window_mode == "days" else 1
    window_value = st.number_input(
        t(lang, "window_value"),
        min_value=1,
        max_value=max_value,
        value=default_value,
        step=1,
    )

    st.subheader(t(lang, "scope"))
    scope_mode = st.radio(
        t(lang, "scope_mode"),
        options=SCOPE_MODE_OPTIONS,
        index=0,
        format_func=lambda x: _scope_mode_label(lang, x),
        help=t(lang, "scope_mode_help"),
    )

    selected_domains: list[str] = []
    custom_categories_raw = ""
    if scope_mode == "preset":
        selected_domains = st.multiselect(
            t(lang, "preset_select"),
            options=list(DOMAIN_PRESETS.keys()),
            default=["ai_ml", "nlp"],
            format_func=lambda x: _domain_label(lang, x),
        )
        mapped_categories = sorted(
            {
                cat
                for domain in selected_domains
                for cat in DOMAIN_PRESETS.get(domain, {}).get("categories", [])
            }
        )
        if mapped_categories:
            st.caption(f"{t(lang, 'mapped_categories')}: " + ", ".join(mapped_categories))
    elif scope_mode == "advanced":
        custom_categories_raw = st.text_area(
            t(lang, "custom_categories"),
            value="cs.AI\ncs.LG\ncs.CL",
        )

    st.subheader(t(lang, "keyword_rules"))
    include_any_raw = st.text_area(
        t(lang, "include_any"),
        value="agent\nretrieval augmented generation",
    )
    include_all_raw = st.text_area(t(lang, "include_all"), value="")
    exclude_any_raw = st.text_area(t(lang, "exclude_any"), value="survey")

    st.subheader(t(lang, "semantic"))
    st.caption(f"{t(lang, 'semantic_provider')}: {provider}")
    semantic_on = st.checkbox(t(lang, "semantic_on"), value=(model_chat_ready and embedding_ready))
    semantic_queries_raw = st.text_area(
        t(lang, "semantic_queries"),
        value="multi-agent tool use\n跨语言检索增强生成",
        disabled=not semantic_on,
    )

    st.subheader(t(lang, "result_size"))
    top_k = st.slider(t(lang, "top_k"), min_value=1, max_value=100, value=15)
    max_results = st.slider(t(lang, "max_fetch"), min_value=50, max_value=2000, value=300, step=50)
    st.caption(t(lang, "max_fetch_tip"))

    run = st.button(
        t(lang, "start"),
        type="primary",
        use_container_width=True,
        disabled=bool(st.session_state.get("search_running")),
    )
    stop = st.button(
        t(lang, "stop"),
        use_container_width=True,
        disabled=not bool(st.session_state.get("search_running")),
    )

if stop:
    _request_stop(lang)
    st.rerun()

if run:
    include_any = _parse_terms(include_any_raw)
    include_all = _parse_terms(include_all_raw)
    exclude_any = _parse_terms(exclude_any_raw)
    semantic_queries = _parse_terms(semantic_queries_raw)

    if not include_any and not include_all and not (semantic_on and semantic_queries):
        st.warning(t(lang, "need_terms"))
        st.stop()

    if semantic_on and provider_requires_key and not api_key_exists:
        st.warning(t(lang, "no_api_key", env_name=model_cfg.api_key_env))
        semantic_on = False

    runtime_model_cfg = replace(base_settings.model, enabled=semantic_on and ((not provider_requires_key) or api_key_exists))
    runtime_settings = replace(base_settings, model=runtime_model_cfg)

    if scope_mode == "all":
        categories = ALL_DOMAIN_CATEGORY_WILDCARDS
    elif scope_mode == "preset":
        categories = sorted(
            {
                cat
                for domain in selected_domains
                for cat in DOMAIN_PRESETS.get(domain, {}).get("categories", [])
            }
        )
    else:
        categories = _parse_terms(custom_categories_raw)

    if not categories:
        st.warning(t(lang, "no_categories"))
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

    d, m, y = _build_window(window_mode, int(window_value))
    _start_search_job(
        runtime_settings,
        runtime_rules,
        days=d,
        months=m,
        years=y,
        top_k=int(top_k),
        max_results_per_category=int(max_results),
        language=lang,
    )
    st.rerun()

if st.session_state.get("search_running"):
    progress = float(st.session_state.get("search_progress_value", 0.0))
    st.progress(max(0.0, min(1.0, progress)))
    st.info(str(st.session_state.get("search_progress_message", t(lang, "running_fallback"))))
    st.caption(t(lang, "progress_hint"))

if st.session_state.get("search_error"):
    st.error(str(st.session_state["search_error"]))

if "dashboard_result" in st.session_state:
    _render_results(lang, st.session_state["dashboard_result"])
else:
    st.info(t(lang, "info_start"))

if st.session_state.get("search_running"):
    time.sleep(0.6)
    st.rerun()
