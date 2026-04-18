#!/usr/bin/env python3
"""
GitHub Trending Fetcher
Fetches trending repositories from GitHub with support for multiple languages and time periods.
Converted from github_trending_extension Chrome extension.
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from _config import get_section

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_TIMEOUT = 10

_GH_CFG = get_section("github")

# Language colors (subset). Override via config.json: github.language_colors.
LANGUAGE_COLORS = _GH_CFG.get("language_colors") or {
    "Python": "#3572A5",
    "TypeScript": "#2b7489",
    "JavaScript": "#f1e05a",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Java": "#b07219",
    "C++": "#f34b7d",
    "C": "#555555",
    "Ruby": "#701516",
    "Swift": "#fa7343",
    "Kotlin": "#A97BFF",
    "Lua": "#000080",
    "Zig": "#ec915c",
}

# Default languages to fetch (overall is always included automatically).
# Override via config.json: github.default_languages.
DEFAULT_LANGUAGES = _GH_CFG.get("default_languages") or [
    "Python", "TypeScript", "Rust", "C++", "C", "Java", "Go", "Lua", "Zig",
]


def parse_trending_html(html: str) -> list[dict]:
    """Parse GitHub trending HTML and extract repository data."""
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("article.Box-row")
    repos = []

    for article in articles:
        try:
            # Title and link
            title_elem = article.select_one("h2.h3 a")
            if not title_elem:
                continue

            full_name = (
                title_elem.get_text(strip=True).replace("\n", "").replace(" ", "")
            )
            parts = full_name.split("/")
            if len(parts) != 2:
                continue
            owner, repo = parts[0].strip(), parts[1].strip()

            href = title_elem.get("href", "")
            html_url = f"https://github.com{href}" if href else ""

            # Description
            desc_elem = article.select_one("p.col-9")
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Stars
            stars_elem = article.select_one('a[href$="/stargazers"]')
            stars_text = stars_elem.get_text(strip=True) if stars_elem else "0"
            stargazers_count = int(stars_text.replace(",", "")) if stars_text else 0

            # Language
            lang_elem = article.select_one('span[itemprop="programmingLanguage"]')
            language = lang_elem.get_text(strip=True) if lang_elem else ""

            # Forks
            forks_elem = article.select_one('a[href$="/forks"]')
            forks_text = forks_elem.get_text(strip=True) if forks_elem else "0"
            forks_count = int(forks_text.replace(",", "")) if forks_text else 0

            # Period stars (e.g., "123 stars today")
            period_stars = 0
            period_range = ""
            for span in article.select("span"):
                text = span.get_text(strip=True).lower()
                if (
                    "stars today" in text
                    or "stars this week" in text
                    or "stars this month" in text
                ):
                    match = re.search(
                        r"(\d+(?:,\d+)*)\s+stars?\s+(today|this week|this month)",
                        text,
                        re.I,
                    )
                    if match:
                        period_stars = int(match.group(1).replace(",", ""))
                        period_range = match.group(2)
                    break

            # Avatar
            avatar_elem = article.select_one('img[src*="avatars"]')
            avatar_url = (
                avatar_elem["src"]
                if avatar_elem
                else f"https://github.com/{owner}.png?size=40"
            )

            repos.append(
                {
                    "full_name": f"{owner}/{repo}",
                    "description": description,
                    "stargazers_count": stargazers_count,
                    "html_url": html_url,
                    "language": language,
                    "forks_count": forks_count,
                    "period_stars": period_stars,
                    "period_range": period_range,
                    "avatar_url": avatar_url,
                    "owner": owner,
                }
            )
        except Exception:
            continue

    return repos


def fetch_trending(
    language: str = "", since: str = "daily", limit: int = 0
) -> list[dict]:
    """
    Fetch trending repositories for a language/time period.

    Args:
        language: Programming language (empty string for overall)
        since: Time period - "daily", "weekly", or "monthly"
        limit: Maximum number of repos to return

    Returns:
        List of repository dictionaries
    """
    if language:
        url = f"https://github.com/trending/{quote(language)}?since={since}"
    else:
        url = f"https://github.com/trending?since={since}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        repos = parse_trending_html(response.text)
        return repos[:limit] if limit > 0 else repos
    except Exception as e:
        print(f"Error fetching {language or 'overall'} trending: {e}", file=sys.stderr)
        return []


def fetch_multiple_languages(
    languages: list[str], since: str = "daily", limit: int = 0
) -> list[dict]:
    """
    Fetch trending repos for multiple languages concurrently.
    Always includes overall (empty string) in addition to specified languages.

    Args:
        languages: List of languages (empty list for default languages)
        since: Time period
        limit: Max repos per language

    Returns:
        Combined list of repos with duplicates removed
    """
    if not languages:
        languages = list(DEFAULT_LANGUAGES)

    # Always include overall (empty string) for language-agnostic trending
    if "" not in languages:
        languages = [""] + languages

    all_repos = []
    seen_names = set()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_trending, lang, since, limit): lang
            for lang in languages
        }

        # Wait for all results, keyed by language (so we can merge deterministically).
        results_by_lang: dict[str, list[dict]] = {}
        for future in as_completed(futures):
            lang = futures[future]
            try:
                results_by_lang[lang] = future.result()
            except Exception:
                results_by_lang[lang] = []

    # Merge in the input `languages` order (overall first), tagging each repo with
    # its source page. Repos surfacing on multiple pages keep the first occurrence
    # (so overall > specific-language order).
    for lang in languages:
        for repo in results_by_lang.get(lang, []):
            if repo["full_name"] in seen_names:
                continue
            seen_names.add(repo["full_name"])
            repo["source_language"] = lang
            all_repos.append(repo)

    return all_repos


def format_output(repos: list[dict], since: str) -> str:
    """Format repos as human-readable text."""
    period_map = {"daily": "今日", "weekly": "本周", "monthly": "本月"}
    period_label = period_map.get(since, since)

    output = f"📈 GitHub {period_label}热门\n\n"

    for i, repo in enumerate(repos, 1):
        stars_k = (
            f"{repo['stargazers_count'] / 1000:.1f}k"
            if repo["stargazers_count"] >= 1000
            else str(repo["stargazers_count"])
        )
        period_info = f"+{repo['period_stars']}" if repo["period_stars"] else ""
        lang_info = f" - {repo['language']}" if repo["language"] else ""

        output += f"{i}. **{repo['full_name']}** ⭐ {stars_k}"
        if period_info:
            output += f" ({period_info})"
        output += f"{lang_info}\n"
        if repo["description"]:
            output += f"   {repo['description'][:100]}\n"
        output += f"   🔗 {repo['html_url']}\n\n"

    return output


def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub trending repositories")
    parser.add_argument(
        "--languages",
        type=str,
        default="",
        help="Comma-separated list of languages (default: "
        + ",".join(DEFAULT_LANGUAGES)
        + "). Overall is always included automatically.",
    )
    parser.add_argument(
        "--since",
        type=str,
        default="daily,weekly",
        help="Comma-separated time periods: daily,weekly,monthly (default: daily,weekly)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max repos per language (default: 0, meaning all)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    languages = (
        [l.strip() for l in args.languages.split(",") if l.strip()]
        if args.languages
        else []
    )

    since_periods = [s.strip() for s in args.since.split(",") if s.strip()]
    valid_periods = {"daily", "weekly", "monthly"}
    for p in since_periods:
        if p not in valid_periods:
            print(
                f"Invalid period: {p}. Must be daily, weekly, or monthly.",
                file=sys.stderr,
            )
            sys.exit(1)

    all_results = {}
    for period in since_periods:
        repos = fetch_multiple_languages(languages, period, args.limit)
        all_results[period] = repos

    if args.json:
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
    else:
        for period in since_periods:
            print(format_output(all_results[period], period))


if __name__ == "__main__":
    main()
