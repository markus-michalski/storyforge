"""Series tools: scaffold a series, get series data, link a book to a series.

Also hosts the series-evolution tooling (Issue #200, D-1 of #195) —
the harvest-character-evolution skill consumes these MCP tools to
bridge between book-level character files and series-level evolution
trackers.
"""

from __future__ import annotations

import json
import re
import shutil
import warnings
from pathlib import Path
from typing import Any

import yaml

from tools.shared.paths import (
    resolve_character_path,
    resolve_people_dir,
    resolve_project_path,
    resolve_series_path,
    slugify,
)
from tools.state.loaders.series import (
    append_updates_log_entry,
    find_series_trackers,
    parse_evolution_sections,
    parse_series_tracker,
    recurring_chars_for_book,
    resolve_book_slug_for_series_tracker,
    write_evolution_section,
)
from tools.state.parsers import parse_frontmatter

from . import _app
from ._app import _cache, mcp


# Snapshot fields read by the harvest tool — mirrors the canonical set
# defined in routers.claudemd._SNAPSHOT_FIELDS (kept in sync manually
# rather than imported to avoid a circular boot dependency).
_SNAPSHOT_LIST_FIELDS = (
    "current_inventory",
    "current_clothing",
    "current_injuries",
    "altered_states",
    "environmental_limiters",
)
_SNAPSHOT_AS_OF_FIELD = "as_of_chapter"


# Relationships heading variants accepted by the harvest reader.
# Singular ``Relationship`` is tolerated for legacy character files.
_RE_RELATIONSHIPS_HEADING = re.compile(
    r"^##\s+(?:Relationships?|Beziehungen(?:\s+(?:ueber\s+die\s+Bande|über\s+die\s+Bände))?)\s*$",
    re.MULTILINE,
)
_RE_NEXT_H2 = re.compile(r"^##\s+\S", re.MULTILINE)


# Band id pattern (B1, B2, ...) for input validation in evolution-write
# tools. Liberal upper-bound — authors may want B12 for long sagas.
_RE_BAND_ID = re.compile(r"^B\d+$")


# Allowed evolution-section kinds, mapped to the canonical lowercase form
# the writer expects.
_VALID_KINDS = {
    "start": "start",
    "ende": "ende",
    "end": "ende",
    "geplant": "geplant",
    "plan": "geplant",
    "planned": "geplant",
}


def _extract_relationships_text(body: str) -> str:
    """Return the body of the first matching ``## Relationships`` section."""
    head = _RE_RELATIONSHIPS_HEADING.search(body)
    if head is None:
        return ""
    rest = body[head.end() :]
    next_h2 = _RE_NEXT_H2.search(rest)
    return (rest[: next_h2.start()] if next_h2 else rest).strip()


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


