"""Idea-registry tools: lightweight markdown files at content_root/ideas/.

Ideas hold pre-book brainstorm output (logline, concept, status). The
``promote_idea`` tool links an idea to a real book project once it's been
turned into a scaffolded project.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from tools.state.parsers import parse_frontmatter

from . import _app
from ._app import _cache, mcp


def _get_ideas_dir(config: dict) -> Path:
    """Return the ideas directory path for the current content root."""
    return _app.get_content_root(config) / "ideas"


def _idea_path(ideas_dir: Path, slug: str) -> Path:
    """Return the file path for a given idea slug."""
    return ideas_dir / f"{slug}.md"


def _read_idea(ideas_dir: Path, slug: str) -> tuple[dict, str] | None:
    """Read and parse an idea file. Returns (meta, body) or None if not found."""
    path = _idea_path(ideas_dir, slug)
    if not path.exists():
        return None
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def _write_idea(path: Path, meta: dict, body: str) -> None:
    """Write frontmatter + body back to an idea file."""
    frontmatter = yaml.dump(meta, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")


def _slugify(text: str) -> str:
    """Local slugify wrapper — kept module-private to match historical behavior."""
    from tools.shared.paths import slugify

    return slugify(text)


@mcp.tool()
def create_idea(title: str, genres: str = "", logline: str = "", concept: str = "") -> str:
    """Create a new idea file in ideas/{slug}.md with YAML frontmatter.

    Args:
        title:   Human-readable title of the idea.
        genres:  Comma-separated genre names (e.g. "fantasy,mystery").
        logline: One-sentence pitch.
        concept: Free-text body content describing the idea.
    """
    config = _app.load_config()
    ideas_dir = _get_ideas_dir(config)
    ideas_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(title)
    genres_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    today = date.today().isoformat()

    meta: dict[str, Any] = {
        "title": title,
        "slug": slug,
        "status": "raw",
        "genres": genres_list,
        "logline": logline,
        "created": today,
        "last_touched": today,
        "promoted_to": None,
    }

    path = _idea_path(ideas_dir, slug)
    _write_idea(path, meta, concept)

    _cache.invalidate()
    return json.dumps({"slug": slug, "title": title, "file_path": str(path)})


@mcp.tool()
def list_ideas(status: str = "", genre: str = "") -> str:
    """List all ideas from the ideas/ directory, with optional filters.

    Args:
        status: Filter by exact status value (e.g. "raw", "explored").
        genre:  Filter by genre (partial match against each idea's genres list).
    """
    config = _app.load_config()
    ideas_dir = _get_ideas_dir(config)

    if not ideas_dir.exists():
        return json.dumps({"ideas": [], "count": 0})

    ideas = []
    for md_file in sorted(ideas_dir.glob("*.md")):
        if not md_file.is_file():
            continue
        try:
            meta, _ = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not meta:
            continue

        idea_status = meta.get("status", "raw")
        idea_genres = meta.get("genres", [])

        if status and idea_status != status:
            continue
        if genre and genre not in idea_genres:
            continue

        ideas.append(
            {
                "slug": meta.get("slug", md_file.stem),
                "title": meta.get("title", md_file.stem),
                "status": idea_status,
                "genres": idea_genres,
                "logline": meta.get("logline", ""),
                "created": str(meta.get("created", "")),
                "last_touched": str(meta.get("last_touched", "")),
                "promoted_to": meta.get("promoted_to"),
            }
        )

    return json.dumps({"ideas": ideas, "count": len(ideas)})


@mcp.tool()
def get_idea(slug: str) -> str:
    """Return the full content of a single idea file.

    Args:
        slug: The idea's slug (filename without .md extension).
    """
    config = _app.load_config()
    ideas_dir = _get_ideas_dir(config)
    result = _read_idea(ideas_dir, slug)

    if result is None:
        return json.dumps({"error": f"Idea '{slug}' not found"})

    meta, body = result
    return json.dumps(
        {
            "slug": meta.get("slug", slug),
            "title": meta.get("title", slug),
            "status": meta.get("status", "raw"),
            "genres": meta.get("genres", []),
            "logline": meta.get("logline", ""),
            "created": str(meta.get("created", "")),
            "last_touched": str(meta.get("last_touched", "")),
            "promoted_to": meta.get("promoted_to"),
            "body": body.strip(),
        }
    )


@mcp.tool()
def update_idea(slug: str, field: str, value: str) -> str:
    """Update a single frontmatter field of an existing idea.

    Args:
        slug:  The idea's slug.
        field: The frontmatter key to update (e.g. "status", "logline").
        value: The new value as a string.
    """
    config = _app.load_config()
    ideas_dir = _get_ideas_dir(config)
    result = _read_idea(ideas_dir, slug)

    if result is None:
        return json.dumps({"error": f"Idea '{slug}' not found"})

    meta, body = result
    meta[field] = value
    meta["last_touched"] = date.today().isoformat()

    _write_idea(_idea_path(ideas_dir, slug), meta, body)
    _cache.invalidate()
    return json.dumps({"success": True, "slug": slug, "field": field, "value": value})


@mcp.tool()
def promote_idea(slug: str, book_slug: str) -> str:
    """Mark an idea as promoted and link it to a book project.

    Sets status to "promoted" and records the book slug in promoted_to.

    Args:
        slug:      The idea's slug.
        book_slug: The slug of the book project this idea was turned into.
    """
    config = _app.load_config()
    ideas_dir = _get_ideas_dir(config)
    result = _read_idea(ideas_dir, slug)

    if result is None:
        return json.dumps({"error": f"Idea '{slug}' not found"})

    meta, body = result
    meta["status"] = "promoted"
    meta["promoted_to"] = book_slug
    meta["last_touched"] = date.today().isoformat()

    _write_idea(_idea_path(ideas_dir, slug), meta, body)
    _cache.invalidate()
    return json.dumps({"success": True, "slug": slug, "promoted_to": book_slug})
