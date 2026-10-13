"""Read-only lookup tools for genre directories and craft reference docs.

These tools surface the static knowledge bundles that live alongside the
plugin (``{plugin_root}/genres/`` and ``{plugin_root}/reference/``).
"""

from __future__ import annotations
from mcp.types import ToolAnnotations

import json
from pathlib import Path

from . import _app
from ._app import mcp


def _genre_dirs_by_precedence() -> list[Path]:
    """Return genre base dirs in lookup order: user genres first.

    A user-created genre with the same name as a built-in shadows it
    (Issue #643) — the user's own definition should win when they've
    customized or forked a built-in genre.
    """
    return [_app.get_user_genres_dir(), _app.get_builtin_genres_dir()]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def list_genres() -> str:
    """List all available genres (built-in plus user-created, Issue #643)."""
    genres: dict[str, None] = {}
    # Built-ins first, then user genres — dict insertion order determines
    # nothing here since the result is sorted, but a user genre with the
    # same slug as a built-in collapses to one entry either way.
    for base_dir in reversed(_genre_dirs_by_precedence()):
        if not base_dir.exists():
            continue
        for d in base_dir.iterdir():
            if d.is_dir() and (d / "README.md").exists():
                genres[d.name] = None

    names = sorted(genres)
    return json.dumps({"genres": names, "count": len(names)})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def get_genre(name: str) -> str:
    """Get genre README content (user genres take precedence, Issue #643)."""
    if ".." in name or "/" in name or "\\" in name or "\x00" in name:
        return json.dumps({"error": f"Invalid genre name: '{name}'"})

    for base_dir in _genre_dirs_by_precedence():
        base_dir = base_dir.resolve()
        genre_path = (base_dir / name / "README.md").resolve()
        if not genre_path.is_relative_to(base_dir):
            return json.dumps({"error": f"Invalid genre name: '{name}'"})
        if genre_path.exists():
            return genre_path.read_text(encoding="utf-8")

    return json.dumps({"error": f"Genre '{name}' not found"})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
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


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
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
