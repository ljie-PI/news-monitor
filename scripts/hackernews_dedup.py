#!/usr/bin/env python3
"""
Hacker News dedup — emit Top-N new stories not seen in a recent baseline snapshot.

Input
-----
Raw JSON produced by `scripts/hackernews.py --json` (a flat list of story dicts).
Pass via `--input PATH` or stdin.

Output
------
Markdown (default) or JSON (`--json`) to stdout. Top N is selected from the
not-yet-seen items, sorted by `score` descending.

State
-----
Snapshot persistence is auto-managed by `dedup_common` using `dedup.snapshot_dir`
and `dedup.lookback_days` from config.json. Use `--no-save` for dry runs.
"""

import argparse
import json
import sys

import dedup_common

SOURCE = "hackernews"


def hn_keys(item: dict) -> list[str]:
    keys = [str(item.get("id", "") or "")]
    if item.get("url"):
        keys.append(str(item["url"]))
    return [k for k in keys if k]


def is_new(item: dict, fullset: dict[str, str]) -> bool:
    return all(k not in fullset for k in hn_keys(item))


def format_md(items: list[dict]) -> str:
    if not items:
        return "# Hacker News\n"
    lines = ["# Hacker News", ""]
    for i, item in enumerate(items, 1):
        title = item.get("title", "") or ""
        url = item.get("url") or item.get("hn_url") or ""
        score = item.get("score", 0) or 0
        comments = item.get("comments", 0) or 0
        lines.append(f"{i}. [{title}]({url}) — {score} points, {comments} comments")
        if item.get("hn_url") and item.get("url"):
            lines.append(f"   - [HN Discussion]({item['hn_url']})")
    return "\n".join(lines)


def format_json(items: list[dict]) -> str:
    payload = {
        "source": SOURCE,
        "generated_at": dedup_common.today_str(),
        "items": items,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find Top-N new HN stories vs the most recent baseline snapshot."
    )
    parser.add_argument("--input", "-i", default=None,
                        help="Raw JSON path; '-' or omitted reads from stdin.")
    parser.add_argument("--top", type=int, default=10, help="Top N (default 10).")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not write today's snapshot (dry run).")
    args = parser.parse_args()

    raw = dedup_common.read_input(args.input)
    if not isinstance(raw, list):
        print("Error: hackernews dedup expects a JSON list of stories.", file=sys.stderr)
        sys.exit(1)

    fullset = dedup_common.load_latest_snapshot(SOURCE)
    new_items = [i for i in raw if is_new(i, fullset)]
    new_items.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
    top_items = new_items[: args.top]

    print(format_json(top_items) if args.json else format_md(top_items))

    if not args.no_save:
        dedup_common.update_fullset(fullset, top_items, hn_keys)
        path = dedup_common.save_snapshot(SOURCE, fullset)
        print(f"[dedup_common] snapshot saved: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
