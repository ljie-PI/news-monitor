# News Monitor

实时新闻聚合器，从多个来源获取热点内容，并支持每日去重与深度调研。

## 数据源

- **GitHub Trending** - 热门开源项目
- **Hacker News** - 技术新闻
- **Reddit** - 多主题社区讨论
- **Product Hunt** - 每日热门产品

## 功能特性

- **两种报告产出**：
  - **全量报告**（默认）：每个数据源一份 Markdown，含标题、链接、~100 字描述
  - **Top 深度解读**（按需）：对每日 Top 项做深度调研，每条产出 400-600 字长文
- **每日去重**：自动识别"今天才出现的新内容"，避免在 Top 深度解读中重复推送昨天已经看过的条目
- **可定制**：通过仓库根的 `config.json` 调整数据源默认列表、阈值、Reddit 分类映射等

## 推荐的定时任务

| 节奏 | 时间 | 内容 |
|------|------|------|
| 每天 | 06:00 | 4 个数据源全量报告，每源一份文件 |
| 每天 | 07:00 | Hacker News + Reddit（AI / Agent 相关分类）Top 深度调研 |
| 每周六 | 07:00 | GitHub Trending + Product Hunt Top 深度调研 |

## 快速开始

```bash
# 安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 设置环境变量
source ~/.openclaw/workspace/.env

# 运行脚本
.venv/bin/python3 scripts/github_trending.py --json
.venv/bin/python3 scripts/hackernews.py --json
.venv/bin/python3 scripts/reddit.py posts --json
.venv/bin/python3 scripts/producthunt.py --json
```

## 文档

详见 [SKILL.md](SKILL.md)

