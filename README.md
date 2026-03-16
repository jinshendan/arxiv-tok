# arxiv-tok

[中文](#中文) | [English](#english)

---

## 中文

`arxiv-tok` 是一个用于“高效看论文”的 arXiv 智能检索与总结工具。

你可以在前端直接设置关键词、时间窗口和搜索范围，系统会自动抓取相关论文并生成摘要，帮助你快速筛选值得精读的工作。

### 功能亮点

- Dashboard 一键搜索（支持中文/英文界面切换）
- 支持全领域检索（计算机、数学、统计、物理、生物、金融、经济、电气等）
- 关键词规则匹配（`include_any / include_all / exclude_any`）
- 可选多 Provider 模型 API（OpenAI / DeepSeek / Qwen / Ollama）
- 自动生成论文摘要、要点和阅读建议
- 命令行模式支持批量检索与自动化
- 内置限流与重试，减少 arXiv 429 报错

### 快速开始

#### 1) 环境要求

- Python `3.11.x`

```bash
python3.11 --version
```

#### 2) 安装

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Windows PowerShell 激活：

```powershell
.venv\Scripts\Activate.ps1
```

#### 3) 启动 Dashboard

```bash
arxiv-agent dashboard
```

默认地址：`http://127.0.0.1:8501`

### 前端使用（推荐）

Dashboard 左侧可配置：

- 界面语言：中文 / English
- 时间窗口：天 / 月 / 年（整数）
- 搜索范围：
  - 全领域
  - 常用方向（中文多选，自动映射 arXiv 分类）
  - 高级自定义（手动填写 arXiv 分类）
- 关键词规则：`include_any / include_all / exclude_any`
- 语义匹配开关：启用后可填写 `semantic_queries`
- 结果数量：`top_k` 与每个分类抓取上限

支持实时进度显示，也可手动点击“停止搜索并返回当前结果”。

### 模型 API 配置（可选）

项目支持三种 Provider：

- `openai`
- `openai_compatible`（DeepSeek / Qwen 兼容接口 / 本地 OpenAI-compatible 网关）
- `ollama`（本地模型）

`config/settings.yaml` 示例：

```yaml
model:
  enabled: true
  provider: openai_compatible
  base_url: https://api.deepseek.com/v1
  api_key_env: DEEPSEEK_API_KEY
  require_api_key: true
  model: deepseek-chat
  embedding_model: text-embedding-3-large
  timeout_seconds: 60
```

本地 Ollama 示例：

```yaml
model:
  enabled: true
  provider: ollama
  base_url: http://127.0.0.1:11434
  require_api_key: false
  model: qwen2.5:7b-instruct
  embedding_model: nomic-embed-text
  timeout_seconds: 60
```

如果模型 API 不可用，系统会自动降级为关键词匹配和本地摘要，不会中断搜索。

### 命令行用法

CLI 默认自动找配置：

- 优先：`config/settings.local.yaml`、`config/keywords.local.yaml`
- 回退：`config/settings.yaml`、`config/keywords.yaml`
- 环境变量覆盖：`ARXIV_AGENT_SETTINGS`、`ARXIV_AGENT_KEYWORDS`

查看当前生效路径：

```bash
arxiv-agent paths
```

常用命令：

```bash
# 初始化数据库
arxiv-agent init-db

# 跑一次完整流程（抓取 + 过滤 + 总结 + 通知）
arxiv-agent run

# 定时运行
arxiv-agent schedule

# 时间窗口检索（简写）
arxiv-agent search --last 6m -p llm-agent -k 20
arxiv-agent search --last 1y -p rag -k 20
arxiv-agent search --last 2w -k 15
```

### 配置文件

- 全局配置：`config/settings.yaml`
- 关键词模板：`config/keywords.yaml`
- 环境变量示例：`.env.example`

建议先复制本地配置：

```bash
cp config/settings.yaml config/settings.local.yaml
cp config/keywords.yaml config/keywords.local.yaml
```

### 常见问题

#### 1) 遇到 `429 Too Many Requests`

这是 arXiv 限流，建议：

- 降低“每个分类抓取上限”（建议 `200-400`）
- 缩短时间窗口
- 减少分类数量
- 稍后重试

可调参数（`config/settings.yaml`）：

- `arxiv_min_request_interval_seconds`
- `arxiv_max_retries`
- `arxiv_page_size`

#### 2) 没有 OpenAI Key 能用吗？

可以。你可以：

- 使用 `ollama` 本地模型（无需 API key）
- 或使用不强制 key 的 `openai_compatible` 网关（`require_api_key: false`）

如果模型 API 不可用，语义匹配和 LLM 摘要会自动降级。

#### 3) 为什么结果为空？

通常是关键词过窄或时间窗口过短。先放宽 `include_any`，再增大时间窗口。

---

## English

`arxiv-tok` is an arXiv monitoring and summarization tool built to reduce paper triage time.

You can configure keywords, time windows, and search scope in a web dashboard, then get matched papers with concise summaries and reading recommendations.

### Highlights

- One-click Dashboard search (with Chinese/English UI switch)
- Cross-domain search support (CS, math, stats, physics, bio, finance, economics, EESS, etc.)
- Rule-based keyword filtering (`include_any / include_all / exclude_any`)
- Optional multi-provider model APIs (OpenAI / DeepSeek / Qwen / Ollama)
- Automatic paper summary, highlights, and read recommendation
- CLI mode for batch search and automation
- Built-in throttling/retries to reduce arXiv 429 failures

### Quick Start

#### 1) Requirements

- Python `3.11.x`

```bash
python3.11 --version
```

#### 2) Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Windows PowerShell activation:

```powershell
.venv\Scripts\Activate.ps1
```

#### 3) Launch Dashboard

```bash
arxiv-agent dashboard
```

Default URL: `http://127.0.0.1:8501`

### Dashboard Usage

Configure from the left panel:

- UI language: 中文 / English
- Time window: day / month / year (integer)
- Scope:
  - All domains
  - Common domains (human-friendly labels mapped to arXiv categories)
  - Advanced custom (manual arXiv category input)
- Keyword rules: `include_any / include_all / exclude_any`
- Semantic matching toggle with `semantic_queries`
- Result size controls: `top_k` and fetch cap per category

Live progress is shown during search. You can also stop the run and keep partial results.

### Model API Setup (Optional)

The project supports three providers:

- `openai`
- `openai_compatible` (DeepSeek / Qwen-compatible / local OpenAI-compatible gateways)
- `ollama` (local models)

Example (`config/settings.yaml`):

```yaml
model:
  enabled: true
  provider: openai_compatible
  base_url: https://api.deepseek.com/v1
  api_key_env: DEEPSEEK_API_KEY
  require_api_key: true
  model: deepseek-chat
  embedding_model: text-embedding-3-large
  timeout_seconds: 60
```

Local Ollama example:

```yaml
model:
  enabled: true
  provider: ollama
  base_url: http://127.0.0.1:11434
  require_api_key: false
  model: qwen2.5:7b-instruct
  embedding_model: nomic-embed-text
  timeout_seconds: 60
```

If model APIs are unavailable, the app gracefully falls back to lexical matching and local summaries.

### CLI Usage

CLI auto-resolves config files by default:

- Preferred: `config/settings.local.yaml` and `config/keywords.local.yaml`
- Fallback: `config/settings.yaml` and `config/keywords.yaml`
- Env overrides: `ARXIV_AGENT_SETTINGS`, `ARXIV_AGENT_KEYWORDS`

Inspect resolved paths:

```bash
arxiv-agent paths
```

Common commands:

```bash
# Initialize DB
arxiv-agent init-db

# Run full daily pipeline (fetch + filter + summarize + notify)
arxiv-agent run

# Start scheduler
arxiv-agent schedule

# Time-window search shorthand
arxiv-agent search --last 6m -p llm-agent -k 20
arxiv-agent search --last 1y -p rag -k 20
arxiv-agent search --last 2w -k 15
```

### Config Files

- Global settings: `config/settings.yaml`
- Keyword templates: `config/keywords.yaml`
- Env example: `.env.example`

Suggested local copies:

```bash
cp config/settings.yaml config/settings.local.yaml
cp config/keywords.yaml config/keywords.local.yaml
```

### FAQ

#### 1) `429 Too Many Requests`

This is arXiv rate limiting. Try:

- Lowering fetch cap per category (start with `200-400`)
- Shortening time window
- Reducing category count
- Retrying later

Tunable settings (`config/settings.yaml`):

- `arxiv_min_request_interval_seconds`
- `arxiv_max_retries`
- `arxiv_page_size`

#### 2) Can I use it without an OpenAI API key?

Yes. You can:

- Use local `ollama` models (no API key required)
- Or use an `openai_compatible` endpoint with `require_api_key: false`

If model APIs are unavailable, semantic matching and LLM summaries degrade automatically.

#### 3) Why are there no results?

Usually your query is too narrow or the time window is too short. Broaden `include_any` and increase window size.

---

## License

This project is released under the [MIT License](LICENSE).
