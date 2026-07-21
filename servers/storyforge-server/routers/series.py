"""Series tools: scaffold a series, get series data, link a book to a series.

Also hosts the series-evolution tooling (Issue #200, D-1 of #195) —
the harvest-character-evolution skill consumes these MCP tools to
bridge between book-level character files and series-level evolution
trackers.
"""

from __future__ import annotations
from mcp.types import ToolAnnotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from tools.db.character_snapshots import get_latest_snapshot_for_book
from tools.db.connection import get_book_num, get_db_slug_for_book, open_canon_db
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
def create_series(title: str, genres: str = "", planned_books: int = 3, author: str = "") -> str:
    """Create a new series directory with series.yaml (Issue #279).

    Scaffolds:
    - series.yaml     — plain YAML metadata (name, slug, total_books, author, created, books[])
    - world/          — shared world-building (canon.md pre-seeded)
    - characters/     — series-level character trackers
    - series-arc.md   — overarching narrative
    - timeline.md     — cross-book chronology
    """
    config = _app.load_config()
    slug = slugify(title)
    series_dir = resolve_series_path(config, slug)

    if series_dir.exists():
        return json.dumps({"error": f"Series '{slug}' already exists"})

    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    series_dir.mkdir(parents=True)
    (series_dir / "characters").mkdir()
    (series_dir / "world").mkdir()

    series_yaml_data: dict = {
        "name": title,
        "slug": slug,
        "total_books": planned_books,
        "status": "Planning",
        "description": "",
        "created": today,
        "books": [],
    }
    if author:
        series_yaml_data["author"] = author
    if genre_list:
        series_yaml_data["genres"] = genre_list

    (series_dir / "series.yaml").write_text(
        yaml.dump(series_yaml_data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (series_dir / "series-arc.md").write_text(
        f"# {title} — Series Arc\n\n*The big picture.*\n", encoding="utf-8"
    )
    (series_dir / "timeline.md").write_text(
        f"# {title} — Timeline\n\n*Chronology across all books.*\n", encoding="utf-8"
    )
    (series_dir / "world" / "canon.md").write_text(
        f"# {title} — Canon\n\n*Established facts that cannot be contradicted.*\n",
        encoding="utf-8",
    )

    _cache.invalidate()
    return json.dumps({"success": True, "slug": slug, "path": str(series_dir)})


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
def add_book_to_series(series_slug: str, book_slug: str, number: int, status: str = "drafting") -> str:
    """Link a book to a series.

    Updates two sources of truth (Issue #279):
    1. Book's README.md frontmatter — sets series/series_number fields.
    2. series.yaml books[] list — appends or updates the entry for this book.
       No books/ ref-file directory is created (obsoleted by #279).
    """
    config = _app.load_config()
    series_dir = resolve_series_path(config, series_slug)
    book_dir = resolve_project_path(config, book_slug)

    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})
    if not book_dir.exists():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    # Update book's README.md frontmatter
    book_readme = book_dir / "README.md"
    text = book_readme.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta["series"] = series_slug
    meta["series_number"] = number

    new_text = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n" + body
    book_readme.write_text(new_text, encoding="utf-8")

    # Update series.yaml books[] list (single source of truth for series membership)
    series_yaml_path = series_dir / "series.yaml"
    if series_yaml_path.exists():
        series_data = yaml.safe_load(series_yaml_path.read_text(encoding="utf-8")) or {}
        books_list: list = series_data.get("books", [])
        existing = next((b for b in books_list if b.get("slug") == book_slug), None)
        if existing:
            existing["number"] = number
            existing["status"] = status
        else:
            books_list.append({"slug": book_slug, "number": number, "status": status})
        series_data["books"] = sorted(books_list, key=lambda b: b.get("number", 0))
        series_yaml_path.write_text(
            yaml.dump(series_data, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    _cache.invalidate()
    return json.dumps({"success": True, "series": series_slug, "book": book_slug, "number": number})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
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


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
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


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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
    - ``prev_book_snapshot``: when ``prev_book_slug`` is provided, projects
      the character's current snapshot (``current_inventory`` etc.) so the
      skill can show a diff. Prefers the per-series ``character_snapshots``
      DB (the canonical end-of-chapter write path since Issue #281 —
      ``update_character_snapshot`` never touches the character file's
      frontmatter), falling back to the character file's frontmatter for
      characters whose snapshot only ever came from a prior
      ``bootstrap_character_for_new_book`` write or a hand-edit. ``None``
      when neither source has anything for this character.
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
            snap: dict[str, Any] | None = None

            # Prefer the per-series character_snapshots DB — the canonical
            # end-of-chapter write path since Issue #281. update_character_
            # snapshot() never touches the character file's frontmatter, so
            # a frontmatter-only read here silently missed any snapshot
            # tracked during the prev book's actual chapter-by-chapter
            # writing (only ever saw state left over from a PRIOR bootstrap
            # write, or nothing at all for a book's first-ever bootstrap).
            conn = open_canon_db(get_db_slug_for_book(prev_dir))
            try:
                db_row = get_latest_snapshot_for_book(conn, book_slug, get_book_num(prev_dir))
            finally:
                conn.close()
            if db_row:
                env_raw = db_row.get("environmental_limiters") or ""
                snap = {
                    "current_inventory": db_row.get("inventory", []),
                    "current_clothing": db_row.get("clothing", []),
                    "current_injuries": db_row.get("injuries", []),
                    "altered_states": db_row.get("altered_states", []),
                    "environmental_limiters": [s for s in env_raw.split(", ") if s],
                    _SNAPSHOT_AS_OF_FIELD: "",
                }

            # Fall back to frontmatter (characters/ then people/ for memoir
            # layouts) when the DB has nothing for this character/book.
            if snap is None:
                for layout in ("characters", "people"):
                    candidate = prev_dir / layout / f"{book_slug}.md"
                    if candidate.exists():
                        text = candidate.read_text(encoding="utf-8")
                        meta, _body = parse_frontmatter(text)
                        snap = {}
                        for field in _SNAPSHOT_LIST_FIELDS:
                            raw = meta.get(field, [])
                            snap[field] = [str(item) for item in raw] if isinstance(raw, list) else []
                        snap[_SNAPSHOT_AS_OF_FIELD] = str(meta.get(_SNAPSHOT_AS_OF_FIELD, ""))
                        break

            if snap is not None:
                payload["prev_book_snapshot"] = snap

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


_VALID_TRACKER_TYPES = {"thin", "full"}


def _build_tracker_content(
    name: str,
    slug: str,
    role: str,
    recurs_in: list[str],
    species: str,
    tracker_type: str,
    book_slug: str,
    today: str,
) -> str:
    """Generate h3-shape series character tracker file content."""
    resolved_book_slug = book_slug if book_slug else slug

    # Build frontmatter as a dict — yaml.dump handles quoting/escaping.
    meta: dict[str, Any] = {
        "name": name,
        "slug": slug,
        "role": role,
        "status": "Profile",
        "recurs_in": recurs_in,
        "tracker_type": tracker_type,
    }
    if species:
        meta["species"] = species
    if book_slug:
        meta["book_slug"] = book_slug

    # Sort keys in a canonical order for readability.
    key_order = ["name", "slug", "book_slug", "role", "species", "status", "recurs_in", "tracker_type"]
    sorted_meta = {k: meta[k] for k in key_order if k in meta}

    frontmatter = "---\n" + yaml.dump(sorted_meta, default_flow_style=False, allow_unicode=True, sort_keys=False) + "---\n"

    # Build Evolution per Band in h3 shape.
    # Each band in recurs_in gets Start + Ende headings.
    # The next band after the last gets a (geplant) heading.
    band_numbers = sorted(int(b[1:]) for b in recurs_in)
    next_band_n = band_numbers[-1] + 1

    evolution_lines: list[str] = ["## Evolution per Band\n"]
    for i, n in enumerate(band_numbers):
        band = f"B{n}"
        if i == 0:
            start_hint = "Initial state, defining wound or driver, current situation. Filled at planning time."
            ende_hint = "Filled by the harvest tool at end-of-book from book-level frontmatter snapshot fields and relationships."
        else:
            prev = f"B{band_numbers[i - 1]}"
            start_hint = f"Where the character begins in {band}. Filled by the bootstrap tool from {prev} Ende."
            ende_hint = f"Where the character ends in {band}. Filled by the harvest tool at end-of-book."
        evolution_lines.append(f"\n### {band} Start\n*{start_hint}*\n")
        evolution_lines.append(f"\n### {band} Ende\n*{ende_hint}*\n")

    next_band = f"B{next_band_n}"
    evolution_lines.append(
        f"\n### {next_band} (geplant)\n"
        f"*Planned arc for Book {next_band_n}. What changes? What carries forward? "
        f"What new external pressure forces growth? Filled at planning time.*\n"
    )

    body = f"""
# {name} — Series Evolution Tracker

> Full character profile per book: `projects/<book-slug>/characters/{resolved_book_slug}.md`

## Snapshot

*One-paragraph essence at series scope. What is constant about this character across all books? Capture identity, role, key relationship anchors. Not plot, not arc-per-book — the through-line.*

{"".join(evolution_lines)}
## Beziehungen über die Bände

*Cross-book relationship arcs. Capture how each significant pairing evolves across the series, not just within one book. Format:*

- **{{Other Character}}**: {{B1 dynamic}} → {{B2 shift}} → resolution

## Updates Log

- {today} — Tracker scaffolded by series-planner
"""
    return frontmatter + body


@mcp.tool()
def create_character_tracker(
    series_slug: str,
    name: str,
    slug: str,
    role: str,
    recurs_in: list[str],
    species: str = "",
    tracker_type: str = "thin",
    book_slug: str = "",
) -> str:
    """Create a series character tracker file from the canonical template.

    Scaffolds ``series/{series_slug}/characters/{slug}.md`` with:
    - YAML frontmatter (name, slug, role, species, status, recurs_in,
      tracker_type; ``book_slug`` included only when it differs from
      ``slug``)
    - h3-shape Evolution per Band sections: ``### BN Start`` and
      ``### BN Ende`` for every band in ``recurs_in``, plus
      ``### B{N+1} (geplant)`` for the next planned book
    - Empty Snapshot and Beziehungen sections
    - An initial Updates Log entry dated today

    Use this in the series-planner Step 5 (Canon Management) to create
    one tracker per recurring character rather than copying the template
    manually.

    Args:
        series_slug: Series slug (must already exist).
        name: Full character name (e.g. ``"King Caelan"``).
        slug: Tracker file slug / stem (e.g. ``"king-caelan"``).
        role: Character role (e.g. ``"supporting"``, ``"protagonist"``).
        recurs_in: Band ids the character appears in
            (e.g. ``["B1", "B2", "B3"]``). Each must match ``B<N>``.
            Must not be empty.
        species: Optional species / type (e.g. ``"vampire"``).
        tracker_type: ``"thin"`` (default) or ``"full"``. Use ``"full"``
            only for characters that span books equally without a home
            book.
        book_slug: Optional. Set when the tracker slug differs from the
            book-level character file stem (e.g. tracker ``king-caelan``
            ↔ book file ``caelan.md``). Omit for the common case where
            they match — the resolver falls back to ``slug``.

    Returns:
        ``{success, slug, path}`` on success or ``{error}`` on failure.
    """
    if not recurs_in:
        return json.dumps({"error": "recurs_in must not be empty"})

    if len(set(recurs_in)) != len(recurs_in):
        dupes = [b for b in recurs_in if recurs_in.count(b) > 1]
        return json.dumps({"error": f"recurs_in contains duplicate band ids: {sorted(set(dupes))}"})

    invalid_bands = [b for b in recurs_in if not _RE_BAND_ID.match(str(b))]
    if invalid_bands:
        return json.dumps(
            {"error": f"recurs_in contains invalid band ids: {invalid_bands} — each must match B<N> (e.g. 'B1')"}
        )

    if tracker_type not in _VALID_TRACKER_TYPES:
        return json.dumps(
            {"error": f"tracker_type must be one of {sorted(_VALID_TRACKER_TYPES)} — got {tracker_type!r}"}
        )

    config = _app.load_config()
    series_dir = resolve_series_path(config, series_slug)
    if not series_dir.exists():
        return json.dumps({"error": f"Series '{series_slug}' not found"})

    chars_dir = series_dir / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)

    tracker_path = chars_dir / f"{slug}.md"
    if tracker_path.exists():
        return json.dumps({"error": f"Tracker '{slug}' already exists in series '{series_slug}'"})

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    content = _build_tracker_content(
        name=name,
        slug=slug,
        role=role,
        recurs_in=[str(b) for b in recurs_in],
        species=species,
        tracker_type=tracker_type,
        book_slug=book_slug,
        today=today,
    )
    tracker_path.write_text(content, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({"success": True, "slug": slug, "path": str(tracker_path)})
