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

**始终同时获取 daily、weekly 两个时间段的结果**（脚本默认行为）。task 描述中可指定语言覆盖默认列表，但时间段不需要用户指定。

默认抓取语言：overall（不限语言）、Python、TypeScript、Rust、C++、C、Java、Go、Lua、Zig。overall 始终自动包含。可在仓库根 `config.json` 的 `github.default_languages` 中调整。

```bash
# 默认抓取（overall + 9 种语言，daily+weekly）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/github_trending.py

# 指定语言（overall 仍会自动包含，仍获取两个时间段）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/github_trending.py --languages Python,Go,Rust

# 仅获取单个时间段（不推荐，特殊场景使用）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/github_trending.py --since daily

# JSON 输出（按时间段分组）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/github_trending.py --json
```

**参数**:
- `--languages`: 逗号分隔的语言列表（默认: `Python,TypeScript,Rust,C++,C,Java,Go,Lua,Zig`，overall 始终自动包含）
- `--since`: 逗号分隔的时间段，可选 `daily`/`weekly`/`monthly`（默认: `daily,weekly`）
- `--limit`: 每个语言的最大条目数 (默认 10)
- `--json`: JSON 格式输出（按时间段分组为 `{"daily": [...], "weekly": [...]}`)

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

默认抓取列表由 `config.json` 的 `reddit.categories` 派生（扁平化 + 去重 + 大小写不敏感排序），覆盖 AI / LLM、Local LLM、ML / CV / NLP、AI Agent、Vibe Coding、量化交易、游戏开发、编程语言、Browser 等分类，共约 29 个 subreddit。要新增或调整分类与 subreddit，直接编辑 `config.json` 即可，`reddit.py` 与 `reddit_dedup.py` 共享同一份配置。task 描述中也可显式指定 subreddit 覆盖默认列表。

```bash
# 默认抓取（约 29 个 subreddit，hot 排序）
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

独立脚本，通过 Product Hunt GraphQL API 获取热门产品。支持两个时间段：
- **daily**（默认）：按官方 RANKING 排序，当前上榜产品
- **weekly**：`order: VOTES` + `postedAfter: <7 天前>`，过去一周票数最高的产品

**始终同时获取 daily、weekly 两个时间段的结果**（脚本默认行为）。

**需要设置环境变量**：
```bash
export PRODUCTHUNT_API_TOKEN="your_token_here"
```
访问 https://api.producthunt.com/v2/oauth/applications 获取 API Token。

```bash
# 默认抓取（daily + weekly 各 top 30）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py

# 指定话题
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py --topic tech

# 调整每个 period 的数量
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py --limit 50

# 关键词过滤
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py --keyword "AI,agent"

