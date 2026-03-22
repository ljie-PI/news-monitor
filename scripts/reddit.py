#!/usr/bin/env python3
"""
Reddit Reader (Public RSS/Atom API)
Read-only Reddit client using public .rss endpoints.
No authentication required.
"""

import argparse
import json
import sys
import time
import subprocess
import urllib.parse

import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Fallback: Reddit blocks unauthenticated RSS/JSON in some regions.
# Redlib instances proxy Reddit content without JS challenges.
REDLIB_BASES = [
    "https://redlib.privacyredirect.com",
]

DEFAULT_SUBREDDITS = [
    "LLM",
    "ComputerVision",
    "LanguageTechnology",
    "MachineLearning",
    "ChatGPT",
    "ClaudeAI",
    "openclaw",
    "vibecoding",
    "ClaudeCode",
    "GithubCopilot",
    "opencodeCLI",
    "CLine",
    "java",
    "rust",
    "lua",
    "algotrading",
    "quant",
    "browsers",
    "robloxgamedev",
]


def parse_entries(xml_text: str, subreddit: str) -> list[dict]:
    """Parse Atom XML feed and return list of post dicts."""
    soup = BeautifulSoup(xml_text, "lxml-xml")
    entries = soup.find_all("entry")
    posts = []

    for entry in entries:
        # ID: "t3_1rl9j3s" -> "1rl9j3s"
        raw_id = entry.find("id")
        post_id = ""
        if raw_id and raw_id.string:
            post_id = raw_id.string.strip()
            if post_id.startswith("t3_"):
                post_id = post_id[3:]

        title = ""
        title_elem = entry.find("title")
        if title_elem and title_elem.string:
            title = title_elem.string.strip()

        # Author: "/u/username" -> "username"
        author = ""
        author_elem = entry.find("author")
        if author_elem:
            name_elem = author_elem.find("name")
            if name_elem and name_elem.string:
                author = name_elem.string.strip()
                if author.startswith("/u/"):
                    author = author[3:]

        # Permalink
        permalink = ""
        link_elem = entry.find("link")
        if link_elem and link_elem.get("href"):
            permalink = link_elem["href"]

        # Published time
        published = ""
        pub_elem = entry.find("published")
        if pub_elem and pub_elem.string:
            published = pub_elem.string.strip()

        # Subreddit from category
        sub = subreddit
        cat_elem = entry.find("category")
        if cat_elem and cat_elem.get("term"):
            sub = cat_elem["term"]

        # Parse content HTML to extract url and selftext
        url = ""
        selftext = ""
        content_elem = entry.find("content")
        if content_elem:
            content_html = content_elem.string or content_elem.get_text()
            if content_html:
                content_soup = BeautifulSoup(content_html, "html.parser")

                # Extract external link: the [link] anchor
                # Reddit RSS has two spans at the end: [link] and [comments]
                spans = content_soup.find_all("span")
                for span in spans:
                    a_tag = span.find("a")
                    if a_tag and a_tag.string and a_tag.string.strip() == "[link]":
                        url = a_tag.get("href", "")
                        break

                # If url == permalink, it's a self post (no external link)
                if url and url == permalink:
                    url = ""

                # Extract selftext: get text from the md div, excluding
                # the "submitted by" footer
                md_div = content_soup.find("div", class_="md")
                if md_div:
                    selftext = md_div.get_text(separator=" ").strip()
                    if len(selftext) > 500:
                        selftext = selftext[:500]

        posts.append(
            {
                "id": post_id,
                "subreddit": sub,
                "title": title,
                "author": author,
                "url": url,
                "permalink": permalink,
                "published": published,
                "selftext": selftext,
            }
        )

    return posts


def _curl_get(url: str, params: dict[str, str | int] | None = None, timeout: int = 30) -> str:
    """Fetch URL using curl (workaround for Python TLS issues with some hosts)."""
    q = urllib.parse.urlencode(params or {})
    full_url = url + ("?" + q if q else "")
    try:
        out = subprocess.check_output(
            [
                "curl",
                "-sS",
                "-L",
                "--max-time",
                str(timeout),
                full_url,
            ],
            stderr=subprocess.STDOUT,
        )
        return out.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"curl failed for {full_url}: {e.output.decode('utf-8', errors='replace')[:200]}")


def _fetch_redlib_json(subreddit: str, sort: str, time_filter: str, limit: int) -> list[dict]:
    params: dict[str, str | int] = {"limit": min(limit, 100)}
    if sort == "top":
        params["t"] = time_filter

    last_err: str | None = None
    for base in REDLIB_BASES:
        url = f"{base}/r/{subreddit}/{sort}.json"
        try:
            raw = _curl_get(url, params=params, timeout=30)
            obj = json.loads(raw)
            children = (obj.get("data") or {}).get("children") or []
            posts: list[dict] = []
            for ch in children:
                data = (ch or {}).get("data") or {}
                post_id = str(data.get("id") or "")
                title = str(data.get("title") or "")
                author = str(data.get("author") or "")
                permalink_path = str(data.get("permalink") or "")
                permalink = "https://www.reddit.com" + permalink_path if permalink_path else ""
                external_url = str(data.get("url") or "")
                # if it's a self post, url points to reddit; we keep empty to match original behavior
                if permalink and external_url == permalink:
                    external_url = ""
                selftext = str(data.get("selftext") or "")
                if len(selftext) > 500:
                    selftext = selftext[:500]

                # created_utc -> ISO-ish string
                published = ""
                created_utc = data.get("created_utc")
                if isinstance(created_utc, (int, float)):
                    published = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(created_utc))

                posts.append(
                    {
                        "id": post_id,
                        "subreddit": subreddit,
                        "title": title,
                        "author": author,
                        "url": external_url if not external_url.startswith('https://www.reddit.com') else "",
                        "permalink": permalink,
                        "published": published,
                        "selftext": selftext.replace("\n", " ").strip(),
                    }
                )
            return posts
        except Exception as e:
            last_err = str(e)
            continue

    raise RuntimeError(last_err or "redlib fetch failed")


