#!/usr/bin/env python3
"""
Hacker News Fetcher — HTML scraping with pagination.

Fetches stories from three HN pages:
  - news  (top stories)    https://news.ycombinator.com/news?p=N
  - front (front page)     https://news.ycombinator.com/front?p=N
  - show  (Show HN)        https://news.ycombinator.com/show?p=N

Supports filtering by min-points, start time, keyword, and deduplication by title.
Results are sorted by points descending.
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://news.ycombinator.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

PAGE_PATHS = {
    "news": "/news",
    "front": "/front",
    "show": "/show",
}

DEFAULT_PAGES = ["news", "front", "show"]
DEFAULT_LIMIT = 100
DEFAULT_MIN_POINTS = 50
MAX_WORKERS = 10
REQUEST_DELAY = 0.5  # seconds between sequential requests per page type


def parse_score(text: str) -> int:
    """Extract integer score from text like '344 points'."""
    m = re.search(r"(\d+)\s+points?", text)
    return int(m.group(1)) if m else 0


def parse_comments(text: str) -> int:
    """Extract comment count from text like '201\xa0comments'."""
    m = re.search(r"(\d+)\s*comment", text.replace("\xa0", " "))
    return int(m.group(1)) if m else 0


def parse_created(age_title: str) -> str:
    """
    Parse the age element's title attribute.
    Format: '2026-03-04T11:43:32 1772535412'
    Returns ISO 8601 string.
    """
    if not age_title:
        return ""
    parts = age_title.strip().split()
    return parts[0] if parts else ""


def parse_page(html: str, source_page: str) -> list[dict]:
    """Parse one page of HN HTML and return a list of story dicts."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.athing")
    items = []

    for row in rows:
        try:
            story_id = row.get("id", "")

            title_a = row.select_one(".titleline a")
            if not title_a:
                continue
            title = title_a.get_text(strip=True)
            url = str(title_a.get("href", ""))
            if url.startswith("item?id="):
                url = f"{BASE_URL}/{url}"

            # The subtext row is the next sibling <tr>
            subtext_tr = row.find_next_sibling("tr")
            if not subtext_tr:
                continue

            # Score
            score_span = subtext_tr.select_one(".score")
            score = parse_score(score_span.get_text()) if score_span else 0

            # Author
            author_elem = subtext_tr.select_one(".hnuser")
            author = author_elem.get_text(strip=True) if author_elem else ""

            # Created time
            age_span = subtext_tr.select_one(".age")
            created = ""
            if age_span:
                created = parse_created(str(age_span.get("title", "")))

            # Comments
            comments = 0
            for a_tag in subtext_tr.select("a"):
                txt = a_tag.get_text()
                if "comment" in txt:
                    comments = parse_comments(txt)
                    break

            items.append(
                {
                    "id": story_id,
                    "title": title,
                    "url": url,
                    "score": score,
                    "comments": comments,
                    "author": author,
                    "created": created,
                    "hn_url": f"{BASE_URL}/item?id={story_id}",
                    "source_page": source_page,
                }
            )
        except Exception:
            continue

    return items


def fetch_page(page_type: str, page_num: int) -> tuple[str, int, list[dict]]:
    """
    Fetch and parse a single paginated HN page.

    Returns:
        (page_type, page_num, list of items)
    """
    path = PAGE_PATHS[page_type]
    url = f"{BASE_URL}{path}?p={page_num}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return page_type, page_num, []
        items = parse_page(resp.text, page_type)
        return page_type, page_num, items
    except Exception as e:
        print(f"Error fetching {page_type} p={page_num}: {e}", file=sys.stderr)
        return page_type, page_num, []


def fetch_one_page_type(
    page_type: str,
    min_points: int,
    start_dt: datetime | None,
) -> list[dict]:
    """
    Sequentially fetch all paginated pages for a single page type.
    Stops when a page returns 0 rows.
    """
    items: list[dict] = []
    page_num = 1

    while True:
        _, _, page_items = fetch_page(page_type, page_num)
        if not page_items:
            break

        for item in page_items:
            # Min points filter
            if item["score"] < min_points:
                continue
            # Start time filter
            if start_dt and item["created"]:
                try:
                    item_dt = datetime.fromisoformat(item["created"])
                    if item_dt.tzinfo is None:
                        item_dt = item_dt.replace(tzinfo=timezone.utc)
                    if item_dt < start_dt:
                        continue
                except ValueError:
                    pass
            items.append(item)

        page_num += 1
        time.sleep(REQUEST_DELAY)

    return items