# 仅获取单个时间段（不推荐，特殊场景使用）
{baseDir}/.venv/bin/python3 {baseDir}/scripts/producthunt.py --period daily
```

**参数**:
- `--topic`: 按话题 slug 过滤（如 `tech`, `ai`）
- `--period`: 逗号分隔的时间段，可选 `daily`/`weekly`（默认: `daily,weekly`）
- `--limit`: 每个 period 的最大条目数（默认: 30）
- `--keyword`: 逗号分隔的关键词过滤（匹配名称、标语、描述）
- `--json`: JSON 格式输出（当前 stdout 始终为 JSON，按时间段分组为 `{"daily": [...], "weekly": [...]}`）

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

## 选择性执行

agent 必须根据用户的措辞推断**两个独立维度**的执行范围：

**维度 1：数据源选择**

- 默认：4 个源全部跑（GitHub Trending、Hacker News、Reddit、Product Hunt）
- 用户显式提到具体源名（"GitHub trending"、"HN"、"Hacker News"、"Reddit"、"r/...", "Product Hunt"、"PH"）→ 仅跑被提到的子集

**维度 2：产出类型（两层）**

| 类型 | 触发 | 行为 |
|------|------|------|
| **全量报告**（默认） | 默认行为 | 每个跑过的源生成一份完整 Markdown 列表，每条 item 含标题 + 链接 + ~100 字描述（详见下文【全量报告内容规范】） |
| **Top 深度解读**（opt-in） | "深度解读"、"详细分析"、"调研"、"Top 深度"、"deep dive" 等关键词 | 在 fetch 之后追加跑 dedup 找出今日新条目的 Top N，对每个 top item 做深度调研，按【结构 A/B】输出 400-600 字长文 |

**触发词→执行方案示例**：

| 用户表达 | 数据源 | 产出类型 |
|---------|--------|---------|
| "看下今日新闻" / "更新一下" | 全部 4 个 | 全量报告 |
| "看一下 Hacker News" | 仅 HN | 全量报告 |
| "GitHub trending 深度解读" | 仅 GitHub | 全量报告 + Top 深度解读 |
| "对今天的 Reddit Top 做调研" | 仅 Reddit | Top 深度解读（深度解读隐含产出，可不重复出全量） |
| "今天有什么值得深度看的" | 全部 4 个 | 全量报告 + Top 深度解读 |

> 不确定时，倾向"全部源 + 仅全量报告"作为安全默认。

## 执行策略

**必须使用 subagent 并行执行各数据源脚本**，以提高效率。

为每个被选中的数据源启动独立的 subagent，使用 `subagent_type=Bash` 并行执行脚本。

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

## 全量报告内容规范

**输出路径**: `{workDir}/news-monitor/`

**文件命名**: 按数据源分文件，每个跑过的源一份 Markdown：

- `{source}_yyyy-mm-dd_HH.md`，其中 `source ∈ {github, hackernews, reddit, producthunt}`
- 例：`github_2026-03-04_06.md`、`hackernews_2026-03-04_06.md`、`reddit_2026-03-04_06.md`、`producthunt_2026-03-04_06.md`

> **定时任务必须 per-source**（每个源一份文件、便于"一文件一条飞书消息"分发）。
> 用户手动触发若明确要求一份合并文件，可额外输出 `yyyy-mm-dd_HH.md`，但不替代 per-source 文件。

### 时间范围

用户可在 task 中指定时间范围（如"过去一周"、"最近3天"），**未指定时默认为过去 24 小时**。报告头部必须标注覆盖的时间范围。

各数据源的时间参数映射：

| 时间范围 | github_trending.py | reddit.py | hackernews.py | producthunt.py |
|---------|-------------------|-----------|---------------|----------------|
| 24h（默认）| 始终 `daily,weekly` | `--sort top --time day` | `--start <24h前>` | 始终 `daily,weekly` |
| 一周 | 始终 `daily,weekly` | `--sort top --time week` | `--start <7天前>` | 始终 `daily,weekly` |
| 一个月 | 始终 `daily,weekly` | `--sort top --time month` | `--start <30天前>` | 始终 `daily,weekly` |

> GitHub Trending 和 Product Hunt **始终同时获取 daily 和 weekly 两个时间段**，均不受用户指定的时间范围影响。

### 每条 item 的内容标准

报告中**每一条 item 必须包含三要素**：

1. **标题**：使用源数据中的 `title` / `name` / `full_name`
2. **链接**：使用源数据中的 `url` / `html_url` / `permalink`
3. **~100 字（约 5 句）描述**：由 agent **对每条 item 调用一次轻量级 `web_fetch`** 抓取目标页面，从首屏正文 / README / OG description / 摘要中提取要点后用中文压缩生成

**抓取与回退规则**：

- 描述**不能凭空编造**，必须基于 `web_fetch` 抓取到的真实内容
- 若 `web_fetch` 失败、超时或返回内容不足以提炼，回退到使用 fetch 脚本本身返回的 `description` / `selftext` / `tagline` 字段，并在描述末尾加注 `(摘自 raw)`
- **强烈建议用 subagent 并行抓取所有 item 的页面**（每个 item 一个 Task），避免串行慢

### 写入要求

脚本只输出到 stdout。agent 必须：

1. 收集所有 fetch 脚本的 JSON 输出
2. 对每条 item 并行调用 `web_fetch` 生成 ~100 字描述
3. 拼装为 markdown 报告
4. 确保输出目录存在（`mkdir -p {workDir}/news-monitor/`）
5. 为每个跑过的源分别写入 `{workDir}/news-monitor/{source}_yyyy-mm-dd_HH.md`

### 完整性

**所有获取到的条目必须全部列出，不得省略、节选或截断。** 宁可报告篇幅长，也不能丢失任何一条信息。禁止使用"节选"、"部分展示"、"更多内容请查看…"等缩略表述。

### Raw 数据保存

为便于调试和数据追溯，agent 在执行脚本后应保存原始 JSON 数据：

**目录**: `{workDir}/news-monitor/raw/`

**命名格式**: `{source}_{period}_yyyy-mm-dd_HH.json`

例如：
- `github_trending_daily_2026-03-07_16.json`、`github_trending_weekly_2026-03-07_16.json`
- `hackernews_week_2026-03-07_16.json`
- `reddit_week_2026-03-07_16.json`
- `producthunt_daily_2026-03-07_16.json`、`producthunt_weekly_2026-03-07_16.json`

**时间戳**：与同次运行的 per-source 报告 `{source}_yyyy-mm-dd_HH.md` 使用相同的时间戳，确保可追溯。

**执行顺序**：
1. 并行执行所有 fetch 脚本获取 JSON 数据
2. 保存各数据源的 raw JSON 文件（带时间后缀）
3. 并行调用 `web_fetch` 为每条 item 生成 ~100 字描述
4. 按平台拼装并分别写入 4 份 per-source md 文件 `{source}_yyyy-mm-dd_HH.md`

## 去重、过滤与深度解读

仅在用户触发"深度解读"等关键词时执行此管道。

### 去重脚本

`scripts/{github,hackernews,producthunt,reddit}_dedup.py` 是 4 个独立的 dedup 工具，用来从今日 raw JSON 中筛出"过去 N 天里没出现过"的新条目并取 Top N。它们的角色是 Top 深度解读管道的中间步骤，**不直接面向用户**。

**统一 CLI**：

| 参数 | 说明 |
|------|------|
| `--input PATH` / `-i PATH` | Raw JSON 输入文件；省略或传 `-` 则从 stdin 读 |
| `--top N` | Top N（默认 10）。Reddit 是按 category 各 Top N |
| `--json` | 输出 JSON（默认 Markdown）。**深度解读流程必须用 `--json`**，方便 agent 解析后驱动 |
| `--no-save` | 干跑：不写入今日 snapshot |

**Snapshot（去重状态）由脚本自管**，agent 不需要传任何路径：

- 目录：`config.json` 的 `dedup.snapshot_dir`（默认 `~/.openclaw/workspace/news-monitor/fullset`）
- 加载策略：扫该目录找 `{source}_fullset_YYYY-MM-DD.json`，取**最近 `dedup.lookback_days`（默认 14）天内、且日期早于今天**的最新一份作为基线 → 找不到则空集（→ 全部视为新）→ 即使断 1-13 天也不会"穿透"重新推荐之前出现过的内容
- 同一天多次运行结果稳定（基线总是排除今天的快照）
- 主流程结束后自动写 `{source}_fullset_{today}.json`（除非 `--no-save`）
- fullset 中的值是 `last_seen_date`，目前未被消费，留作未来 N 天过期清理使用
- 如需 bootstrap 历史 fullset，可单独调用 `dedup_common.bootstrap_from_raw`

### 话题过滤规则

**必须逐条检查**每个候选 item 的 title + description/selftext/tagline，与以下话题直接或间接相关的都删除，**严格执行，从严处理**:
- ❌ 社会、伦理
- ❌ 政策、法规
- ❌ 政治、地缘政治
- ❌ 娱乐、体育
- ❌ 招聘、求职、职场文化

### 深度调研要求

- 取前 N 条进入深度调研
- 单篇 **400-600 字**，按下文【结构 A】或【结构 B】组织
- 输出目录：`{workDir}/news-monitor/deep_dive/yyyy-mm-dd_HH/{source}/`
  - Reddit 再加一级 category 子目录，例如 `.../deep_dive/2026-04-18_14/reddit/AI%20%2F%20LLM/foo.md`
- 调研工具：`web_fetch` / `browser` / `web-chat` / `last30days`（按需组合）
- 每个 top item 用一个 subagent 独立调研 → 并行加速

#### 【结构 A】针对开源项目（GitHub）

1. **定位与痛点剖析**：项目是什么？解决什么具体的开发痛点？面向哪类用户？
2. **核心架构与技术细节**：技术栈？独特工程设计？（必须 `web_fetch` 拉取 README + `web-chat` 做深度解析）
3. **竞品对比与生态站位**：替代方案？相对优劣势？在所属生态中的位置？
4. **开发者反馈与局限性**：社区评价、issue 中暴露的局限？
5. **附带链接**：GitHub Repo + 官网 / 文档（如有）

#### 【结构 B】针对新闻 / 帖子 / 产品（HN, Reddit, Product Hunt）

1. **事件背景**：核心诉求 / 事件背景，发生了什么？为什么现在出现？
2. **核心观点 / 产品机制**：核心主张或产品的运行机制（深度查阅原文 / 官网 / Demo）
3. **社区热议与争议点**：**必须深度阅读评论区**，举 2-4 个具体讨论例子，正反方意见 pros / cons 对立必须体现
4. **行业影响与未来展望**：长远影响、相关趋势
5. **附带链接**：原帖 + 原始新闻 / 产品链接（外部 URL，如有）

### 调用步骤
1. fetch raw JSON 并落盘
```bash
{baseDir}/.venv/bin/python3 {baseDir}/scripts/reddit.py posts --sort top --time day --limit 25 --json \
    > {workDir}/news-monitor/raw/reddit_2026-04-18_14.json
