#!/usr/bin/env python3
"""
Product Hunt dedup — emit Top-N new products not seen in a recent baseline snapshot.

Input
-----
Raw JSON produced by `scripts/producthunt.py` (a dict keyed by period —
typically `daily`/`weekly` — whose values are lists of product dicts), or a
flat list of product dicts for backward compatibility. Pass via `--input PATH`
or stdin.

Output
------
Markdown (default) or JSON (`--json`) to stdout. Sections are emitted per
period present in the input, each containing up to `--top` previously-unseen
products sorted by `votes_count` descending.

State
-----
Snapshot persistence is auto-managed by `dedup_common` using `dedup.snapshot_dir`
and `dedup.lookback_days` from config.json. Use `--no-save` for dry runs.
"""

import argparse
import json
import sys
from typing import Any

import dedup_common

SOURCE = "producthunt"


def flatten(data: Any) -> list[dict]:
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        items: list[dict] = []
        for v in data.values():
            if isinstance(v, list):
                items.extend(v)
        return items
    return []


def ph_keys(item: dict) -> list[str]:
    return [str(item.get("id", "") or "")]


def is_new(item: dict, fullset: dict[str, str]) -> bool:
    return all(k not in fullset for k in ph_keys(item) if k)


def split_periods(items: list[dict]) -> dict[str, list[dict]]:
    periods: dict[str, list[dict]] = {}
    for it in items:
        periods.setdefault(it.get("period_range") or "daily", []).append(it)
    return periods


def format_md(periods: dict[str, list[dict]], top: int) -> tuple[str, list[dict]]:
    lines = ["# Product Hunt", ""]
    output_items: list[dict] = []
    if not periods:
        return "# Product Hunt\n", output_items

    label_map = {"daily": "今日榜", "weekly": "本周榜"}
    for period, items in periods.items():
        items_sorted = sorted(
            items, key=lambda x: x.get("votes_count", 0) or 0, reverse=True
        )[:top]
        if not items_sorted:
            continue
        output_items.extend(items_sorted)
        lines.append(f"## {label_map.get(period, period)}")
        lines.append("")
        for i, item in enumerate(items_sorted, 1):
            name = item.get("name", "") or ""
            url = item.get("url") or item.get("website") or ""
            votes = item.get("votes_count", 0) or 0
            tagline = (item.get("tagline") or "").strip()
            lines.append(f"{i}. [{name}]({url}) — {votes} votes")
            if tagline:
                lines.append(f"   - {tagline}")
            desc = (item.get("description") or "")[:300].strip()
            if desc:
                lines.append(f"   - {desc}")
        lines.append("")
    return "\n".join(lines), output_items


def format_json(periods: dict[str, list[dict]], top: int) -> tuple[str, list[dict]]:
    out_periods: dict[str, list[dict]] = {}
    output_items: list[dict] = []
    for period, items in periods.items():
        items_sorted = sorted(
            items, key=lambda x: x.get("votes_count", 0) or 0, reverse=True
        )[:top]
        out_periods[period] = items_sorted
        output_items.extend(items_sorted)
    payload = {
        "source": SOURCE,
        "generated_at": dedup_common.today_str(),
        "by_period": out_periods,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2), output_items


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find Top-N new Product Hunt items vs the most recent baseline snapshot."
    )
    parser.add_argument("--input", "-i", default=None,
                        help="Raw JSON path; '-' or omitted reads from stdin.")
    parser.add_argument("--top", type=int, default=10, help="Top N per period (default 10).")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not write today's snapshot (dry run).")
    args = parser.parse_args()

    raw = dedup_common.read_input(args.input)
    items = flatten(raw)
    if not items:
        print("Error: producthunt dedup expects a list or a dict of period-keyed lists.",
              file=sys.stderr)
        sys.exit(1)

    fullset = dedup_common.load_latest_snapshot(SOURCE)
    new_items = [i for i in items if is_new(i, fullset)]
    periods = split_periods(new_items)

    formatter = format_json if args.json else format_md
    text, output_items = formatter(periods, args.top)
    print(text)

    if not args.no_save:
        dedup_common.update_fullset(fullset, output_items, ph_keys)
        path = dedup_common.save_snapshot(SOURCE, fullset)
        print(f"[dedup_common] snapshot saved: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
