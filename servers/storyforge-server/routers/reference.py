"""Read-only lookup tools for genre directories and craft reference docs.

These tools surface the static knowledge bundles that live alongside the
plugin (``{plugin_root}/genres/`` and ``{plugin_root}/reference/``).
"""

from __future__ import annotations

import json

from . import _app
from ._app import mcp


@mcp.tool(annotations={"readOnlyHint": True})
def list_genres() -> str:
    """List all available genres."""
    genres_dir = _app.get_genres_dir()
    if not genres_dir.exists():
        return json.dumps({"genres": [], "count": 0})

    genres = sorted(d.name for d in genres_dir.iterdir() if d.is_dir() and (d / "README.md").exists())
    return json.dumps({"genres": genres, "count": len(genres)})


@mcp.tool(annotations={"readOnlyHint": True})
def get_genre(name: str) -> str:
    """Get genre README content."""
    if ".." in name or "/" in name or "\\" in name or "\x00" in name:
        return json.dumps({"error": f"Invalid genre name: '{name}'"})
    genres_dir = _app.get_genres_dir().resolve()
    genre_path = (genres_dir / name / "README.md").resolve()
    if not genre_path.is_relative_to(genres_dir):
        return json.dumps({"error": f"Invalid genre name: '{name}'"})
    if not genre_path.exists():
        return json.dumps({"error": f"Genre '{name}' not found"})
    return genre_path.read_text(encoding="utf-8")


@mcp.tool(annotations={"readOnlyHint": True})
def get_craft_reference(name: str) -> str:
    """Load a craft reference document (e.g. 'story-structure', 'dialog-craft').

    Args:
        name: Reference filename without .md extension
    """
    if ".." in name or "/" in name or "\\" in name or "\x00" in name:
        return json.dumps({"error": f"Invalid reference name: '{name}'"})
    ref_base = _app.get_reference_dir().resolve()
    ref_path = (ref_base / "craft" / f"{name}.md").resolve()
    if not ref_path.is_relative_to(ref_base):
        return json.dumps({"error": f"Invalid reference name: '{name}'"})
    if not ref_path.exists():
        # Try genre subfolder
        ref_path = (ref_base / "genre" / f"{name}.md").resolve()
        if not ref_path.is_relative_to(ref_base):
            return json.dumps({"error": f"Invalid reference name: '{name}'"})
    if not ref_path.exists():
        return json.dumps({"error": f"Reference '{name}' not found"})
    return ref_path.read_text(encoding="utf-8")


@mcp.tool(annotations={"readOnlyHint": True})
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
