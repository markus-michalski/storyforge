"""Author-profile CRUD tools: list/get/create/update.

Issue #151 also adds ``harvest_book_rules`` here — the harvest tool produces
author-level promotion candidates from a book's CLAUDE.md ``## Rules`` section,
so it lives next to the rest of the author state surface.
"""

from __future__ import annotations
from mcp.types import ToolAnnotations

import json
import os
import re
import shutil
import stat
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from tools.author.discovery_lint import lint_author_discovery
from tools.author.pdf_extractor import (
    extract_text_from_file as _extract_text_impl,
    get_text_stats,
)
from tools.author.rule_harvester import harvest
from tools.claudemd.rules_editor import (
    MarkersNotFoundError,
    list_rules,
)
from tools.db.author_discoveries import (
    VALID_TYPES,
    discoveries_as_writing_discoveries,
    discovery_exists,
    get_discoveries,
    insert_discovery,
    remove_author_discoveries,
    remove_discovery,
    update_source_genres,
)
from tools.db.connection import open_authors_db
from tools.shared.paths import (
    find_projects,
    resolve_author_path,
    resolve_project_path,
    slugify,
)
from tools.state.parsers import parse_author_profile, parse_book_readme, parse_frontmatter

from . import _app
from ._app import _cache, mcp

# Fields that may be written via update_author() — anything not in this set is
# rejected. Keeps prompt-injection from adding arbitrary YAML keys to profiles.
_ALLOWED_AUTHOR_FIELDS: frozenset[str] = frozenset({
    # Core identity (set at creation)
    "name", "updated",
    # Narrative settings
    "primary_genres", "narrative_voice", "tense", "tone",
    "sentence_style", "vocabulary_level", "dialog_style", "pacing",
    "themes", "influences", "avoid",
    # Writing-mode config (set by create-author / new-book)
    "author_writing_mode",
    # Language / locale
    "native_language", "preferred_writing_language",
    # Memoir-specific (set by create-author memoir mode)
    "subject_position", "off_limits", "relationship_to_material",
    # Misc profile meta
    "pen_name", "bio", "website", "social_media", "mood", "voice",
    # Quantitative prose targets (set by study-author, read by author-check)
    "dialog_ratio_target", "fragment_ratio_target",
    "single_line_paragraph_ratio_target", "avg_sentence_length_target",
})

# Subset of _ALLOWED_AUTHOR_FIELDS that create_author()'s own template always writes
# as a real YAML list (primary_genres, tone, avoid via json.dumps(list)). update_author()
# only accepts a plain str value, so without this, updating one of these fields writes
# a scalar string into a field every other writer treats as a list — schema drift a
# live-tool-call test caught (create-author's own Phase 4 fix would otherwise write
# `themes: "a, b"` instead of `themes: ["a", "b"]`). Accepts either a JSON array string
# (`["a", "b"]`) or a plain comma-separated string (`"a, b"`) and normalizes to a list.
_LIST_AUTHOR_FIELDS: frozenset[str] = frozenset({
    "primary_genres", "tone", "themes", "influences", "avoid", "off_limits",
})


def _coerce_author_field_value(field: str, value: str) -> Any:
    """Normalize a raw update_author() string value for known list-typed fields.

    Non-list fields pass through unchanged. List fields accept a JSON array
    string or a comma-separated string; a blank value becomes an empty list.
    """
    if field not in _LIST_AUTHOR_FIELDS:
        return value

    stripped = value.strip()
    if not stripped:
        return []

    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]

    return [part.strip() for part in stripped.split(",") if part.strip()]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def list_authors() -> str:
    """List all author profiles."""
    state = _cache.get()
    authors = state.get("authors", {})
    result = [
        {
            "slug": slug,
            "name": a.get("name", slug),
            "genres": a.get("primary_genres", []),
            "studied_works": a.get("studied_works_count", 0),
        }
        for slug, a in authors.items()
    ]
    return json.dumps({"authors": result, "count": len(result)})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def get_author(slug: str) -> str:
    """Get full author profile data — writing_discoveries read from SQLite (Issue #281)."""
    state = _cache.get()
    author = state.get("authors", {}).get(slug)
    if not author:
        return json.dumps({"error": f"Author '{slug}' not found"})

    conn = open_authors_db()
    try:
        rows = get_discoveries(conn, slug)
    finally:
        conn.close()
    author["writing_discoveries"] = discoveries_as_writing_discoveries(rows)

    return json.dumps(author)


