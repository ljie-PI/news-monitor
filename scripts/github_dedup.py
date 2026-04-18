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
from _config import get_section

SOURCE = "github"

_FALLBACK_INTERLEAVE_PRIORITY = ["Python", "TypeScript", "Rust", "C++", "C", "Zig"]
_FALLBACK_INTERLEAVE_ROUNDS = 3


def _load_interleave_config() -> tuple[list[str], int]:
    cfg = get_section("github")
    prio = cfg.get("interleave_priority_languages")
    if not isinstance(prio, list) or not prio:
        prio = list(_FALLBACK_INTERLEAVE_PRIORITY)
    else:
        prio = [str(x) for x in prio]
    rounds = cfg.get("interleave_rounds")
    if not isinstance(rounds, int) or rounds <= 0:
        rounds = _FALLBACK_INTERLEAVE_ROUNDS
    return prio, rounds


PRIORITY_LANGUAGES, INTERLEAVE_ROUNDS = _load_interleave_config()


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


def interleave_by_source(
    items: list[dict],
    priority_langs: list[str],
    rounds: int = INTERLEAVE_ROUNDS,
) -> list[dict]:
    """
    Order items by source page:
      1. All items whose source_language == "" (overall page), in input order
      2. Round-robin across priority_langs, up to `rounds` rounds
         (i.e. each priority language contributes at most `rounds` items)
      3. Any remaining items (non-priority languages, or priority-lang items
         beyond the `rounds` cut) appended at the tail in input order
    Backward compat: items without `source_language` field are treated as
    "overall" (so old raw files still work).
    """
    overall: list[dict] = []
    by_lang: dict[str, list[dict]] = {lang: [] for lang in priority_langs}
    other: list[dict] = []

    for it in items:
        src = it.get("source_language")
        if src is None or src == "":
            overall.append(it)
        elif src in by_lang:
            by_lang[src].append(it)
        else:
            other.append(it)

    interleaved: list[dict] = []
    for r in range(rounds):
        for lang in priority_langs:
            bucket = by_lang[lang]
            if r < len(bucket):
                interleaved.append(bucket[r])

    # Remaining priority-lang items (beyond `rounds`) go to tail in lang order.
    priority_tail: list[dict] = []
    for lang in priority_langs:
        priority_tail.extend(by_lang[lang][rounds:])

    return overall + interleaved + priority_tail + other


def format_md(periods: dict[str, list[dict]]) -> tuple[str, list[dict]]:
    title_map = {"today": "Today", "this week": "This Week", "this month": "This Month"}
    order = ["today", "this week", "this month", "other"]

    output_items: list[dict] = []
    blocks: list[str] = []
    for period in order:
        items = periods.get(period) or []
        if not items:
            continue
        output_items.extend(items)

        section_title = title_map.get(period, period.title())
        lines = [f"# {section_title}", ""]
        for it in items:
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


def format_json(periods: dict[str, list[dict]]) -> tuple[str, list[dict]]:
    output_items: list[dict] = []
    for items in periods.values():
        output_items.extend(items)
    payload = {
        "source": SOURCE,
        "generated_at": dedup_common.today_str(),
        "top_by_period": dict(periods),
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

    # Flow (per user spec): split by period → interleave by source_language
    # → filter against fullset → take top N.
    by_period_all = split_periods(items)
    top_by_period: dict[str, list[dict]] = {}
    for period, period_items in by_period_all.items():
        interleaved = interleave_by_source(period_items, PRIORITY_LANGUAGES)
        new_items = [i for i in interleaved if is_new(i, fullset)]
        top_by_period[period] = new_items[: args.top]

    if args.json:
        text, output_items = format_json(top_by_period)
    else:
        text, output_items = format_md(top_by_period)

    print(text)

    if not args.no_save:
        dedup_common.update_fullset(fullset, output_items, repo_keys)
        path = dedup_common.save_snapshot(SOURCE, fullset)
        print(f"[dedup_common] snapshot saved: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
