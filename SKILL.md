---
name: news-monitor
description: "新闻聚合器 | News Aggregator。从多个来源获取实时新闻：Hacker News（HTML 爬取）、GitHub Trending（多语言+多时间段）、Reddit（RSS）、Product Hunt（GraphQL API）。支持主题聚焦模式（多维度搜索策略）、全网扫描、单源深度扫描。触发词：新闻、news、热点、trending、AI动态、科技快讯、开源趋势。"
metadata:
  openclaw:
    emoji: "📰"
    category: "news"
    tags: ["news", "aggregator", "ai", "tech", "trending", "github", "reddit", "hackernews", "producthunt"]
    requires:
      bins: ["python3", "curl"]
---

# News Aggregator

从多个来源获取、过滤和深度分析实时新闻内容。

## 运行环境

脚本依赖 `requests`、`beautifulsoup4`、`lxml`，已安装在项目自带的 venv 中。

**执行脚本时，必须使用 venv 内的 Python 解释器**，而不是系统 `python3`：

```bash
{baseDir}/.venv/bin/python3 {baseDir}/scripts/<script>.py [args...]
```

如果 venv 丢失或损坏，重建步骤：

```bash
python3 -m venv {baseDir}/.venv
{baseDir}/.venv/bin/pip install -r {baseDir}/requirements.txt
```

也可使用 `uv`（如已安装）加速安装：

```bash
uv venv {baseDir}/.venv
uv pip install -r {baseDir}/requirements.txt --python {baseDir}/.venv/bin/python3
```

## 数据源与工具

### GitHub Trending（github_trending.py）

独立脚本，专用于获取 GitHub Trending 项目。支持按编程语言和时间段过滤，多语言并发抓取。

**始终同时获取 daily、weekly、monthly 三个时间段的结果**（脚本默认行为）。task 描述中可指定语言覆盖默认列表，但时间段不需要用户指定。

默认抓取语言：overall（不限语言）、Python、TypeScript、Rust、C++、C、Java、Go、Lua。overall 始终自动包含。

```bash
# 默认抓取（overall + 8 种语言，daily+weekly+monthly）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/github_trending.py

# 指定语言（overall 仍会自动包含，仍获取三个时间段）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/github_trending.py --languages Python,Go,Rust

# 仅获取单个时间段（不推荐，特殊场景使用）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/github_trending.py --since daily

# JSON 输出（按时间段分组）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/github_trending.py --json
```

**参数**:
- `--languages`: 逗号分隔的语言列表（默认: `Python,TypeScript,Rust,C++,C,Java,Go,Lua`，overall 始终自动包含）
- `--since`: 逗号分隔的时间段（默认: `daily,weekly,monthly`，即同时获取三个时间段）
- `--limit`: 每个语言的最大条目数 (默认 10)
- `--json`: JSON 格式输出（按时间段分组为 `{"daily": [...], "weekly": [...], "monthly": [...]}`)

**输出字段**:
- `full_name`: owner/repo
- `description`: 项目描述
- `stargazers_count`: 总 stars
- `forks_count`: fork 数
- `language`: 编程语言
- `html_url`: 项目链接
- `period_stars`: 时间段内新增 stars
- `period_range`: today / this week / this month

### Reddit（reddit.py）

独立脚本，通过公开 RSS（Atom）端点获取 Reddit 帖子。支持获取帖子和搜索，可指定多个 subreddit。无需认证。

> 注意：RSS 端点不包含 score（点赞数）和评论数。排序由 Reddit 服务端完成（hot/top/new 等）。

默认抓取以下 subreddit：`algotrading`, `ArtificialIntelligence`, `browsers`, `ChatGPTCoding`, `CLine`, `ComputerVision`, `java`, `LanguageTechnology`, `LLM`, `MachineLearning`, `quant`, `robloxgamedev`, `rust`。task 描述中可指定其他 subreddit 覆盖默认列表。

