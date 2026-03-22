# News Monitor

实时新闻聚合器，从多个来源获取热点内容。

## 数据源

- **GitHub Trending** - 热门开源项目
- **Hacker News** - 技术新闻
- **Reddit** - 多主题社区讨论
- **Product Hunt** - 每日热门产品

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
