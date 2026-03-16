# arxiv-tok

`arxiv-tok` 是一个用于“高效看论文”的 arXiv 智能检索与总结工具。

你可以在前端界面里直接设置关键词、时间窗口和搜索范围，系统会自动抓取相关论文并生成中文摘要，帮助你快速筛选值得精读的工作。

## 功能亮点

- 前端 Dashboard 一键搜索（中文界面）
- 支持全领域检索（计算机、数学、统计、物理、生物、金融、经济、电气等）
- 关键词规则匹配（`include_any / include_all / exclude_any`）
- 可选 OpenAI 语义匹配（支持中英文语义相近检索）
- 自动生成论文摘要、要点和阅读建议
- 命令行模式可做批量检索与自动化
- 内置限流与重试，减少 arXiv 429 报错

## 适用场景

- 每周跟踪某个研究方向的新论文
- 快速做某个主题的文献扫描
- 给组会/项目做论文候选池
- 缩短“找论文 + 初筛”时间

## 快速开始

### 1) 环境要求

- Python `3.11.x`

检查版本：

```bash
python3.11 --version
```

### 2) 安装

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

### 3) 启动 Dashboard

```bash
arxiv-agent dashboard
```

默认地址：`http://127.0.0.1:8501`

## 前端使用（推荐）

在 Dashboard 左侧设置：

- 时间窗口：按“天 / 月 / 年”
- 搜索范围三选一：
  - 全领域（无需了解分类代码）
  - 常用方向（中文多选，自动映射 arXiv 分类）
  - 高级自定义（手动填写 arXiv 分类）
- 关键词规则：
  - `include_any` 至少命中一个
  - `include_all` 必须全部命中
  - `exclude_any` 命中即排除
- 语义匹配开关：启用后可填写 `semantic_queries`
- 结果数量：`top_k` 与每个分类抓取上限

点击“开始搜索”后，会返回：

- 论文标题与 arXiv 链接
- 中文摘要
- 关键信息要点
- 阅读建议

搜索过程中会显示实时进度，你也可以点击“停止搜索并返回当前结果”提前结束任务。

## OpenAI 语义匹配（可选）

如果希望支持“语义相近”而非只做关键词字面匹配：

1. 设置环境变量：

```bash
export OPENAI_API_KEY="your_api_key"
```

2. 在前端打开“启用 OpenAI 语义匹配”

如果未设置 API Key，系统会自动降级为关键词匹配，不会中断搜索。

## 命令行用法

### 初始化数据库

```bash
arxiv-agent init-db --settings config/settings.yaml
```

### 跑一次每日任务流（抓取 + 过滤 + 总结 + 通知）

```bash
arxiv-agent run --settings config/settings.yaml --keywords config/keywords.yaml
```

### 定时运行

```bash
arxiv-agent schedule --settings config/settings.yaml --keywords config/keywords.yaml
```

### 按时间窗口检索（近几个月 / 近1年）

```bash
# 近 6 个月
arxiv-agent search --settings config/settings.yaml --keywords config/keywords.yaml --months 6 --profile llm-agent --top-k 20

# 近 1 年
arxiv-agent search --settings config/settings.yaml --keywords config/keywords.yaml --years 1 --profile rag --top-k 20
```

## 配置文件

- 全局配置：`config/settings.yaml`
- 关键词模板：`config/keywords.yaml`
- 环境变量示例：`.env.example`

建议先复制本地配置：

```bash
cp config/settings.yaml config/settings.local.yaml
cp config/keywords.yaml config/keywords.local.yaml
```

然后在运行命令时使用 `*.local.yaml`。

## 常见问题

### 1) 遇到 `429 Too Many Requests`

这是 arXiv 限流。建议：

- 降低“每个分类抓取上限”（先用 `200-400`）
- 缩短时间窗口
- 减少分类数量
- 稍后重试

项目已内置请求间隔与重试机制，默认参数在 `config/settings.yaml` 可调：

- `arxiv_min_request_interval_seconds`
- `arxiv_max_retries`
- `arxiv_page_size`

### 2) 没有 OpenAI Key 能用吗？

可以。只是语义匹配和 LLM 摘要能力会降级为本地规则/摘要。

### 3) 为什么结果为空？

通常是关键词过窄或时间窗口过短。先放宽 `include_any`，再增大时间窗口。

## 项目结构

```text
.
├── config/
├── src/arxiv_agent/
│   ├── dashboard.py
│   ├── search_service.py
│   ├── arxiv_client.py
│   ├── filtering.py
│   ├── summarizer.py
│   └── ...
├── tests/
└── README.md
```

## 许可证

本项目采用 [MIT License](LICENSE) 开源发布。