```bash
# 默认抓取（13 个 subreddit，hot 排序）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/reddit.py posts --sort hot --limit 10

# 指定 subreddit
{baseDir}/.venv/bin/python3 {baseDir}/scripts/reddit.py posts MachineLearning,LocalLLaMA,programming --sort hot --limit 10

# 获取 top 帖子（按时间段）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/reddit.py posts MachineLearning --sort top --time week --limit 20

# 在多个 subreddit 中搜索
{baseDir}/.venv/bin/python3 {baseDir}/scripts/reddit.py search MachineLearning,LocalLLaMA "RAG" --sort top --time week

# 全站搜索
{baseDir}/.venv/bin/python3 {baseDir}/scripts/reddit.py search all "AI agent" --limit 15

# JSON 输出
{baseDir}/.venv/bin/python3 {baseDir}/scripts/reddit.py posts MachineLearning --sort top --time week --limit 10 --json
```

**参数**:
- `posts [subreddits]`: 获取帖子，subreddits 用逗号分隔（可选，不指定则使用默认列表）
  - `--sort`: `hot` | `new` | `top` | `rising` (默认 hot)
  - `--time`: `day` | `week` | `month` | `year` | `all` (仅 top 有效)
  - `--limit`: 每个 subreddit 的最大条目数 (默认 25)
- `search <subreddits> <query>`: 搜索帖子（用 `all` 全站搜索）
  - `--sort`: `relevance` | `top` | `new` | `comments` (默认 relevance)
  - `--time`: 同上
- `--json`: JSON 格式输出

**输出字段**:
- `id`: 帖子 ID
- `subreddit`: 来源 subreddit
- `title`: 标题
- `author`: 作者
- `url`: 外部链接（self post 为空）
- `permalink`: Reddit 讨论链接
- `published`: 发布时间（ISO 8601）
- `selftext`: 正文（前 500 字符）

### Hacker News（hackernews.py）

独立脚本，从 Hacker News 三个页面获取故事，HTML 分页爬取。支持按 points、时间、关键词过滤，以 title 去重，按 points 降序排序。

**三个页面：**

| 页面参数 | URL | 说明 |
|---------|-----|------|
| `news` | `https://news.ycombinator.com/news` | 热门故事（Top Stories） |
| `front` | `https://news.ycombinator.com/front` | 曾上首页的故事 |
| `show` | `https://news.ycombinator.com/show` | Show HN |

默认同时获取三个页面（`news,front,show`）。

```bash
# 默认抓取（三个页面，min-points=50，limit=100）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/hackernews.py

# 仅获取 Show HN
{baseDir}/.venv/bin/python3 {baseDir}/scripts/hackernews.py --pages show

# 指定时间范围（过滤掉早于此时间的故事）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/hackernews.py --start 2026-03-04

# 调整 points 阈值
{baseDir}/.venv/bin/python3 {baseDir}/scripts/hackernews.py --min-points 100

# 关键词过滤
{baseDir}/.venv/bin/python3 {baseDir}/scripts/hackernews.py --keyword "AI,LLM,GPT"

# JSON 输出
{baseDir}/.venv/bin/python3 {baseDir}/scripts/hackernews.py --json
```

**参数**:
- `--pages`: 逗号分隔的页面类型（默认: `news,front,show`）
- `--limit`: 最大返回条目数，0 表示全部（默认: 100）
- `--start`: 过滤掉早于此时间的故事（格式: `YYYY-MM-DD` 或 `YYYY-MM-DDTHH:MM:SS`）
- `--min-points`: 最低 points 阈值（默认: 50）
- `--keyword`: 逗号分隔的关键词过滤（匹配标题）
- `--json`: JSON 格式输出

**输出字段**:
- `id`: 故事 ID
- `title`: 标题
- `url`: 外部链接
- `score`: points
- `comments`: 评论数
- `author`: 作者
- `created`: ISO 8601 时间
- `hn_url`: Hacker News 讨论链接
- `source_page`: 来源页面（news/front/show）

### Product Hunt（producthunt.py）

独立脚本，通过 Product Hunt GraphQL API 获取每日热门产品（按官方 RANKING 排序）。

**需要设置环境变量**：
```bash
export PRODUCTHUNT_API_TOKEN="your_token_here"
```
访问 https://api.producthunt.com/v2/oauth/applications 获取 API Token。