@mcp.tool()
def read_character_for_harvest(
    book_slug: str,
    character_slug: str,
    book_category: str = "fiction",
) -> str:
    """Read a book-level character file for the harvest skill (D-1 of #195).

    Projects exactly the fields the harvest skill needs to propose a
    ``B{N} Ende`` summary for the matching series-tracker:

    - ``snapshot``: dict with ``current_inventory``, ``current_clothing``,
      ``current_injuries``, ``altered_states``, ``environmental_limiters``
      (all ``list[str]``) and ``as_of_chapter`` (``str``). Missing fields
      default to empty list / empty string.
    - ``relationships_text``: raw text of the ``## Relationships`` (or
      ``## Beziehungen``) section, stripped. Empty string when absent.
    - ``name``, ``role``, ``description``: identity fields from the
      frontmatter; defaults to ``character_slug`` if name is missing.

    Args:
        book_slug: Book project slug.
        character_slug: Character / person slug (no extension).
        book_category: ``"fiction"`` (default) reads from
            ``characters/``; ``"memoir"`` reads from ``people/`` (with
            legacy fallback to ``characters/`` for pre-#59 books).

    Returns:
        ``{name, role, description, snapshot, relationships_text}`` JSON
        on success, or ``{error}`` on a not-found / IO failure.
    """
    config = _app.load_config()

    project_dir = resolve_project_path(config, book_slug)
    if not project_dir.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    if book_category == "memoir":
        char_file = resolve_people_dir(project_dir, "memoir") / f"{character_slug}.md"
    else:
        char_file = resolve_character_path(config, book_slug, character_slug)

    if not char_file.exists():
        return json.dumps(
            {"error": (f"Character '{character_slug}' not found in book '{book_slug}' ({book_category})")}
        )

    text = char_file.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    snapshot: dict[str, list[str] | str] = {}
    for field in _SNAPSHOT_LIST_FIELDS:
        raw = meta.get(field, [])
        if isinstance(raw, list):
            snapshot[field] = [str(item) for item in raw]
        else:
            snapshot[field] = []
    snapshot[_SNAPSHOT_AS_OF_FIELD] = str(meta.get(_SNAPSHOT_AS_OF_FIELD, ""))

    return json.dumps(
        {
            "name": str(meta.get("name", character_slug)),
            "role": str(meta.get("role", "supporting")),
            "description": str(meta.get("description", "")),
            "snapshot": snapshot,
            "relationships_text": _extract_relationships_text(body),
        }
    )


@mcp.tool()
def list_series_trackers_for_book(
    series_slug: str,
    band: str,
) -> str:
    """List series-trackers whose ``recurs_in`` includes the given band.

    The harvest skill calls this once per run to learn which characters
    need a ``B{N} Ende`` summary. Each entry surfaces the resolved
    book-level slug (via :func:`resolve_book_slug_for_series_tracker`)
    and the existing Ende content (if any) so the skill can present a
    diff before overwriting hand-edited drafts.

    Args:
        series_slug: Series slug.
        band: Band id (``"B1"``, ``"B2"``, ...).

    Returns:
        ``{trackers: [{tracker_slug, book_slug, name, role, recurs_in,
        has_existing_ende, existing_ende, path}, ...]}`` JSON or
        ``{error}`` on validation / not-found failure.
    """
    if not _RE_BAND_ID.match(band):
        return json.dumps({"error": f"band must match B<N> (e.g. 'B1') — got {band!r}"})

    config = _app.load_config()
    series_dir = resolve_series_path(config, series_slug)
    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})

    out: list[dict] = []
    for tracker_path in find_series_trackers(series_dir):
        tracker = parse_series_tracker(tracker_path)
        if band not in tracker["recurs_in"]:
            continue
        sections = parse_evolution_sections(tracker_path)
        existing_ende = sections.get(band, {}).get("ende", "")
        out.append(
            {
                "tracker_slug": tracker["slug"],
                "book_slug": resolve_book_slug_for_series_tracker(tracker),
                "name": tracker["name"],
                "role": tracker["role"],
                "recurs_in": tracker["recurs_in"],
                "has_existing_ende": bool(existing_ende),
                "existing_ende": existing_ende,
                "path": str(tracker_path),
            }
        )

    return json.dumps({"trackers": out})