@mcp.tool()
def create_author(
    name: str, genres: str = "", tone: str = "", voice: str = "third-limited", tense: str = "past"
) -> str:
    """Create a new author profile directory with template files.

    Args:
        name: Author pen name
        genres: Comma-separated primary genres
        tone: Comma-separated tone descriptors (e.g. "sarcastic, dark-humor")
        voice: Narrative voice (first-person, third-limited, third-omniscient, second-person)
        tense: Narrative tense (past, present)
    """
    config = _app.load_config()
    slug = slugify(name)
    author_dir = resolve_author_path(config, slug)

    if author_dir.exists():
        return json.dumps({"error": f"Author '{slug}' already exists"})

    author_dir.mkdir(parents=True)
    (author_dir / "studied-works").mkdir()
    (author_dir / "examples").mkdir()

    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    tone_list = [t.strip() for t in tone.split(",") if t.strip()] if tone else []

    today = date.today().isoformat()
    profile = f"""---
name: "{name}"
slug: "{slug}"
created: "{today}"
updated: "{today}"
primary_genres: {json.dumps(genre_list)}
narrative_voice: "{voice}"
tense: "{tense}"
tone: {json.dumps(tone_list)}
sentence_style: "varied"
vocabulary_level: "moderate"
dialog_style: "naturalistic"
pacing: "tension-driven"
themes: []
influences: []
avoid: ["purple-prose", "info-dumps", "deus-ex-machina"]
---

# {name}

## Writing Style

*Style description will be refined through the study-author skill.*

## Signature Techniques

- *To be defined*

## Voice Notes

*Notes on this author's distinctive voice characteristics.*
"""

    (author_dir / "profile.md").write_text(profile, encoding="utf-8")
    (author_dir / "vocabulary.md").write_text(
        f"# {name} — Vocabulary\n\n## Preferred Words\n\n*To be defined*\n\n## Banned Words\n\n- delve\n- tapestry\n- nuanced\n- vibrant\n- resonate\n- pivotal\n- multifaceted\n- realm\n- testament\n- intricate\n- myriad\n- unprecedented\n- foster\n- beacon\n- juxtaposition\n- paradigm\n- synergy\n- interplay\n- ever-evolving\n- navigate (metaphorical)\n\n## Signature Phrases\n\n*To be defined through study-author*\n",
        encoding="utf-8",
    )

    _cache.invalidate()
    return json.dumps(
        {
            "success": True,
            "slug": slug,
            "path": str(author_dir),
            "message": f"Author profile '{name}' created at {author_dir}",
        }
    )


