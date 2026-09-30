"""chapter-humanizer support tools.

``scan_chapter_ai_tells`` is the deterministic pre-scan the chapter-humanizer
skill runs before it judges anything by ear; ``check_replacement_text`` lets
the skill verify a proposed fix against the same patterns before presenting it.
Both are read-only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import ToolAnnotations

from tools.analysis.humanizer_scan import (
    check_replacement,
    load_author_dash_limit,
    load_patterns,
    scan_draft,
)
from tools.banlist_loader import author_slug_from_book
from tools.shared.paths import (
    catch_slug_value_error,
    resolve_author_path,
    resolve_chapter_path,
    resolve_project_path,
)

from . import _app
from ._app import mcp

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def _author_for(config: dict[str, Any], book_path: Path, author_slug: str) -> str | None:
    """Explicit slug wins; otherwise read it from the book's CLAUDE.md Book Facts."""
    if author_slug:
        resolve_author_path(config, author_slug)  # validates the slug
        return author_slug
    return author_slug_from_book(book_path)


def _source_report(
    shapes: list[Any],
    tells: list[Any],
    author_patterns: list[Any],
    author: str | None,
) -> tuple[dict[str, int], list[str]]:
    """How many patterns each source yielded, plus a warning for every source
    that came back empty — an empty source otherwise reads as a clean scan."""
    loaded = {"shapes": len(shapes), "tells": len(tells), "author": len(author_patterns)}
    warnings: list[str] = []
    if not shapes or not tells:
        warnings.append(
            "anti-ai-patterns.md yielded no shape or vocabulary patterns; the scan is incomplete, "
            "do not treat an empty result as clean."
        )
    if author and not author_patterns:
        warnings.append(
            f"Author '{author}' yielded no patterns (unknown slug, a display name instead of a slug, "
            "or an author with no bans yet); author rules were NOT applied."
        )
    return loaded, warnings


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
@catch_slug_value_error
def scan_chapter_ai_tells(
    book_slug: str,
    chapter_slug: str,
    author_slug: str = "",
    em_dash_per_1k_limit: float | None = None,
) -> str:
    """Deterministic pre-scan of a chapter draft for AI-construction candidates.

    Matches the Section 11 shape regexes and Section 1 flagged vocabulary of
    ``anti-ai-patterns.md`` plus the author's own bans, applies the per-scene
    density rules (near-miss body language, negation loop, hedge words), flags
    narration dash density, runs of identical sentence openers and invisible
    characters, and reports rhythm metrics. Dashes inside dialogue never count.

    Shapes that need judgement (expository repeat, verb substitution,
    synonym-cycling, literal vs. metaphorical vocabulary) are NOT matched —
    the caller reviews the draft for those itself. Hits inside quoted speech
    carry ``in_dialogue: true`` so in-character usage can be weighed.

    ``draft.md`` has no scene marker: segments split only on horizontal rules
    (``---`` / ``***``); without one the density rules cover the whole chapter
    and ``flags`` says so. The density rules (near-miss, negation loop, hedges)
    count narration only; quoted speech — straight/curly double quotes, German
    „…“, guillemets, single quotes — is excluded, and a speech span that runs
    across paragraphs is not recognised.

    Chapter-level findings come back in ``flags`` (``dash_density`` with the
    number of dashes to rework in ``excess`` and one ``lines`` entry per dash,
    ``uniform_rhythm``, ``no_scene_breaks``). ``sources_loaded`` counts the
    patterns each source yielded and ``warnings`` names any source that came
    back empty — an empty ``hits`` list with a warning is NOT a clean scan.

    Args:
        book_slug: The book project slug.
        chapter_slug: Chapter directory name (e.g. "01-invisible").
        author_slug: Author slug. Defaults to the author named in the book's
            CLAUDE.md Book Facts.
        em_dash_per_1k_limit: Narration dashes per 1,000 words above which a
            ``dash_density`` flag is raised; must be positive. Precedence:
            this argument, then ``em_dash_per_1k_limit`` in the author's
            profile.md frontmatter, then a provisional default.
    """
    if em_dash_per_1k_limit is not None and em_dash_per_1k_limit <= 0:
        return json.dumps({"error": "em_dash_per_1k_limit must be a positive number"})
    config = _app.load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})
    chapter_path = resolve_chapter_path(config, book_slug, chapter_slug)
    draft_path = chapter_path / "draft.md"
    if not draft_path.is_file():
        return json.dumps({"error": f"No draft.md for chapter '{chapter_slug}' in book '{book_slug}'"})

    try:
        draft_text = draft_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return json.dumps({"error": f"Cannot read draft.md for chapter '{chapter_slug}' as UTF-8: {exc}"})

    author = _author_for(config, book_path, author_slug)
    limit = em_dash_per_1k_limit
    if limit is None and author:
        limit = load_author_dash_limit(resolve_author_path(config, author))

    shapes, tells, author_patterns = load_patterns(_PLUGIN_ROOT, author)
    result = scan_draft(
        draft_text,
        global_shapes=shapes,
        global_tells=tells,
        author_patterns=author_patterns,
        dash_limit=limit,
    )
    loaded, warnings = _source_report(shapes, tells, author_patterns, author)
    return json.dumps(
        {
            "book_slug": book_slug,
            "chapter_slug": chapter_slug,
            "author_slug": author or "",
            "sources_loaded": loaded,
            "warnings": warnings,
            **result,
        },
        ensure_ascii=False,
    )


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
@catch_slug_value_error
def check_replacement_text(book_slug: str, text: str, author_slug: str = "") -> str:
    """Check a proposed replacement against the humanizer's patterns.

    Run this on every fix the chapter-humanizer is about to propose. ``clean``
    is false when the text contains a catalog shape, flagged vocabulary, an
    author ban, or an invisible character; ``hits`` names each one. Hedge
    words, near-miss constructions, negation loops and narration dashes come
    back as ``cautions`` (one is fine — weigh them against the scene).

    Args:
        book_slug: The book project slug (selects the author's bans).
        text: The replacement prose to check.
        author_slug: Author slug. Defaults to the author named in the book's
            CLAUDE.md Book Facts.
    """
    config = _app.load_config()
    book_path = resolve_project_path(config, book_slug)
    if not book_path.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found at {book_path}"})

    author = _author_for(config, book_path, author_slug)
    shapes, tells, author_patterns = load_patterns(_PLUGIN_ROOT, author)
    result = check_replacement(
        text,
        global_shapes=shapes,
        global_tells=tells,
        author_patterns=author_patterns,
    )
    loaded, warnings = _source_report(shapes, tells, author_patterns, author)
    return json.dumps({**result, "sources_loaded": loaded, "warnings": warnings}, ensure_ascii=False)
