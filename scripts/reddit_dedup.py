#!/usr/bin/env python3
"""
Reddit dedup — emit Top-N new posts per category not seen in a recent baseline snapshot.

Input
-----
Raw JSON produced by `scripts/reddit.py posts ... --json` (a flat list of post
dicts, each with a `subreddit` field). Pass via `--input PATH` or stdin.

Output
------
Markdown (default) or JSON (`--json`) to stdout. Items are grouped by category
(based on `reddit.categories` in config.json — subreddits not mapped go to
"Other"), each category emits up to `--top` previously-unseen posts sorted by
`published` descending.

State
-----
Snapshot persistence is auto-managed by `dedup_common` using `dedup.snapshot_dir`
and `dedup.lookback_days` from config.json. Use `--no-save` for dry runs.
"""

import argparse
import json
import sys

import dedup_common
from _config import get_section

SOURCE = "reddit"

_FALLBACK_CATEGORIES: dict[str, list[str]] = {
    "AI / LLM": ["ChatGPT", "ClaudeAI", "LLM", "artificial"],
    "Local LLM": ["LocalLLaMA", "LocalLLM", "unsloth"],
    "ML / CV / NLP": ["MachineLearning", "computervision", "LanguageTechnology"],
    "AI Agent": ["AI_Agents", "openclaw", "OpenClawUsers"],
    "Vibe Coding": ["ClaudeCode", "CLine", "GithubCopilot", "opencodeCLI", "vibecoding"],
    "量化交易": ["algotrading", "quant"],
    "游戏开发": ["godot", "IndieDev", "IndieGaming", "robloxgamedev", "aigamedev"],
    "编程语言": ["rust", "java", "lua"],
    "Browser": ["browsers"],
}

_FALLBACK_ORDER = [
    "AI / LLM", "Local LLM", "ML / CV / NLP", "AI Agent", "Vibe Coding",
    "量化交易", "游戏开发", "编程语言", "Browser", "Other",
]


def _load_category_config() -> tuple[dict[str, str], list[str]]:
    """Read reddit.{categories,category_order} and return (sub→cat, order)."""
    cfg = get_section("reddit")
    categories = cfg.get("categories")
    if not isinstance(categories, dict) or not categories:
        categories = _FALLBACK_CATEGORIES
    order = cfg.get("category_order")
    if not isinstance(order, list) or not order:
        order = _FALLBACK_ORDER

    sub_to_cat: dict[str, str] = {}
    for cat, subs in categories.items():
        if not isinstance(subs, list):
            continue
        for sub in subs:
            sub_to_cat[str(sub)] = str(cat)

    if "Other" not in order:
        order = list(order) + ["Other"]
    return sub_to_cat, list(order)


CATEGORY_MAP, CATEGORY_ORDER = _load_category_config()


def reddit_keys(item: dict) -> list[str]:
    keys = [str(item.get("id", "") or "")]
    if item.get("permalink"):
        keys.append(str(item["permalink"]))
    return [k for k in keys if k]


def is_new(item: dict, fullset: dict[str, str]) -> bool:
    return all(k not in fullset for k in reddit_keys(item))


def group_by_category(items: list[dict]) -> dict[str, list[dict]]:
    by_cat: dict[str, list[dict]] = {cat: [] for cat in CATEGORY_ORDER}
    for item in items:
        sub = item.get("subreddit", "") or ""
        cat = CATEGORY_MAP.get(sub, "Other")
        by_cat.setdefault(cat, []).append(item)
    return by_cat


def select_top(by_cat: dict[str, list[dict]], top: int) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for cat in CATEGORY_ORDER:
        items = by_cat.get(cat) or []
        items.sort(key=lambda x: x.get("published", "") or "", reverse=True)
        chosen = items[:top]
        if chosen:
            out[cat] = chosen
    return out


def format_md(top_by_cat: dict[str, list[dict]]) -> str:
    blocks: list[str] = []
    for cat, items in top_by_cat.items():
        lines = [f"# {cat}", ""]
        for item in items:
            title = item.get("title", "") or ""
            url = item.get("url") or item.get("permalink") or ""
            sub = item.get("subreddit", "") or ""
            lines.append(f"- [{title}]({url}) — r/{sub} | {cat}")
            selftext = (item.get("selftext") or "")[:300].strip()
            if selftext:
                lines.append(f"  - {selftext}")
        lines.append("")
        blocks.append("\n".join(lines))
    return "\n".join(blocks).strip()


def format_json(top_by_cat: dict[str, list[dict]]) -> str:
    payload = {
        "source": SOURCE,
        "generated_at": dedup_common.today_str(),
        "by_category": top_by_cat,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find Top-N new Reddit posts per category vs the most recent baseline snapshot."
    )
    parser.add_argument("--input", "-i", default=None,
                        help="Raw JSON path; '-' or omitted reads from stdin.")
    parser.add_argument("--top", type=int, default=10, help="Top N per category (default 10).")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not write today's snapshot (dry run).")
    args = parser.parse_args()

    raw = dedup_common.read_input(args.input)
    if not isinstance(raw, list):
        print("Error: reddit dedup expects a JSON list of posts.", file=sys.stderr)
        sys.exit(1)

    fullset = dedup_common.load_latest_snapshot(SOURCE)
    new_items = [i for i in raw if is_new(i, fullset)]
    by_cat = group_by_category(new_items)
    top_by_cat = select_top(by_cat, args.top)

    print(format_json(top_by_cat) if args.json else format_md(top_by_cat))

    if not args.no_save:
        flat = [it for items in top_by_cat.values() for it in items]
        dedup_common.update_fullset(fullset, flat, reddit_keys)
        path = dedup_common.save_snapshot(SOURCE, fullset)
        print(f"[dedup_common] snapshot saved: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
