"""Read-only lookup tools for genre directories and craft reference docs.

These tools surface the static knowledge bundles that live alongside the
plugin (``{plugin_root}/genres/`` and ``{plugin_root}/reference/``).
"""

from __future__ import annotations

import json

from . import _app
from ._app import mcp


@mcp.tool()
def list_genres() -> str:
    """List all available genres."""
    genres_dir = _app.get_genres_dir()
    if not genres_dir.exists():
        return json.dumps({"genres": [], "count": 0})

    genres = sorted(d.name for d in genres_dir.iterdir() if d.is_dir() and (d / "README.md").exists())
    return json.dumps({"genres": genres, "count": len(genres)})


@mcp.tool()
def get_genre(name: str) -> str:
    """Get genre README content."""
    genre_path = _app.get_genres_dir() / name / "README.md"
    if not genre_path.exists():
        return json.dumps({"error": f"Genre '{name}' not found"})
    return genre_path.read_text(encoding="utf-8")


@mcp.tool()
def get_craft_reference(name: str) -> str:
    """Load a craft reference document (e.g. 'story-structure', 'dialog-craft').

    Args:
        name: Reference filename without .md extension
    """
    ref_path = _app.get_reference_dir() / "craft" / f"{name}.md"
    if not ref_path.exists():
        # Try genre subfolder
        ref_path = _app.get_reference_dir() / "genre" / f"{name}.md"
    if not ref_path.exists():
        return json.dumps({"error": f"Reference '{name}' not found"})
    return ref_path.read_text(encoding="utf-8")


@mcp.tool()
def list_craft_references() -> str:
    """List all available craft and genre reference documents."""
    result: dict[str, list[str]] = {"craft": [], "genre": []}

    craft_dir = _app.get_reference_dir() / "craft"
    if craft_dir.exists():
        result["craft"] = sorted(f.stem for f in craft_dir.glob("*.md"))

    genre_dir = _app.get_reference_dir() / "genre"
    if genre_dir.exists():
        result["genre"] = sorted(f.stem for f in genre_dir.glob("*.md"))

    return json.dumps(result)