def fetch_all_pages(
    page_types: list[str],
    min_points: int,
    start_dt: datetime | None,
) -> list[dict]:
    """
    Fetch all pages for each page type.
    Each page type is fetched concurrently (up to MAX_WORKERS page types in parallel).
    Within each page type, pages are fetched sequentially.
    """
    all_items: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(page_types))) as executor:
        futures = {
            executor.submit(fetch_one_page_type, pt, min_points, start_dt): pt
            for pt in page_types
        }
        for future in as_completed(futures):
            pt = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
            except Exception as e:
                print(f"Error fetching {pt}: {e}", file=sys.stderr)

    return all_items


def deduplicate_by_title(items: list[dict]) -> list[dict]:
    """Deduplicate items by title, keeping the one with the highest score."""
    seen: dict[str, dict] = {}
    for item in items:
        key = item["title"]
        if key not in seen or item["score"] > seen[key]["score"]:
            seen[key] = item
    return list(seen.values())


def filter_by_keyword(items: list[dict], keyword: str) -> list[dict]:
    """Filter items by comma-separated keywords (case-insensitive, in title)."""
    if not keyword:
        return items
    keywords = [k.strip() for k in keyword.split(",") if k.strip()]
    if not keywords:
        return items
    pattern = "|".join(re.escape(k) for k in keywords)
    regex = re.compile(pattern, re.IGNORECASE)
    return [item for item in items if regex.search(item.get("title", ""))]


def parse_start_time(s: str) -> datetime:
    """
    Parse --start value into a timezone-aware datetime (UTC).
    Supports: YYYY-MM-DD, YYYY-MM-DDTHH:MM, YYYY-MM-DDTHH:MM:SS
    """
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(
        f"Invalid --start format: {s!r}. "
        "Expected YYYY-MM-DD or YYYY-MM-DDTHH:MM or YYYY-MM-DDTHH:MM:SS"
    )


def format_output(items: list[dict]) -> str:
    """Format items as human-readable text."""
    if not items:
        return "No stories found.\n"

    output = ""
    for i, item in enumerate(items, 1):
        output += f"{i}. **{item['title']}**\n"
        output += (
            f"   {item['score']} points | "
            f"{item['comments']} comments | "
            f"by {item['author']} | "
            f"{item['created']} | "
            f"[{item['source_page']}]\n"
        )
        if item["url"] and item["url"] != item["hn_url"]:
            output += f"   {item['url']}\n"
        output += f"   {item['hn_url']}\n\n"

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Hacker News stories from news/front/show pages"
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=",".join(DEFAULT_PAGES),
        help="Comma-separated page types: news,front,show (default: news,front,show)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Max stories to return, 0 for all (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Filter out stories earlier than this time "
        "(YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    parser.add_argument(
        "--min-points",
        type=int,
        default=DEFAULT_MIN_POINTS,
        help=f"Minimum points threshold (default: {DEFAULT_MIN_POINTS})",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        help="Comma-separated keyword filter (matches title)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    # Parse page types
    page_types = [p.strip() for p in args.pages.split(",") if p.strip()]
    for pt in page_types:
        if pt not in PAGE_PATHS:
            print(
                f"Invalid page type: {pt!r}. Must be one of: {', '.join(PAGE_PATHS)}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Parse start time
    start_dt = None
    if args.start:
        try:
            start_dt = parse_start_time(args.start)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    # Fetch
    print(
        f"Fetching pages: {', '.join(page_types)} "
        f"(min-points={args.min_points}"
        f"{f', start={args.start}' if args.start else ''})"
        f" ...",
        file=sys.stderr,
    )
    items = fetch_all_pages(page_types, args.min_points, start_dt)
    print(f"Fetched {len(items)} items before dedup/filter.", file=sys.stderr)

    # Keyword filter
    items = filter_by_keyword(items, args.keyword)

    # Deduplicate by title
    items = deduplicate_by_title(items)

    # Sort by score descending
    items.sort(key=lambda x: x["score"], reverse=True)

    # Apply limit
    if args.limit > 0:
        items = items[: args.limit]

    print(f"Returning {len(items)} items.", file=sys.stderr)

    # Output
    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
    else:
        print(format_output(items))


if __name__ == "__main__":
    main()