@mcp.tool()
def write_series_evolution_section(
    series_slug: str,
    tracker_slug: str,
    band: str,
    kind: str,
    content: str,
    log_message: str,
    date: str = "",
) -> str:
    """Write a Start/Ende/geplant value into a series-tracker (atomic).

    Two side effects in one call:
    1. Replaces or inserts the requested keyed slot in ``Evolution per
       Band`` (preserving the tracker's existing shape).
    2. Appends a dated entry to ``Updates Log``.

    Args:
        series_slug: Series slug.
        tracker_slug: Tracker slug (file stem under
            ``series/{series_slug}/characters/``).
        band: Band id (``"B1"``, ``"B2"``, ...).
        kind: ``"start"``, ``"ende"``, ``"geplant"`` (also accepts
            ``"plan"``, ``"planned"``, ``"end"`` as aliases).
        content: Body text for the slot.
        log_message: Message to append to Updates Log (date is
            prepended automatically).
        date: Optional ISO date (``YYYY-MM-DD``) for the log entry.
            Defaults to today's UTC date when omitted or empty.

    Returns:
        ``{success, tracker_slug, band, kind, path}`` on success or
        ``{error}`` on validation / not-found failure.
    """
    if not _RE_BAND_ID.match(band):
        return json.dumps({"error": f"band must match B<N> (e.g. 'B1') — got {band!r}"})
    canonical_kind = _VALID_KINDS.get(kind.lower())
    if canonical_kind is None:
        return json.dumps({"error": (f"kind must be one of {sorted(set(_VALID_KINDS))} — got {kind!r}")})

    config = _app.load_config()
    series_dir = resolve_series_path(config, series_slug)
    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})

    tracker_path = series_dir / "characters" / f"{tracker_slug}.md"
    if not tracker_path.exists():
        return json.dumps({"error": (f"Tracker '{tracker_slug}' not found in series '{series_slug}'")})

    write_evolution_section(tracker_path, band=band, kind=canonical_kind, content=content)
    append_updates_log_entry(
        tracker_path,
        message=log_message,
        date=date or None,
    )
    _cache.invalidate()

    return json.dumps(
        {
            "success": True,
            "tracker_slug": tracker_slug,
            "band": band,
            "kind": canonical_kind,
            "path": str(tracker_path),
        }
    )


@mcp.tool()
def copy_recurring_chars_to_new_book(
    series_slug: str,
    prev_book_slug: str,
    new_book_slug: str,
    new_band: str,
    book_category: str = "fiction",
) -> str:
    """1:1 copy of recurring character files from a prior book (Issue #196).

    Dumb-copy precursor to D-2: filters series-trackers by ``recurs_in``
    (must include ``new_band``), resolves each tracker's book-level slug
    via #194's resolver, and copies the source file from the previous
    book's character/people directory to the new book's matching
    directory.

    No frontmatter mutation. No content transformation. The new book's
    character files start as byte-identical copies of the prior book's
    end-of-book state — author edits manually OR runs
    ``/storyforge:bootstrap-book-from-series`` (D-2, future) for smart
    state migration on top.

    Args:
        series_slug: Series slug.
        prev_book_slug: Slug of the source book (typically B1 when
            scaffolding B2). Must exist on disk.
        new_book_slug: Slug of the destination book. Must already be
            scaffolded (i.e. ``projects/{new_book_slug}/`` must exist).
        new_band: Band id of the destination book (``"B2"`` etc.).
        book_category: ``"fiction"`` (default) → ``characters/``;
            ``"memoir"`` → ``people/``.

    Returns:
        ``{copied, skipped, new_chars}`` JSON, where:

        - ``copied``: list of ``{tracker_slug, book_slug, source, dest}``
        - ``skipped``: list of ``{tracker_slug, book_slug, reason}``
          (dest already exists, or source missing while prior_bands
          present)
        - ``new_chars``: list of ``{tracker_slug, book_slug, recurs_in}``
          for trackers whose first appearance is ``new_band`` (no source
          to copy from — author must create manually)

        ``{error}`` on validation / not-found failure.
    """
    if not _RE_BAND_ID.match(new_band):
        return json.dumps({"error": f"new_band must match B<N> (e.g. 'B2') — got {new_band!r}"})

    config = _app.load_config()
    series_dir = resolve_series_path(config, series_slug)
    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})

    prev_dir = resolve_project_path(config, prev_book_slug)
    if not prev_dir.exists():
        return json.dumps({"error": f"Previous book '{prev_book_slug}' not found"})

    new_dir = resolve_project_path(config, new_book_slug)
    if not new_dir.exists():
        return json.dumps({"error": f"New book '{new_book_slug}' not found"})

    layout = "people" if book_category == "memoir" else "characters"
    src_layout = resolve_people_dir(prev_dir, "memoir") if book_category == "memoir" else prev_dir / "characters"
    dst_layout = resolve_people_dir(new_dir, "memoir") if book_category == "memoir" else new_dir / "characters"
    dst_layout.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    new_chars: list[dict] = []

    for tracker in recurring_chars_for_book(series_dir, new_band):
        tracker_slug = tracker["tracker_slug"]
        book_slug = tracker["book_slug"]

        # New char in this band — no source to copy from.
        if not tracker["prior_bands"]:
            new_chars.append(
                {
                    "tracker_slug": tracker_slug,
                    "book_slug": book_slug,
                    "recurs_in": tracker["recurs_in"],
                }
            )
            continue

        source = src_layout / f"{book_slug}.md"
        dest = dst_layout / f"{book_slug}.md"

        if not source.exists():
            # Tracker says the char appears in prior book(s) but the
            # source file is missing — surface as new_char so the author
            # knows they have to create it.
            new_chars.append(
                {
                    "tracker_slug": tracker_slug,
                    "book_slug": book_slug,
                    "recurs_in": tracker["recurs_in"],
                }
            )
            continue

        if dest.exists():
            skipped.append(
                {
                    "tracker_slug": tracker_slug,
                    "book_slug": book_slug,
                    "reason": (f"destination already exists at {layout}/{book_slug}.md — not overwriting"),
                }
            )
            continue

        shutil.copy2(source, dest)
        copied.append(
            {
                "tracker_slug": tracker_slug,
                "book_slug": book_slug,
                "source": str(source),
                "dest": str(dest),
            }
        )

    _cache.invalidate()
    return json.dumps({"copied": copied, "skipped": skipped, "new_chars": new_chars})


