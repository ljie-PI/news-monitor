#!/usr/bin/env python3
"""
Product Hunt Fetcher — RSS feed.

Fetches products from Product Hunt's Atom feed:
  https://www.producthunt.com/feed

Supports filtering by start time and keyword.
Results are sorted by published time descending.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

FEED_URL = "https://www.producthunt.com/feed"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def parse_datetime(s: str) -> datetime | None:
    """Parse an ISO 8601 / RFC datetime string into a timezone-aware datetime."""
    if not s:
        return None
    s = s.strip()
    # Try common formats
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%a, %d %b %Y %H:%M:%S %z",  # RSS pubDate format
        "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def fetch_feed() -> list[dict]:
    """Fetch and parse the Product Hunt Atom/RSS feed."""
    resp = requests.get(FEED_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "xml")
    # Fallback if xml parser doesn't find entries
    if not soup.find("entry") and not soup.find("item"):
        soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    for entry in soup.find_all(["entry", "item"]):
        title_elem = entry.find("title")
        title = title_elem.get_text(strip=True) if title_elem else ""

        # Link: Atom uses <link href="...">, RSS uses <link>text</link>
        link_tag = entry.find("link")
        url = ""
        if link_tag:
            url = link_tag.get("href") or link_tag.get_text(strip=True)

        # Author
        author_elem = entry.find("author")
        author = ""
        if author_elem:
            name_elem = author_elem.find("name")
            author = (
                name_elem.get_text(strip=True)
                if name_elem
                else author_elem.get_text(strip=True)
            )

        # Published time
        pub_elem = entry.find("published") or entry.find("pubDate")
        published = pub_elem.get_text(strip=True) if pub_elem else ""

        # Updated time
        upd_elem = entry.find("updated")
        updated = upd_elem.get_text(strip=True) if upd_elem else ""

        # Description / content
        content_elem = entry.find("content") or entry.find("description")
        description = ""
        if content_elem:
            # In Atom XML, content.string holds the raw HTML as a text node
            raw_html = content_elem.string or content_elem.get_text()
            desc_soup = BeautifulSoup(raw_html, "html.parser")
            # Extract only the first <p> text (the tagline), skip navigation links
            first_p = desc_soup.find("p")
            if first_p:
                description = first_p.get_text(strip=True)
            else:
                description = desc_soup.get_text(strip=True)
            description = re.sub(r"\s+", " ", description).strip()

        items.append(
            {
                "title": title,
                "url": url,
                "author": author,
                "published": published,
                "updated": updated,
                "description": description,
            }
        )

    return items


def filter_by_start(items: list[dict], start_dt: datetime) -> list[dict]:
    """Filter out items published before start_dt."""
    result = []
    for item in items:
        pub_str = item.get("published") or item.get("updated", "")
        pub_dt = parse_datetime(pub_str)
        if pub_dt and pub_dt < start_dt:
            continue
        # If we can't parse the time, keep the item
        result.append(item)
    return result


def filter_by_keyword(items: list[dict], keyword: str) -> list[dict]:
    """Filter items by comma-separated keywords (case-insensitive, matches title + description)."""
    if not keyword:
        return items
    keywords = [k.strip() for k in keyword.split(",") if k.strip()]
    if not keywords:
        return items
    pattern = "|".join(re.escape(k) for k in keywords)
    regex = re.compile(pattern, re.IGNORECASE)
    return [
        item
        for item in items
        if regex.search(item.get("title", ""))
        or regex.search(item.get("description", ""))
    ]


def sort_by_published(items: list[dict]) -> list[dict]:
    """Sort items by published time descending (newest first)."""

    def sort_key(item: dict) -> float:
        pub_str = item.get("published") or item.get("updated", "")
        dt = parse_datetime(pub_str)
        return dt.timestamp() if dt else 0

    return sorted(items, key=sort_key, reverse=True)


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
        return "No products found.\n"

    output = ""
    for i, item in enumerate(items, 1):
        output += f"{i}. **{item['title']}**\n"
        output += f"   by {item['author']} | {item['published']}\n"
        if item["description"]:
            desc = item["description"][:200]
            output += f"   {desc}\n"
        output += f"   {item['url']}\n\n"

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Fetch products from Product Hunt RSS feed"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max products to return, 0 for all (default: 0)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Filter out products published before this time "
        "(YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        help="Comma-separated keyword filter (matches title and description)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    # Parse start time
    start_dt = None
    if args.start:
        try:
            start_dt = parse_start_time(args.start)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    # Fetch
    print("Fetching Product Hunt feed...", file=sys.stderr)
    items = fetch_feed()
    print(f"Fetched {len(items)} items.", file=sys.stderr)

    # Filter by start time
    if start_dt:
        items = filter_by_start(items, start_dt)

    # Filter by keyword
    items = filter_by_keyword(items, args.keyword)

    # Sort by published time descending
    items = sort_by_published(items)

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
