#!/usr/bin/env python3
"""
GitHub Trending dedup — emit Top-N new repositories not seen in a recent baseline snapshot.

Input
-----
Raw JSON produced by `scripts/github_trending.py --json` (a dict whose values
are lists of repo dicts, keyed by period — typically `daily`/`weekly`/`monthly`),
or a flat list of repo dicts. Pass via `--input PATH` or stdin.

Output
------
Markdown (default) or JSON (`--json`) to stdout. Sections are emitted per
period present in the input, each containing up to `--top` previously-unseen
repos in the input's original order.

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

SOURCE = "github"


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


def repo_keys(item: dict) -> list[str]:
    return [item.get("full_name", ""), item.get("html_url", "")]


def is_new(item: dict, fullset: dict[str, str]) -> bool:
    return all(k not in fullset for k in repo_keys(item) if k)


def split_periods(items: list[dict]) -> dict[str, list[dict]]:
    periods: dict[str, list[dict]] = {}
    for it in items:
        periods.setdefault(it.get("period_range") or "other", []).append(it)
    return periods


def format_md(periods: dict[str, list[dict]], top: int) -> tuple[str, list[dict]]:
    title_map = {"today": "Today", "this week": "This Week", "this month": "This Month"}
    order = ["today", "this week", "this month", "other"]

    output_items: list[dict] = []
    blocks: list[str] = []
    for period in order:
        items = periods.get(period) or []
        if not items:
            continue
        chosen = items[:top]
        output_items.extend(chosen)

        section_title = title_map.get(period, period.title())
        lines = [f"# {section_title}", ""]
        for it in chosen:
            name = it.get("full_name") or ""
            url = it.get("html_url") or ""
            stars = it.get("period_stars") or 0
            lines.append(f"- [{name}]({url}) — +{stars} stars")
            desc = (it.get("description") or "").strip()
            if desc:
                lines.append(f"  - {desc}")
        lines.append("")
        blocks.append("\n".join(lines))

    return "\n".join(blocks).strip(), output_items


def format_json(periods: dict[str, list[dict]], top: int) -> tuple[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    output_items: list[dict] = []
    for period, items in periods.items():
        chosen = items[:top]
        out[period] = chosen
        output_items.extend(chosen)
    payload = {
        "source": SOURCE,
        "generated_at": dedup_common.today_str(),
        "top_by_period": out,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2), output_items


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find Top-N new GitHub trending repos vs the most recent baseline snapshot."
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

    fullset = dedup_common.load_latest_snapshot(SOURCE)
    new_items = [i for i in items if is_new(i, fullset)]
    periods = split_periods(new_items)

    if args.json:
        text, output_items = format_json(periods, args.top)
    else:
        text, output_items = format_md(periods, args.top)

    print(text)

    if not args.no_save:
        dedup_common.update_fullset(fullset, output_items, repo_keys)
        path = dedup_common.save_snapshot(SOURCE, fullset)
        print(f"[dedup_common] snapshot saved: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