@mcp.tool()
def read_tracker_for_bootstrap(
    series_slug: str,
    tracker_slug: str,
    prev_band: str,
    new_band: str,
    prev_book_slug: str = "",
) -> str:
    """Project per-tracker bootstrap data for the D-2 skill (Issue #203).

    Returns the data the bootstrap skill needs to synthesize a starting
    snapshot for the new book's character file:

    - ``prev_band``: dict with ``start`` / ``ende`` / ``geplant`` slot
      values from the tracker (empty strings when absent)
    - ``new_band``: same shape — the planned narrative for the new book
    - ``prev_book_snapshot``: when ``prev_book_slug`` is provided AND the
      character file exists there, projects its current snapshot
      frontmatter (``current_inventory`` etc.) so the skill can show a
      diff. ``None`` otherwise.
    - identity fields: ``name``, ``role``, ``tracker_slug``, ``book_slug``
      (resolved via #194)

    Args:
        series_slug: Series slug.
        tracker_slug: Tracker file stem under ``series/{slug}/characters/``.
        prev_band: Band id to read Ende from (typically the band of the
            previous book — ``"B1"`` when bootstrapping ``B2``).
        new_band: Band id to read (geplant) from (the new book's band).
        prev_book_slug: Optional. When set, also project the prev book
            character file's existing snapshot so the skill can diff.

    Returns:
        ``{tracker_slug, book_slug, name, role, prev_band, new_band,
        prev_book_snapshot}`` JSON, or ``{error}``.
    """
    if not _RE_BAND_ID.match(prev_band):
        return json.dumps({"error": f"prev_band must match B<N> — got {prev_band!r}"})
    if not _RE_BAND_ID.match(new_band):
        return json.dumps({"error": f"new_band must match B<N> — got {new_band!r}"})

    config = _app.load_config()
    series_dir = resolve_series_path(config, series_slug)
    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})

    tracker_path = series_dir / "characters" / f"{tracker_slug}.md"
    if not tracker_path.exists():
        return json.dumps({"error": (f"Tracker '{tracker_slug}' not found in series '{series_slug}'")})

    tracker = parse_series_tracker(tracker_path)
    sections = parse_evolution_sections(tracker_path)
    book_slug = resolve_book_slug_for_series_tracker(tracker)

    def _slot_payload(band: str) -> dict[str, str]:
        band_data = sections.get(band, {})
        return {
            "start": band_data.get("start", ""),
            "ende": band_data.get("ende", ""),
            "geplant": band_data.get("geplant", ""),
            "title": band_data.get("title", band),
            "shape": band_data.get("shape", ""),
        }

    payload: dict[str, Any] = {
        "tracker_slug": tracker["slug"],
        "book_slug": book_slug,
        "name": tracker["name"],
        "role": tracker["role"],
        "prev_band": _slot_payload(prev_band),
        "new_band": _slot_payload(new_band),
        "prev_book_snapshot": None,
    }

    if prev_book_slug:
        prev_dir = resolve_project_path(config, prev_book_slug)
        if prev_dir.exists():
            # Try characters/ first, then people/ for memoir layouts.
            for layout in ("characters", "people"):
                candidate = prev_dir / layout / f"{book_slug}.md"
                if candidate.exists():
                    text = candidate.read_text(encoding="utf-8")
                    meta, _body = parse_frontmatter(text)
                    snap: dict[str, Any] = {}
                    for field in _SNAPSHOT_LIST_FIELDS:
                        raw = meta.get(field, [])
                        snap[field] = [str(item) for item in raw] if isinstance(raw, list) else []
                    snap[_SNAPSHOT_AS_OF_FIELD] = str(meta.get(_SNAPSHOT_AS_OF_FIELD, ""))
                    payload["prev_book_snapshot"] = snap
                    break

    return json.dumps(payload)


