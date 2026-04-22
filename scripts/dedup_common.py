"""
Common dedup utilities for news-monitor.

Manages per-source "fullset" snapshots that record which item keys have
already been surfaced in past Top-N reports. Snapshot files are named
`{source}_fullset_YYYY-MM-DD.json` and live in the directory configured at
`dedup.snapshot_dir` in the repo-root config.json.

Loading strategy
----------------
Scan the snapshot directory for the source's snapshot files, take the most
recent one whose date is in the window `[today - lookback_days, today)` —
i.e. excluding today itself, so that re-running on the same day stays stable
even after the script has just written today's snapshot. If no snapshot in the
window is found, return an empty fullset (first-run / cold-start behaviour).

Saving strategy
---------------
At the end of a run, write `{source}_fullset_{today}.json` containing only the
item keys that actually appeared in this run's Top-N output. The value stored
for each key is the run's date (`last_seen_date`); keys whose `last_seen_date`
is older than `dedup.expiry_days` (default 90) are pruned during each
`update_fullset` call, preventing unbounded growth.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from glob import glob
from pathlib import Path
from typing import Any, Callable, Iterable

from _config import get_section

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

_DEFAULT_SNAPSHOT_DIR = "~/.openclaw/workspace/news-monitor/fullset"
_DEFAULT_LOOKBACK_DAYS = 14


_DEFAULT_EXPIRY_DAYS = 90


def _dedup_cfg() -> tuple[str, int, int]:
    """Return (snapshot_dir, lookback_days, expiry_days), with config fallbacks."""
    cfg = get_section("dedup")
    snapshot_dir = cfg.get("snapshot_dir") or _DEFAULT_SNAPSHOT_DIR
    lookback = cfg.get("lookback_days")
    if not isinstance(lookback, int) or lookback <= 0:
        lookback = _DEFAULT_LOOKBACK_DAYS
    expiry = cfg.get("expiry_days")
    if not isinstance(expiry, int) or expiry <= 0:
        expiry = _DEFAULT_EXPIRY_DAYS
    return os.path.expanduser(str(snapshot_dir)), lookback, expiry


def get_snapshot_dir() -> str:
    """Resolved (absolute, ~-expanded) snapshot directory."""
    return _dedup_cfg()[0]


def get_lookback_days() -> int:
    """Configured lookback window in days."""
    return _dedup_cfg()[1]


def get_expiry_days() -> int:
    """Configured expiry threshold in days for fullset pruning."""
    return _dedup_cfg()[2]


def today_str() -> str:
    """ISO date string for 'today'."""
    return datetime.now().strftime("%Y-%m-%d")


def read_input(path: str | None) -> Any:
    """
    Read raw JSON from `path` if given, otherwise from stdin.

    Accepts the path "-" as an explicit alias for stdin.
    """
    if path and path != "-":
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return json.load(sys.stdin)


def _extract_date(fname: str) -> str | None:
    m = _DATE_RE.search(fname)
    return m.group(0) if m else None


def load_latest_snapshot(
    source: str,
    today: str | None = None,
    snapshot_dir: str | None = None,
    lookback_days: int | None = None,
) -> dict[str, str]:
    """
    Find the most recent `{source}_fullset_*.json` snapshot whose date falls in
    `[today - lookback_days, today)` (today excluded) and return its `fullset`
    map. Returns `{}` if no snapshot in the window is found.
    """
    if today is None:
        today = today_str()
    if snapshot_dir is None or lookback_days is None:
        cfg_dir, cfg_lookback, _ = _dedup_cfg()
        if snapshot_dir is None:
            snapshot_dir = cfg_dir
        if lookback_days is None:
            lookback_days = cfg_lookback

    snapshot_dir = os.path.expanduser(snapshot_dir)
    if not os.path.isdir(snapshot_dir):
        return {}

    today_dt = datetime.strptime(today, "%Y-%m-%d")
    earliest_dt = today_dt - timedelta(days=lookback_days)

    candidates: list[tuple[str, str]] = []
    pattern = os.path.join(snapshot_dir, f"{source}_fullset_*.json")
    for path in glob(pattern):
        fdate = _extract_date(os.path.basename(path))
        if not fdate:
            continue
        try:
            fdt = datetime.strptime(fdate, "%Y-%m-%d")
        except ValueError:
            continue
        if fdt >= today_dt:
            continue  # exclude today and any (rare) future-dated snapshot
        if fdt < earliest_dt:
            continue
        candidates.append((fdate, path))

    if not candidates:
        return {}

    candidates.sort(key=lambda t: t[0], reverse=True)
    latest_path = candidates[0][1]
    try:
        with open(latest_path, encoding="utf-8") as f:
            payload = json.load(f)
        fullset = payload.get("fullset", {})
        return fullset if isinstance(fullset, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        print(
            f"[dedup_common] failed to load {latest_path}: {e}",
            file=sys.stderr,
        )
        return {}


def save_snapshot(
    source: str,
    fullset: dict[str, str],
    today: str | None = None,
    snapshot_dir: str | None = None,
) -> str:
    """Persist `fullset` as today's snapshot. Returns the written path."""
    if today is None:
        today = today_str()
    if snapshot_dir is None:
        snapshot_dir = _dedup_cfg()[0]
    snapshot_dir = os.path.expanduser(snapshot_dir)

    Path(snapshot_dir).mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {"source": source, "created_at": today, "version": 1},
        "fullset": fullset,
    }
    path = os.path.join(snapshot_dir, f"{source}_fullset_{today}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def update_fullset(
    fullset: dict[str, str],
    items: Iterable[Any],
    key_funcs: Callable[[Any], Iterable[str]],
    today: str | None = None,
) -> None:
    """Mark each item's keys as seen on `today` (in place), then prune expired keys."""
    if today is None:
        today = today_str()
    for item in items:
        for key in key_funcs(item):
            if key:
                fullset[key] = today

    expiry_days = get_expiry_days()
    cutoff_dt = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=expiry_days)
    expired = [
        k for k, v in fullset.items()
        if _is_expired(v, cutoff_dt)
    ]
    for k in expired:
        del fullset[k]


def _is_expired(date_str: str, cutoff_dt: datetime) -> bool:
    """Return True if date_str parses to a date strictly before cutoff_dt."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d") < cutoff_dt
    except (ValueError, TypeError):
        return False


def bootstrap_from_raw(
    raw_dir: str,
    glob_pattern: str,
    key_funcs: Callable[[Any], Iterable[str]],
    flatten_func: Callable[[Any], list[Any]] | None = None,
) -> dict[str, str]:
    """
    Scan all historical raw files and build a fullset dict mapping
    key -> last_seen_date. Useful for one-shot bootstrapping.
    """
    fullset: dict[str, str] = {}
    for path in glob(os.path.join(os.path.expanduser(raw_dir), glob_pattern)):
        fname = os.path.basename(path)
        fdate = _extract_date(fname)
        if not fdate:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[bootstrap warning] skipping {fname}: {e}", file=sys.stderr)
            continue

        items = flatten_func(data) if flatten_func else data
        if not isinstance(items, list):
            continue

        for item in items:
            for key in key_funcs(item):
                if key:
                    existing = fullset.get(key)
                    if not existing or fdate > existing:
                        fullset[key] = fdate
    return fullset