def _clear_readonly_and_retry(func: Any, path: Any, _exc: Any) -> None:
    """shutil.rmtree error handler: clear a read-only bit and retry once.

    Windows raises ``PermissionError`` when rmtree meets a read-only file; the
    standard remedy is to clear the attribute and re-run the failed operation.
    If the retry still fails it re-raises, so delete_author()'s ``except`` can
    turn it into a structured error instead of a raw traceback.

    Registered as ``onexc`` on Python 3.12+ and ``onerror`` on 3.11. Both pass
    three positional args; only the third differs (exception instance vs.
    ``(type, value, tb)`` tuple) and this handler ignores it, so one function
    serves both.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False))
def delete_author(slug: str, force: bool = False) -> str:
    """Delete an author profile directory and all its writing discoveries (Issue #385).

    Removes ``~/.storyforge/authors/{slug}/`` (the whole tree) and every
    ``author_discoveries`` row for the author. Refuses when any book's README
    ``author`` field still references the slug — unless ``force=True``, which
    proceeds and reports the now-orphaned books so the caller can fix them.

    This is the supported alternative to a manual ``rm -rf`` of the author dir:
    it validates the slug, guards against deleting anything outside the authors
    root, checks book references, cleans up the DB, and refreshes the cache.

    Args:
        slug: Author slug to delete (e.g. ``ethan-cole``).
        force: When True, delete even if books still reference the author.

    Returns ``{success, slug, deleted_path, removed_discoveries, referencing_books, message}``
    on success, or ``{error, ...}`` on failure — unknown/unsafe slug, or a book
    reference block when ``force`` is False (then also ``referencing_books``).
    """
    if not slug or not slug.strip():
        return json.dumps({"error": "slug is required"})

    config = _app.load_config()
    try:
        author_dir = resolve_author_path(config, slug)
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": str(exc)})

    # Defense in depth: never let a resolved path escape the authors root,
    # even if _validate_slug is ever loosened. rmtree gets a vetted path only.
    authors_root = Path(config["paths"]["authors_root"]).resolve()
    try:
        resolved_dir = author_dir.resolve()
    except (OSError, RuntimeError) as exc:
        return json.dumps({"error": f"Invalid author slug '{slug}': {exc}"})
    if resolved_dir == authors_root or authors_root not in resolved_dir.parents:
        return json.dumps({"error": f"Refusing to delete '{slug}': path escapes the authors root"})

    if not (author_dir / "profile.md").is_file():
        return json.dumps({"error": f"Author '{slug}' not found"})

    # Reference integrity: which books still point at this author?
    referencing: list[str] = []
    for book_dir in find_projects(config):
        readme = book_dir / "README.md"
        if not readme.is_file():
            continue
        try:
            meta = parse_book_readme(readme)
        except (OSError, ValueError):
            # Unreadable / non-UTF-8 README: skip rather than crash the whole
            # delete (mirrors _read_book_meta's error handling in connection.py).
            continue
        if str(meta.get("author", "")).strip() == slug:
            referencing.append(book_dir.name)

    if referencing and not force:
        return json.dumps({
            "error": (
                f"Author '{slug}' is referenced by {len(referencing)} book(s): "
                f"{referencing}. Pass force=True to delete anyway — this leaves "
                f"those books with a dangling author field."
            ),
            "referencing_books": referencing,
        })

    # Clear the author's DB discoveries first, then remove the directory tree.
    conn = open_authors_db()
    try:
        removed = remove_author_discoveries(conn, slug)
    finally:
        conn.close()

    try:
        # onexc is the Python 3.12+ replacement for onerror; on 3.11 it does
        # not exist yet, so pick the keyword the running interpreter supports.
        rmtree_kwargs: dict[str, Any] = (
            {"onexc": _clear_readonly_and_retry}
            if sys.version_info >= (3, 12)
            else {"onerror": _clear_readonly_and_retry}
        )
        shutil.rmtree(author_dir, **rmtree_kwargs)
    except OSError as exc:
        # DB rows are already gone but the directory survives (e.g. a locked
        # file on Windows). Report it as JSON instead of throwing; re-running
        # finishes the job since profile.md still exists for the existence gate.
        return json.dumps({
            "error": (
                f"Removed DB discoveries for '{slug}' but could not delete "
                f"{author_dir}: {exc}. Re-run to finish removing the directory."
            ),
            "removed_discoveries": removed,
        })

    _cache.invalidate()

    message = f"Author '{slug}' deleted ({removed} discovery row(s) removed)."
    if referencing:
        message += (
            f" WARNING: {len(referencing)} book(s) now reference a missing "
            f"author: {referencing}."
        )

    return json.dumps({
        "success": True,
        "slug": slug,
        "deleted_path": str(author_dir),
        "removed_discoveries": removed,
        "referencing_books": referencing,
        "message": message,
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def harvest_book_rules(book_slug: str, author_slug: str = "") -> str:
    """Collect promotion candidates from a book's findings (Issue #151).

    Walks the book's ``CLAUDE.md ## Rules`` section, classifies each rule as
    ``banned_phrase`` / ``style_principle`` / ``world_rule``, and dedupes
    against the author's profile + vocabulary. Returns a structured candidate
    list with per-entry recommendations (``promote`` / ``keep_book_only``).

    Args:
        book_slug: The book to harvest from.
        author_slug: Optional author slug. If empty, the book's README
            ``author`` field is used.

    Returns the issue-spec'd JSON:
    ``{"book_slug", "author_slug", "candidates": [...], "summary": {...}}``
    Each candidate carries ``id``, ``type``, ``value``, ``context``,
    ``evidence``, ``recommendation``, ``rationale``, ``source``,
    ``target_section``, and (for book-rule sources) ``source_rule_index``.

    On error returns ``{"error": "..."}`` — typical causes: book not found,
    CLAUDE.md missing RULES markers.
    """
    config = _app.load_config()

    book_dir = resolve_project_path(config, book_slug)
    if not book_dir.is_dir():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    readme = book_dir / "README.md"
    book_meta: dict = {}
    if readme.is_file():
        book_meta = parse_book_readme(readme)

    resolved_author = author_slug.strip() or book_meta.get("author", "")

    try:
        parsed_rules = list_rules(config, book_slug)
    except MarkersNotFoundError as exc:
        return json.dumps({"error": f"Book CLAUDE.md missing RULES markers: {exc}"})
    except FileNotFoundError as exc:
        return json.dumps({"error": str(exc)})

    author_profile, vocabulary_text = _load_author_for_dedup(config, resolved_author)
    world_terms = _collect_world_terms(book_dir)

    result = harvest(
        book_slug=book_slug,
        author_slug=resolved_author or None,
        parsed_rules=parsed_rules,
        findings=None,  # manuscript findings integration is a follow-up
        author_profile=author_profile,
        vocabulary_text=vocabulary_text,
        world_terms=world_terms,
    )
    return json.dumps(result)


def _load_author_for_dedup(config: dict, author_slug: str) -> tuple[dict | None, str]:
    """Load author profile + vocabulary text for dedup. Missing files return defaults."""
    if not author_slug:
        return None, ""
    try:
        author_dir = resolve_author_path(config, author_slug)
    except (KeyError, ValueError):
        return None, ""

    profile_path = author_dir / "profile.md"
    profile = parse_author_profile(profile_path) if profile_path.is_file() else None

    vocab_path = author_dir / "vocabulary.md"
    vocab_text = vocab_path.read_text(encoding="utf-8") if vocab_path.is_file() else ""

    return profile, vocab_text


_BOLD_TERM_RE = re.compile(r"\*\*([^*]+)\*\*")
_BULLET_HEADING_RE = re.compile(r"^[-*]\s+\*\*([^*]+)\*\*", re.MULTILINE)


def _collect_world_terms(book_dir: Path) -> set[str]:
    """Build a case-insensitive set of canon/world/character terms.

    Sources walked:

    - ``world/glossary.md`` — bold terms in bullets
    - ``plot/canon-log.md`` — bold terms / headings
    - ``characters/*.md`` and ``people/*.md`` — file slugs and front-matter names

    The set feeds the rule classifier so glossary terms get marked
    ``world_rule`` and are excluded from author-profile promotion.
    """
    terms: set[str] = set()
    for rel in ("world/glossary.md", "plot/canon-log.md"):
        path = book_dir / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        terms.update(m.strip() for m in _BOLD_TERM_RE.findall(text) if m.strip())

    for sub in ("characters", "people"):
        char_dir = book_dir / sub
        if not char_dir.is_dir():
            continue
        for md_file in char_dir.glob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            terms.add(md_file.stem.replace("-", " "))
            try:
                head = md_file.read_text(encoding="utf-8")[:2000]
                meta, _body = parse_frontmatter(head)
                name = meta.get("name") or meta.get("real_name")
                if isinstance(name, str) and name.strip():
                    terms.add(name.strip())
            except OSError:
                continue

    # Drop empty / whitespace-only entries defensively.
    return {t for t in terms if t.strip()}


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
def write_author_discovery(
    author_slug: str,
    section: str,
    text: str,
    book_slug: str,
    year_month: str = "",
    validate: bool = True,
    example: str = "",
    genres: str = "",
    universal: bool = False,
) -> str:
    """Append a discovery to the author_discoveries SQLite table (Issue #281).

    Replaces the profile.md Markdown write from Issue #151. Idempotent via
    UNIQUE(author_slug, discovery_type, text). Cache is invalidated so
    subsequent get_author() calls reflect the new entry immediately.

    Args:
        author_slug: Author whose profile gets the entry.
        section: One of ``recurring_tics``, ``style_principles``, ``donts``.
        text: Entry body (single line), e.g. ``**"thing"** — concretize on sight.``.
        book_slug: Book the discovery emerged from.
        year_month: ``YYYY-MM`` stamp; defaults to today's year-month.
        validate: When ``True`` (default), attaches ``warnings`` and
            ``extracted_patterns`` from the lint check (Issue #218).
        example: Optional illustrative prose (Issue #268).
        genres: Optional comma-separated genre slugs (Issue #266).
        universal: When ``True``, the discovery applies across all genres.

    Returns ``{written, already_present, message}`` on success — with
    ``warnings`` and ``extracted_patterns`` when ``validate=True``
    — or ``{error: ...}`` on failure.
    """
    if section not in VALID_TYPES:
        return json.dumps({"error": f"Invalid section '{section}'. Must be one of: {sorted(VALID_TYPES)}"})

    if not year_month:
        year_month = date.today().strftime("%Y-%m")

    config = _app.load_config()
    try:
        profile_path = resolve_author_path(config, author_slug) / "profile.md"
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": str(exc)})

    if not profile_path.is_file():
        return json.dumps({"error": f"Author '{author_slug}' not found at {profile_path}"})

    lint_result: dict[str, Any] | None = None
    if validate:
        try:
            lint_result = lint_author_discovery(section, text)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})

    source_genres = ",".join(g.strip() for g in genres.split(",") if g.strip()) if genres else ""

    conn = open_authors_db()
    try:
        already = discovery_exists(conn, author_slug, section, text)
        if not already:
            insert_discovery(
                conn,
                author_slug=author_slug,
                discovery_type=section,
                text=text,
                book_slug=book_slug,
                source_genres=source_genres,
                example=example,
                date_added=year_month,
                universal=universal,
            )
        written = not already
    finally:
        conn.close()

    _cache.invalidate()

    payload: dict[str, Any] = {
        "written": written,
        "already_present": already,
        "message": (
            f"Discovery added for {author_slug} [{section}]."
            if written
            else f"Discovery already present for {author_slug} [{section}]."
        ),
    }
    if lint_result is not None:
        payload["warnings"] = lint_result["warnings"]
        payload["extracted_patterns"] = lint_result["extracted_patterns"]
    return json.dumps(payload)


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
def write_author_banned_phrase(author_slug: str, phrase: str, reason: str = "") -> str:
    """Append a banned phrase to author_discoveries (discovery_type='donts') — Issue #281.

    Replaces the vocabulary.md write from Issue #151. Idempotent via the
    UNIQUE constraint. Cache is invalidated on write.

    Args:
        author_slug: Target author.
        phrase: Phrase to ban (e.g. ``thing``).
        reason: Short rationale stored alongside the phrase.

    Returns ``{written, message}`` or ``{error: ...}``.
    """
    config = _app.load_config()
    try:
        profile_path = resolve_author_path(config, author_slug) / "profile.md"
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": str(exc)})

    if not profile_path.is_file():
        return json.dumps({"error": f"Author '{author_slug}' not found at {profile_path}"})

    text = f"**{phrase}**" + (f" — {reason}" if reason else "")

    conn = open_authors_db()
    try:
        already = discovery_exists(conn, author_slug, "donts", text)
        if not already:
            insert_discovery(
                conn,
                author_slug=author_slug,
                discovery_type="donts",
                text=text,
            )
        written = not already
    finally:
        conn.close()

    _cache.invalidate()

    return json.dumps({
        "written": written,
        "message": (
            f"Banned phrase '{phrase}' added for {author_slug}."
            if written
            else f"Banned phrase '{phrase}' already present."
        ),
    })


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
def update_discovery_metadata(
    author_slug: str,
    book_slug: str,
    source_genres: str,
) -> str:
    """Set source_genres for all discoveries from a specific book (Issue #277 / #281).

    Replaces the complex migrate-source-genres skill with a single SQL UPDATE.

    Args:
        author_slug: Target author.
        book_slug: Book whose discoveries get the genre tag.
        source_genres: Comma-separated genre slugs, e.g. ``"shifter-romance,omega-verse"``.

    Returns ``{updated, author_slug, book_slug, source_genres}`` or ``{error: ...}``.
    """
    config = _app.load_config()
    try:
        profile_path = resolve_author_path(config, author_slug) / "profile.md"
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": str(exc)})

    if not profile_path.is_file():
        return json.dumps({"error": f"Author '{author_slug}' not found"})

    conn = open_authors_db()
    try:
        updated = update_source_genres(
            conn,
            author_slug=author_slug,
            book_slug=book_slug,
            source_genres=source_genres,
        )
    finally:
        conn.close()

    _cache.invalidate()

    return json.dumps({
        "updated": updated,
        "author_slug": author_slug,
        "book_slug": book_slug,
        "source_genres": source_genres,
    })


_VOCAB_ENTRY_TYPE_MAP: dict[str, str] = {
    "banned": "donts",
    "preferred": "style_principles",
    "phrase": "style_principles",
}


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
def add_vocabulary_entry(author_slug: str, entry_type: str, text: str, source: str = "") -> str:
    """Add a vocabulary entry for an author — user-facing shortcut (Issue #293).

    Maps ``entry_type`` to the appropriate ``author_discoveries`` type and
    delegates to ``insert_discovery``. Idempotent. Cache invalidated on write.

    Args:
        author_slug: Target author.
        entry_type: ``"banned"`` (→ donts), ``"preferred"`` or ``"phrase"`` (→ style_principles).
        text: The vocabulary entry text, stored as-is.
        source: Optional book slug the entry comes from.

    Returns ``{written, already_present, discovery_type, message}`` or ``{error: ...}``.
    """
    discovery_type = _VOCAB_ENTRY_TYPE_MAP.get(entry_type)
    if discovery_type is None:
        valid = sorted(_VOCAB_ENTRY_TYPE_MAP)
        return json.dumps({"error": f"Invalid entry_type '{entry_type}'. Must be one of: {valid}"})

    config = _app.load_config()
    try:
        profile_path = resolve_author_path(config, author_slug) / "profile.md"
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": str(exc)})

    if not profile_path.is_file():
        return json.dumps({"error": f"Author '{author_slug}' not found at {profile_path}"})

    conn = open_authors_db()
    try:
        already = discovery_exists(conn, author_slug, discovery_type, text)
        if not already:
            insert_discovery(
                conn,
                author_slug=author_slug,
                discovery_type=discovery_type,
                text=text,
                book_slug=source,
            )
        written = not already
    finally:
        conn.close()

    _cache.invalidate()

    return json.dumps({
        "written": written,
        "already_present": already,
        "discovery_type": discovery_type,
        "message": (
            f"Vocabulary entry added for {author_slug} [{discovery_type}]."
            if written
            else f"Entry already present for {author_slug} [{discovery_type}]."
        ),
    })


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def delete_discovery(author_slug: str, discovery_type: str, text: str) -> str:
    """Remove a discovery from author_discoveries by exact text match (Issue #293).

    Used by promote-rule to remove a book-scoped entry when promoting to
    author scope. Validates author existence and discovery_type before deleting.
    Cache invalidated regardless of whether a row was found.

    Args:
        author_slug: Target author.
        discovery_type: One of ``recurring_tics``, ``style_principles``, ``donts``.
        text: Exact text of the entry to remove.

    Returns ``{deleted, message}`` or ``{error: ...}``.
    """
    if discovery_type not in VALID_TYPES:
        return json.dumps({"error": f"Invalid discovery_type '{discovery_type}'. Must be one of: {sorted(VALID_TYPES)}"})

    config = _app.load_config()
    try:
        profile_path = resolve_author_path(config, author_slug) / "profile.md"
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": str(exc)})

    if not profile_path.is_file():
        return json.dumps({"error": f"Author '{author_slug}' not found at {profile_path}"})

    conn = open_authors_db()
    try:
        deleted = remove_discovery(conn, author_slug=author_slug, discovery_type=discovery_type, text=text)
    finally:
        conn.close()

    _cache.invalidate()

    return json.dumps({
        "deleted": deleted,
        "message": (
            f"Discovery removed for {author_slug} [{discovery_type}]."
            if deleted
            else f"No matching discovery found for {author_slug} [{discovery_type}]."
        ),
    })


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
def update_author(slug: str, field: str, value: str) -> str:
    """Update a field in an author's profile frontmatter."""
    config = _app.load_config()
    profile_path = resolve_author_path(config, slug) / "profile.md"

    if not profile_path.exists():
        return json.dumps({"error": f"Author '{slug}' not found"})

    if field not in _ALLOWED_AUTHOR_FIELDS:
        allowed = ", ".join(sorted(_ALLOWED_AUTHOR_FIELDS))
        return json.dumps({"error": f"Field '{field}' is not an allowed author profile field. Allowed: {allowed}"})

    text = profile_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta[field] = _coerce_author_field_value(field, value)
    meta["updated"] = date.today().isoformat()

    new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n" + body
    profile_path.write_text(new_text, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "field": field, "value": meta[field]})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF, EPUB, DOCX, TXT, or MD files for style analysis.

    Used by the study-author skill to read binary formats (EPUB, DOCX) that
    Claude's native Read tool cannot parse. Text files and PDFs can be read
    via the Read tool directly, but EPUB and DOCX require this extraction step.

    Supported formats: .pdf, .epub, .docx, .txt, .md
    Max file size: 50 MB. Max extracted text: 200,000 words.
    Large texts are automatically sampled (beginning / middle / end).

    Args:
        file_path: Absolute path to the file.

    Returns:
        ``{text, stats}`` on success where ``stats`` contains word_count,
        paragraph_count, character_count, estimated_pages, and sampled flag.
        ``{error}`` on file-not-found, unsupported format, or size limit breach.
    """
    config = _app.load_config()
    allowed_roots = [
        Path(config["paths"]["content_root"]).resolve(),
        Path(config["paths"]["authors_root"]).resolve(),
    ]
    try:
        resolved = Path(file_path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return json.dumps({"error": f"Invalid file_path: {exc}"})
    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        return json.dumps({"error": "file_path must be within content_root or authors_root"})
    try:
        text = _extract_text_impl(resolved)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"text": text, "stats": get_text_stats(text)})