```bash
# 默认抓取（每日 top 30）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py

# 指定话题
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py --topic tech

# 调整数量
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py --limit 50

# 关键词过滤
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py --keyword "AI,agent"

# JSON 输出
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py --json
```

**参数**:
- `--topic`: 按话题 slug 过滤（如 `tech`, `ai`）
- `--limit`: 最大条目数（默认: 30）
- `--keyword`: 逗号分隔的关键词过滤（匹配名称、标语、描述）
- `--json`: JSON 格式输出

**输出字段**:
- `id`: 产品 ID
- `name`: 产品名称
- `tagline`: 标语
- `description`: 描述
- `url`: Product Hunt 链接
- `website`: 产品官网
- `votes_count`: 点赞数
- `comments_count`: 评论数
- `reviews_count`: 评价数
- `reviews_rating`: 评价评分
- `created_at`: 发布时间
- `featured_at`: 精选时间
- `daily_rank`: 每日排名
- `topics`: 话题列表
- `thumbnail`: 缩略图 URL

## 执行策略

**必须使用 subagent 并行执行各数据源脚本**，以提高效率。

为每个数据源（GitHub Trending、Reddit、Hacker News、Product Hunt）启动独立的 subagent，使用 `subagent_type=Bash` 并行执行脚本。

示例：
```python
Task(
    subagent_type=Bash,
    description=f"Fetch GitHub Trending",
    prompt=f"cd {baseDir} && .venv/bin/python3 scripts/github_trending.py --json",
    run_in_background=True
)
```

等待所有 subagent 完成后，收集各自输出的 JSON 数据，然后进行格式化和写入。

## 输出规范

**输出路径**: `{workDir}/news-monitor/`

**文件命名**: `yyyy-mm-dd_HH.md`

例如：
- 2026年3月4日16点 → `2026-03-04_16.md`
- 2026年3月5日09点 → `2026-03-05_09.md`

### 时间范围

用户可在 task 中指定时间范围（如"过去一周"、"最近3天"），**未指定时默认为过去 24 小时**。报告头部必须标注覆盖的时间范围。

各数据源的时间参数映射：

| 时间范围 | github_trending.py | reddit.py | hackernews.py | producthunt.py |
|---------|-------------------|-----------|---------------|----------------|
| 24h（默认）| 始终 `daily,weekly,monthly` | `--sort top --time day` | `--start <24h前>` | 始终 daily |
| 一周 | 始终 `daily,weekly,monthly` | `--sort top --time week` | `--start <7天前>` | 始终 daily |
| 一个月 | 始终 `daily,weekly,monthly` | `--sort top --time month` | `--start <30天前>` | 始终 daily |

> GitHub Trending **始终获取全部三个时间段**，Product Hunt 只获取每日热门（top 30），均不受用户指定的时间范围影响。

### 写入要求

脚本只输出到 stdout。agent 必须：

1. 收集所有脚本输出
2. 格式化为 markdown 报告
3. 确保输出目录存在（`mkdir -p {workDir}/news-monitor/`）
4. 将报告写入 `{workDir}/news-monitor/yyyy-mm-dd_HH.md`

### 完整性

**所有获取到的条目必须全部列出，不得省略、节选或截断。** 宁可报告篇幅长，也不能丢失任何一条信息。禁止使用"节选"、"部分展示"、"更多内容请查看…"等缩略表述。

### Raw 数据保存

为便于调试和数据追溯，agent 在执行脚本后应保存原始 JSON 数据：

**目录**: `{workDir}/news-monitor/raw/`

**命名格式**: `{source}_{period}_yyyy-mm-dd_HH.json`

例如：
- `github_trending_2026-03-07_16.json`
- `hackernews_week_2026-03-07_16.json`
- `reddit_week_2026-03-07_16.json`
- `producthunt_2026-03-07_16.json`

**时间戳**：与汇总报告 `yyyy-mm-dd_HH.md` 使用相同的时间戳，确保可追溯。

**执行顺序**：
1. 并行执行所有脚本获取 JSON 数据
2. 保存各数据源的 raw JSON 文件（带时间后缀）
3. 格式化并写入汇总报告 md 文件
