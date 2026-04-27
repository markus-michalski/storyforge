"""Configuration loading and validation for StoryForge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path.home() / ".storyforge" / "config.yaml"
CACHE_DIR = Path.home() / ".storyforge" / "cache"
STATE_PATH = CACHE_DIR / "state.json"
AUTHORS_DIR = Path.home() / ".storyforge" / "authors"


def _expand_path(raw: str) -> Path:
    """Expand ~ and environment variables in a path string."""
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def load_config() -> dict[str, Any]:
    """Load and validate configuration from ~/.storyforge/config.yaml."""
    if not CONFIG_PATH.exists():
        return _default_config()

    with open(CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    config = _default_config()
    _deep_merge(config, raw)

    # Expand all path values
    if "paths" in config:
        for key, val in config["paths"].items():
            if isinstance(val, str):
                config["paths"][key] = str(_expand_path(val))

    return config


def _default_config() -> dict[str, Any]:
    """Return default configuration values."""
    return {
        "paths": {
            "content_root": str(Path.home() / "projekte" / "book-projects"),
            "authors_root": str(AUTHORS_DIR),
        },
        "defaults": {
            "language": "en",
            "book_type": "novel",
            "book_category": "fiction",
            "review_handle": "Author",
        },
        "export": {
            "pandoc_path": "pandoc",
            "calibre_path": "ebook-convert",
            "default_format": "epub",
            "pdf_engine": "xelatex",
        },
        "cover": {
            "platform": "midjourney",
            "default_style": "realistic",
        },
        "translation": {
            "preserve_formatting": True,
            "include_glossary": True,
        },
    }


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base dict (mutates base)."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def get_review_handle(config: dict[str, Any]) -> str:
    """Return the configured review comment handle (without colon)."""
    return config.get("defaults", {}).get("review_handle", "Author")


def get_content_root(config: dict[str, Any]) -> Path:
    """Return the content root path from config."""
    return Path(config["paths"]["content_root"])


def get_authors_root(config: dict[str, Any]) -> Path:
    """Return the authors root path from config."""
    return Path(config["paths"]["authors_root"])


def get_plugin_root() -> Path:
    """Return the plugin root directory."""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    # Fallback: relative to this file
    return Path(__file__).resolve().parent.parent.parent


def get_genres_dir() -> Path:
    """Return the genres directory path."""
    return get_plugin_root() / "genres"


def get_book_categories_dir() -> Path:
    """Return the book categories directory path (Path E, Issue #55).

    Houses category-specific knowledge (e.g. memoir craft docs, status models)
    under ``book_categories/{category}/``.
    """
    return get_plugin_root() / "book_categories"


def get_reference_dir() -> Path:
    """Return the reference directory path."""
    return get_plugin_root() / "reference"


def get_templates_dir() -> Path:
    """Return the templates directory path."""
    return get_plugin_root() / "templates"
