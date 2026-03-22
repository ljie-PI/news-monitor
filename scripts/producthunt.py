#!/usr/bin/env python3
"""
Product Hunt Fetcher — GraphQL API.

Fetches daily top products from Product Hunt's GraphQL API:
  https://api.producthunt.com/v2/api/graphql

Requires environment variables:
  PRODUCTHUNT_API_TOKEN - Your Product Hunt API access token
"""

import argparse
import json
import os
import re
import sys

import requests

API_URL = "https://api.producthunt.com/v2/api/graphql"

DEFAULT_LIMIT = 30
DEFAULT_TOPIC = None


def get_api_token() -> str:
    api_token = os.environ.get("PRODUCTHUNT_API_TOKEN")
    if not api_token:
        print(
            "Error: PRODUCTHUNT_API_TOKEN environment variable is required.\n"
            "Get your token at https://api.producthunt.com/v2/oauth/applications",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_token


def build_query(
    topic: str | None,
    first: int,
    after: str | None = None,
) -> str:
    topic_filter = f', topic: "{topic}"' if topic else ""
    after_filter = f', after: "{after}"' if after else ""

    query = f"""{{
    posts(order: RANKING{topic_filter}{after_filter}, first: {first}) {{
        edges {{
            node {{
                id
                name
                tagline
                description
                url
                website
                votesCount
                commentsCount
                reviewsCount
                reviewsRating
                createdAt
                featuredAt
                dailyRank
                topics(first: 5) {{
                    edges {{
                        node {{
                            name
                            slug
                        }}
                    }}
                }}
                thumbnail {{
                    url
                }}
            }}
        }}
        pageInfo {{
            hasNextPage
            endCursor
        }}
        totalCount
    }}
}}"""
    return query


def fetch_posts(
    topic: str | None,
    limit: int,
) -> list[dict]:
    api_token = get_api_token()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}",
        "Host": "api.producthunt.com",
    }

    all_posts = []
    cursor = None
    page_size = min(limit, 20)

    while len(all_posts) < limit:
        query = build_query(topic, page_size, cursor)

        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json={"query": query},
                timeout=30,
            )

            if response.status_code == 401:
                print(
                    "Error: Invalid or expired API token. "
                    "Check your PRODUCTHUNT_API_TOKEN environment variable.",
                    file=sys.stderr,
                )
                sys.exit(1)
            elif response.status_code == 429:
                print(
                    "Rate limit exceeded. Waiting 60 seconds...",
                    file=sys.stderr,
                )
                import time

                time.sleep(60)
                response = requests.post(
                    API_URL,
                    headers=headers,
                    json={"query": query},
                    timeout=30,
                )

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                print(f"GraphQL Error: {error_msg}", file=sys.stderr)
                sys.exit(1)

            posts_data = data.get("data", {}).get("posts", {})
            edges = posts_data.get("edges", [])
            page_info = posts_data.get("pageInfo", {})

            for edge in edges:
                node = edge.get("node", {})
                topics = [
                    t["node"]["name"] for t in node.get("topics", {}).get("edges", [])
                ]

                all_posts.append(
                    {
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "tagline": node.get("tagline"),
                        "description": node.get("description"),
                        "url": node.get("url"),
                        "website": node.get("website"),
                        "votes_count": node.get("votesCount", 0),
                        "comments_count": node.get("commentsCount", 0),
                        "reviews_count": node.get("reviewsCount", 0),
                        "reviews_rating": node.get("reviewsRating"),
                        "created_at": node.get("createdAt"),
                        "featured_at": node.get("featuredAt"),
                        "daily_rank": node.get("dailyRank"),
                        "topics": topics,
                        "thumbnail": (
                            node.get("thumbnail", {}).get("url")
                            if node.get("thumbnail")
                            else None
                        ),
                    }
                )

            if not page_info.get("hasNextPage") or not page_info.get("endCursor"):
                break

            cursor = page_info["endCursor"]

        except requests.exceptions.RequestException as e:
            print(f"Error fetching posts: {e}", file=sys.stderr)
            return []

    all_posts.sort(key=lambda x: x.get("daily_rank", 9999))
    return all_posts[:limit]


def filter_by_keyword(items: list[dict], keyword: str) -> list[dict]:
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
        if regex.search(item.get("name", ""))
        or regex.search(item.get("tagline", ""))
        or regex.search(item.get("description", "") or "")
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch products from Product Hunt GraphQL API"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=DEFAULT_TOPIC,
        help="Filter by topic slug (e.g., 'tech', 'ai')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Max products to return (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        help="Comma-separated keyword filter (matches name, tagline, description)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    items = fetch_posts(
        topic=args.topic,
        limit=args.limit,
    )

    items = filter_by_keyword(items, args.keyword)

    print(json.dumps(items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