def fetch_posts(
    subreddits: list[str],
    sort: str = "hot",
    time_filter: str = "day",
    limit: int = 25,
) -> list[dict]:
    """
    Fetch posts from multiple subreddits using .rss endpoints.

    Args:
        subreddits: List of subreddit names
        sort: "hot", "new", "top", "rising"
        time_filter: For top sort - "day", "week", "month", "year", "all"
        limit: Max posts per subreddit

    Returns:
        List of post dictionaries
    """
    all_posts = []
    headers = {"User-Agent": USER_AGENT}

    for subreddit in subreddits:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/{sort}.rss"
            params: dict[str, str | int] = {"limit": min(limit, 100)}
            if sort == "top":
                params["t"] = time_filter

            response = requests.get(
                url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT
            )
            if response.status_code == 200:
                posts = parse_entries(response.text, subreddit)
            else:
                # Fallback via redlib (Reddit may block direct RSS)
                try:
                    posts = _fetch_redlib_json(subreddit, sort, time_filter, limit)
                except Exception:
                    print(
                        f"Error fetching r/{subreddit}: HTTP {response.status_code}",
                        file=sys.stderr,
                    )
                    continue

            all_posts.extend(posts)

            # Be polite to Reddit's servers
            time.sleep(1)

        except Exception as e:
            print(f"Error fetching r/{subreddit}: {e}", file=sys.stderr)

    return all_posts


def search_posts(
    subreddits: list[str],
    query: str,
    sort: str = "relevance",
    time_filter: str = "all",
    limit: int = 25,
) -> list[dict]:
    """
    Search posts using .rss endpoints.

    Args:
        subreddits: List of subreddit names (use ["all"] for site-wide)
        query: Search query
        sort: "relevance", "top", "new", "comments"
        time_filter: "all", "day", "week", "month", "year"
        limit: Max results per subreddit

    Returns:
        List of post dictionaries
    """
    all_posts = []
    seen_ids: set[str] = set()
    headers = {"User-Agent": USER_AGENT}

    for subreddit in subreddits:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/search.rss"
            params: dict[str, str | int] = {
                "q": query,
                "sort": sort,
                "t": time_filter,
                "limit": min(limit, 100),
                "restrict_sr": "on" if subreddit.lower() != "all" else "off",
            }

            response = requests.get(
                url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT
            )
            if response.status_code != 200:
                print(
                    f"Error searching r/{subreddit}: HTTP {response.status_code}",
                    file=sys.stderr,
                )
                continue

            posts = parse_entries(response.text, subreddit)
            for post in posts:
                if post["id"] not in seen_ids:
                    seen_ids.add(post["id"])
                    all_posts.append(post)

            time.sleep(1)

        except Exception as e:
            print(f"Error searching r/{subreddit}: {e}", file=sys.stderr)

    return all_posts


def format_posts(posts: list[dict]) -> str:
    """Format posts as human-readable text."""
    if not posts:
        return "No posts found.\n"

    output = ""
    for i, post in enumerate(posts, 1):
        output += f"{i}. **{post['title']}**\n"
        output += (
            f"   r/{post['subreddit']} | by u/{post['author']} | {post['published']}\n"
        )
        output += f"   {post['permalink']}\n"
        if post.get("url"):
            output += f"   Link: {post['url']}\n"
        if post.get("selftext"):
            text = post["selftext"][:150].replace("\n", " ")
            output += f"   {text}...\n"
        output += "\n"

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Reddit reader - fetch and search posts via public .rss API"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # posts command
    posts_parser = subparsers.add_parser("posts", help="Fetch posts from subreddits")
    posts_parser.add_argument(
        "subreddits",
        type=str,
        nargs="?",
        default=None,
        help="Comma-separated list of subreddits (default: "
        + ",".join(DEFAULT_SUBREDDITS)
        + ")",
    )
    posts_parser.add_argument(
        "--sort", choices=["hot", "new", "top", "rising"], default="hot"
    )
    posts_parser.add_argument(
        "--time", choices=["day", "week", "month", "year", "all"], default="day"
    )
    posts_parser.add_argument("--limit", type=int, default=25)
    posts_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # search command
    search_parser = subparsers.add_parser("search", help="Search posts")
    search_parser.add_argument(
        "subreddits", type=str, help="Comma-separated subreddits (or 'all')"
    )
    search_parser.add_argument("query", type=str, help="Search query")
    search_parser.add_argument(
        "--sort", choices=["relevance", "top", "new", "comments"], default="relevance"
    )
    search_parser.add_argument(
        "--time", choices=["all", "day", "week", "month", "year"], default="all"
    )
    search_parser.add_argument("--limit", type=int, default=25)
    search_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "posts":
        if args.subreddits:
            subreddits = [s.strip() for s in args.subreddits.split(",") if s.strip()]
        else:
            subreddits = list(DEFAULT_SUBREDDITS)
        posts = fetch_posts(subreddits, args.sort, args.time, args.limit)

        if args.json:
            print(json.dumps(posts, ensure_ascii=False, indent=2))
        else:
            print(format_posts(posts))

    elif args.command == "search":
        subreddits = [s.strip() for s in args.subreddits.split(",") if s.strip()]
        posts = search_posts(subreddits, args.query, args.sort, args.time, args.limit)

        if args.json:
            print(json.dumps(posts, ensure_ascii=False, indent=2))
        else:
            print(format_posts(posts))


if __name__ == "__main__":
    main()
