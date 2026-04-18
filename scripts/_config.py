"""
Config loader for news-monitor scripts.

Reads the repo-root config.json (sibling of SKILL.md). Every script keeps its
in-code fallback constants, so a missing config.json — or a missing section /
key — is fully tolerated and behaviour stays identical to the pre-config era.
"""

import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

_cache: dict[str, Any] | None = None


def load_config() -> dict[str, Any]:
    """Load and cache the repo-root config.json. Missing file → empty dict."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
    except FileNotFoundError:
        _cache = {}
    except (json.JSONDecodeError, OSError):
        _cache = {}
    return _cache


def get_section(name: str) -> dict[str, Any]:
    """Return config[name] (or empty dict if missing)."""
    cfg = load_config()
    section = cfg.get(name)
    return section if isinstance(section, dict) else {}


def get_value(section: str, key: str, default: Any) -> Any:
    """Return config[section][key] (or default if missing)."""
    sec = get_section(section)
    if key not in sec or sec[key] is None:
        return default
    return sec[key]