# Snapshot fields accepted by ``bootstrap_character_for_new_book``. The
# canonical list lives in routers.claudemd._SNAPSHOT_FIELDS — duplicated
# here to avoid a cross-router import.
_BOOTSTRAP_SNAPSHOT_FIELDS = frozenset(
    {
        "current_inventory",
        "current_clothing",
        "current_injuries",
        "altered_states",
        "environmental_limiters",
        "as_of_chapter",
    }
)


def _apply_bootstrap_frontmatter(char_path: Path, snapshot: dict[str, Any], prev_band: str) -> None:
    """Update ``char_path`` frontmatter with bootstrap snapshot + marker.

    Preserves all existing frontmatter fields, replaces the snapshot
    fields present in ``snapshot`` (list fields default to ``[]`` when
    absent), and sets ``series_evolution_imported_from: {prev_band}``.
    Body of the file is unchanged.
    """
    text = char_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    if not isinstance(meta, dict):
        meta = {}

    list_fields = _BOOTSTRAP_SNAPSHOT_FIELDS - {"as_of_chapter"}
    for field in list_fields:
        if field in snapshot:
            meta[field] = list(snapshot[field])
    if "as_of_chapter" in snapshot:
        meta["as_of_chapter"] = str(snapshot["as_of_chapter"])
    meta["series_evolution_imported_from"] = prev_band

    new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False) + "---\n" + body
    char_path.write_text(new_text, encoding="utf-8")


