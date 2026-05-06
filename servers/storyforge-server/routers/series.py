"""Series tools: scaffold a series, get series data, link a book to a series."""

from __future__ import annotations

import json
import warnings

import yaml

from tools.shared.paths import (
    resolve_project_path,
    resolve_series_path,
    slugify,
)
from tools.state.parsers import parse_frontmatter

from . import _app
from ._app import _cache, mcp


@mcp.tool()
def create_series(title: str, genres: str = "", planned_books: int = 3) -> str:
    """Create a new series directory."""
    config = _app.load_config()
    slug = slugify(title)
    series_dir = resolve_series_path(config, slug)

    if series_dir.exists():
        return json.dumps({"error": f"Series '{slug}' already exists"})

    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []

    series_dir.mkdir(parents=True)
    (series_dir / "characters").mkdir()
    (series_dir / "world").mkdir()
    (series_dir / "books").mkdir()

    readme = f"""---
title: "{title}"
slug: "{slug}"
genres: {json.dumps(genre_list)}
planned_books: {planned_books}
status: "Planning"
description: ""
---

# {title} — Series

## Series Arc

*The overarching story across all books.*

## Books

*Use /storyforge:series-planner to develop.*
"""
    (series_dir / "README.md").write_text(readme, encoding="utf-8")
    (series_dir / "series-arc.md").write_text(f"# {title} — Series Arc\n\n*The big picture.*\n", encoding="utf-8")
    (series_dir / "timeline.md").write_text(
        f"# {title} — Timeline\n\n*Chronology across all books.*\n", encoding="utf-8"
    )
    (series_dir / "world" / "canon.md").write_text(
        f"# {title} — Canon\n\n*Established facts that cannot be contradicted.*\n", encoding="utf-8"
    )

    _cache.invalidate()
    return json.dumps({"success": True, "slug": slug, "path": str(series_dir)})


@mcp.tool()
def get_series(slug: str) -> str:
    """Get series data.

    .. deprecated::
        No skill references this tool — series-planner reads series files
        directly. Removal in v2.0.
    """
    warnings.warn(
        "get_series is deprecated — no skill uses it; series-planner reads files directly. Removal in v2.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    _deprecated_msg = "no skill references this tool; series-planner reads files directly"
    state = _cache.get()
    series = state.get("series", {}).get(slug)
    if not series:
        return json.dumps({"error": f"Series '{slug}' not found", "_deprecated": _deprecated_msg})
    return json.dumps({**series, "_deprecated": _deprecated_msg})


@mcp.tool()
def add_book_to_series(series_slug: str, book_slug: str, number: int) -> str:
    """Link a book to a series."""
    config = _app.load_config()
    series_dir = resolve_series_path(config, series_slug)
    book_dir = resolve_project_path(config, book_slug)

    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})
    if not book_dir.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    # Update book's frontmatter
    book_readme = book_dir / "README.md"
    text = book_readme.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta["series"] = series_slug
    meta["series_number"] = number

    new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n" + body
    book_readme.write_text(new_text, encoding="utf-8")

    # Create reference in series/books/
    ref_file = series_dir / "books" / f"{number:02d}-{book_slug}.md"
    ref_file.parent.mkdir(parents=True, exist_ok=True)
    ref_file.write_text(f"# Book {number}: {book_slug}\n\nPath: {book_dir}\n", encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "series": series_slug, "book": book_slug, "number": number})