```

2. dedup 找出 Top ⌈N×2⌉
```bash
{baseDir}/.venv/bin/python3 {baseDir}/scripts/reddit_dedup.py \
    --input {workDir}/news-monitor/raw/reddit_2026-04-18_14.json \
    --top <N×2> --json > /tmp/reddit_top.json
```

3. 话题过滤 + 截取 Top N
    - 解析 dedup output JSON，逐条检查 title + description/selftext/tagline
    - 参考**话题过滤规则**丢弃不符合话题范围的条目
    - 然后从过滤结果中取前 N 条进入深度调研

4. 参考**深度调研要求**启动 subagent 做深度调研, 输出到要求中指定的目录。

## 配置文件简介

仓库根的 `config.json` 集中管理所有可调项，按数据源分区：

- `github`：`default_languages`、`language_colors`
- `hackernews`：`page_paths`、`default_pages`、`default_limit`、`default_min_points`
- `reddit`：`redlib_bases`、`category_order`、`categories`（**`reddit.py` 的默认抓取列表由这里派生**，避免与 `reddit_dedup.py` 漂移）
- `producthunt`：`default_limit`、`default_topic`
- `dedup`：`snapshot_dir`（支持 `~`）、`lookback_days`、`expiry_days`（fullset 中 `last_seen_date` 超过此天数的 key 会在 `update_fullset` 时被自动清理，默认 90）

**Fallback 策略**：`config.json` 不存在、某段或某键缺失，脚本均自动回退到代码内 fallback 常量（行为与无配置文件时完全一致）。CLI 参数依然存在并且优先级高于配置文件。`config.json` 中**不放任何敏感信息**（如 `PRODUCTHUNT_API_TOKEN` 仍走环境变量）。