@mcp.tool()
def bootstrap_character_for_new_book(
    series_slug: str,
    tracker_slug: str,
    prev_book_slug: str,
    new_book_slug: str,
    prev_band: str,
    snapshot_json: str,
    log_message: str = "",
    book_category: str = "fiction",
    date: str = "",
) -> str:
    """Atomic bootstrap of a recurring character for a new book (Issue #203).

    Combines four side effects in one call so the bootstrap skill can
    walk char-by-char without partial-state risk:

    1. **Ensure new book char file exists** — when missing, copy from
       the prev book (reuses the #196 file-copy pattern). When the file
       already exists (e.g. ``/storyforge:new-book`` ran the dumb-copy
       beforehand), the existing body is preserved and only the
       frontmatter is mutated.
    2. **Apply snapshot** — replaces the frontmatter snapshot fields
       (``current_inventory`` etc.) with the user-confirmed values
       from ``snapshot_json``.
    3. **Add marker** — writes
       ``series_evolution_imported_from: {prev_band}`` to the
       frontmatter for transparency.
    4. **Append Updates Log entry** to the series-tracker so the
       evolution history is auditable.

    Args:
        series_slug: Series slug.
        tracker_slug: Tracker file stem.
        prev_book_slug: Source book for the file copy (typically the
            book whose ``B{prev_band}`` end-state was harvested).
        new_book_slug: Destination book.
        prev_band: ``"B1"``, ``"B2"``, ... — used as the marker value.
        snapshot_json: JSON object with any subset of:
            ``current_inventory``, ``current_clothing``,
            ``current_injuries``, ``altered_states``,
            ``environmental_limiters`` (list[str]); ``as_of_chapter``
            (str). Unknown keys are rejected.
        log_message: Optional. Defaults to
            ``"Bootstrapped from {prev_band} for {new_book_slug}"``.
        book_category: ``"fiction"`` or ``"memoir"``.
        date: Optional ISO date for the log entry. Defaults to today.

    Returns:
        ``{success, copied_from_prev, snapshot_applied, log_added,
        new_char_path}`` or ``{error}``.
    """
    if not _RE_BAND_ID.match(prev_band):
        return json.dumps({"error": f"prev_band must match B<N> — got {prev_band!r}"})

    try:
        snapshot: dict[str, Any] = json.loads(snapshot_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"snapshot_json is not valid JSON: {exc}"})
    if not isinstance(snapshot, dict):
        return json.dumps({"error": "snapshot_json must be a JSON object"})
    unknown = set(snapshot.keys()) - _BOOTSTRAP_SNAPSHOT_FIELDS
    if unknown:
        return json.dumps(
            {"error": (f"Unknown snapshot fields: {sorted(unknown)}. Allowed: {sorted(_BOOTSTRAP_SNAPSHOT_FIELDS)}")}
        )

    config = _app.load_config()
    series_dir = resolve_series_path(config, series_slug)
    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})

    tracker_path = series_dir / "characters" / f"{tracker_slug}.md"
    if not tracker_path.exists():
        return json.dumps({"error": (f"Tracker '{tracker_slug}' not found in series '{series_slug}'")})

    new_dir = resolve_project_path(config, new_book_slug)
    if not new_dir.exists():
        return json.dumps({"error": f"New book '{new_book_slug}' not found"})

    tracker = parse_series_tracker(tracker_path)
    book_slug = resolve_book_slug_for_series_tracker(tracker)

    layout = "people" if book_category == "memoir" else "characters"
    dst_layout = resolve_people_dir(new_dir, "memoir") if book_category == "memoir" else new_dir / "characters"
    dst_layout.mkdir(parents=True, exist_ok=True)
    dest = dst_layout / f"{book_slug}.md"

    copied_from_prev = False
    if not dest.exists():
        prev_dir = resolve_project_path(config, prev_book_slug)
        if not prev_dir.exists():
            return json.dumps({"error": f"Previous book '{prev_book_slug}' not found"})
        src_layout = resolve_people_dir(prev_dir, "memoir") if book_category == "memoir" else prev_dir / "characters"
        source = src_layout / f"{book_slug}.md"
        if not source.exists():
            return json.dumps(
                {
                    "error": (
                        f"Source character '{book_slug}.md' missing in "
                        f"'{prev_book_slug}/{layout}/' — cannot copy. The "
                        "character may be a B{N}-first-appearance — create it "
                        "via /storyforge:character-creator before bootstrap."
                    )
                }
            )
        shutil.copy2(source, dest)
        copied_from_prev = True

    _apply_bootstrap_frontmatter(dest, snapshot, prev_band)
    snapshot_applied = True

    final_log = log_message or f"Bootstrapped from {prev_band} for {new_book_slug}"
    append_updates_log_entry(tracker_path, message=final_log, date=date or None)
    log_added = True

    _cache.invalidate()
    return json.dumps(
        {
            "success": True,
            "copied_from_prev": copied_from_prev,
            "snapshot_applied": snapshot_applied,
            "log_added": log_added,
            "new_char_path": str(dest),
        }
    )
