# arxiv-agent

一个基于 Python 3.11.9 的 arXiv 论文监控 Agent：

- 每天抓取新发布论文
- 按自定义关键词规则过滤
- 调用 LLM 生成中文摘要与阅读建议
- 发送通知（控制台 / Email / Telegram）
- 支持定时运行

## 1. 环境准备

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## 2. 配置

1. 复制配置并修改：

```bash
cp config/settings.yaml config/settings.local.yaml
cp config/keywords.yaml config/keywords.local.yaml
cp .env.example .env
```

2. 在 `config/keywords.local.yaml` 里配置你的关键词规则（支持 `include_all/include_any/exclude_any`）。

3. 如果要开启 LLM 摘要，把 `openai.enabled: true` 并配置环境变量 `OPENAI_API_KEY`。

4. 如果要开启通知，打开 `notify.email.enabled` 或 `notify.telegram.enabled` 并配置对应参数。

## 3. 运行

初始化数据库：

```bash
arxiv-agent init-db --settings config/settings.local.yaml
```

手动跑一次：

```bash
arxiv-agent run --settings config/settings.local.yaml --keywords config/keywords.local.yaml
```

启动定时任务（阻塞前台）：

```bash
arxiv-agent schedule --settings config/settings.local.yaml --keywords config/keywords.local.yaml
```

## 4. 筛选规则说明

- `include_all`: 这些词必须都出现，否则不命中。
- `include_any`: 这些词至少出现一个。
- `exclude_any`: 出现任意一个即排除。
- `min_score`: 最低得分阈值。
- `max_items_per_run`: 每次运行最多输出多少篇。

当前打分逻辑：

- 每个 `include_all` 命中 +2 分
- 每个 `include_any` 命中 +1 分
- 有 `exclude_any` 命中直接剔除

## 5. 目录结构

```text
.
├── config/
│   ├── settings.yaml
│   └── keywords.yaml
├── data/
├── src/arxiv_agent/
│   ├── arxiv_client.py
│   ├── cli.py
│   ├── config.py
│   ├── db.py
│   ├── filtering.py
│   ├── notifier.py
│   ├── pipeline.py
│   ├── scheduler.py
│   └── summarizer.py
└── README.md
```

## 6. 后续增强建议

- 用 embedding 召回替代纯关键词匹配。
- 增加网页 Dashboard（查看历史摘要、标记有用/无用）。
- 将 SQLite 升级到 Postgres，并接入多用户。
