"""Series-tracker loaders (Issues #194, #200).

Bridges the gap between book-level character files
(``projects/{book}/characters/{slug}.md``) and series-level evolution
trackers (``series/{series}/characters/{tracker-slug}.md``).

The series-planner skill may pick role/title-prefixed slugs at series
scope when a character is recurringly addressed by title across the
trilogy (e.g. ``king-caelan`` for "King Caelan", whose book-level file
is just ``caelan.md``). The tracker schema therefore supports an
optional ``book_slug:`` frontmatter field that declares the explicit
mapping. When absent, the tracker slug IS the book-level slug — no
breakage for the common case where they match.

The series-evolution tooling (harvest, bootstrap, brief-source — see
Epic #195) consumes the resolver and the section parsers below. Two
tracker shapes exist in the wild:

- **bullet shape** (most existing trackers): ``### B1 Firelight`` heading
  with keyed bullets ``- **Start:** ...`` / ``- **Ende:** ...`` /
  ``- **Plan:** ...`` in the body. May contain freeform bullets.
- **h3 shape** (spec-style): separate ``### B1 Start`` / ``### B1 Ende``
  / ``### B1 (geplant)`` H3 headings, body is whatever follows until
  the next H2/H3.

Parsers are tolerant of both. The shape is reported per-band so writers
can preserve the existing structure rather than dual-writing.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.state.parsers import parse_frontmatter


# Heading patterns
# H2 (top-level section markers we care about).
_RE_H2_EVOLUTION = re.compile(r"^##\s+Evolution\s+per\s+Band\s*$", re.MULTILINE)
# Relationships heading — supports German variants (with/without umlauts) and
# the English "Relationships" fallback.
_RE_H2_RELATIONSHIPS = re.compile(
    r"^##\s+(?:"
    r"Beziehungen\s+(?:ueber\s+die\s+Bande|über\s+die\s+Bände)"
    r"|Relationships"
    r")\s*$",
    re.MULTILINE,
)
_RE_H2_UPDATES_LOG = re.compile(r"^##\s+Updates\s+Log\s*$", re.MULTILINE)
# Generic next H2 to find section end.
_RE_H2_ANY = re.compile(r"^##\s+\S", re.MULTILINE)

# Band heading shapes inside Evolution per Band.
# Bullet shape: "### B1 Firelight" or "### B2 Moonrise (geplant)" — band id
# (B<N>) at the start, anything after it is the title. ``rest`` matches
# only same-line trailing characters: ``[ \t]+`` (not ``\s+``) prevents
# the engine from greedily consuming a following newline + bullet body.
_RE_BAND_H3 = re.compile(r"^###[ \t]+(?P<band>B\d+)(?P<rest>[ \t]+[^\n]*)?[ \t]*$", re.MULTILINE)

# Keyed bullet inside a band body: "- **Start:** ..." / "- **Ende:** ..." /
# "- **Plan:** ...". The colon sits INSIDE the bold marker (the canonical
# author convention) — also tolerates a trailing-colon variant
# ("- **Start**: ...") for resilience. Match is case-insensitive on the
# key.
_RE_KEYED_BULLET = re.compile(
    r"^-\s+\*\*(?P<key>start|ende|plan|geplant|planned)\s*:?\s*\*\*"
    r"\s*:?\s*(?P<value>.*)$",
    re.IGNORECASE,
)

# Plain bullet (no keyed prefix). Used to harvest "(geplant)" body content
# where every bullet is a planning point rather than a Start/Ende keyed one.
_RE_PLAIN_BULLET = re.compile(r"^-\s+(?P<value>.+)$")


def parse_series_tracker(path: Path) -> dict[str, Any]:
    """Parse a series-character-tracker frontmatter into a dict.

    Returns at minimum: ``slug``, ``name``, ``role``, ``species``,
    ``status``, ``recurs_in``, ``tracker_type``, ``book_slug``.
    The ``book_slug`` value is ``None`` when the field is absent.
    ``slug`` falls back to the path stem so downstream callers always
    have a non-empty value.
    """
    text = path.read_text(encoding="utf-8")
    meta, _body = parse_frontmatter(text)

    return {
        "slug": str(meta.get("slug") or path.stem),
        "name": str(meta.get("name", path.stem)),
        "role": str(meta.get("role", "supporting")),
        "species": str(meta.get("species", "")),
        "status": str(meta.get("status", "Profile")),
        "recurs_in": list(meta.get("recurs_in") or []),
        "tracker_type": str(meta.get("tracker_type", "thin")),
        "book_slug": meta.get("book_slug"),
    }


def resolve_book_slug_for_series_tracker(tracker: dict[str, Any]) -> str:
    """Return the book-level slug for a series tracker.

    Priority: explicit ``book_slug`` field (when truthy) > tracker
    ``slug`` as-is. Returns an empty string when neither is set so
    callers can branch without exception handling.
    """
    book_slug = tracker.get("book_slug")
    if book_slug:
        return str(book_slug)
    return str(tracker.get("slug") or "")


def find_series_trackers(series_dir: Path) -> list[Path]:
    """Return all series-character-tracker files for a series.

    Looks under ``{series_dir}/characters/`` and returns every ``*.md``
    sorted by path, excluding ``INDEX.md``. Returns an empty list when
    the directory does not exist.
    """
    chars_dir = series_dir / "characters"
    if not chars_dir.exists():
        return []
    return sorted(p for p in chars_dir.glob("*.md") if p.name != "INDEX.md")


# Band id pattern (B1, B2, ...) — kept here so callers don't need to
# import from the routing layer.
_RE_VALID_BAND = re.compile(r"^B\d+$")


def recurring_chars_for_book(series_dir: Path, band: str) -> list[dict[str, Any]]:
    """Return tracker dicts whose ``recurs_in`` includes ``band``.

    Used by the new-book auto-copy logic (Issue #196) and the future
    bootstrap-book-from-series skill (D-2 of Epic #195) to learn which
    characters belong in a given book band.

    Each entry mirrors :func:`parse_series_tracker` output (so callers
    have ``slug``, ``book_slug``, ``recurs_in``, ``role``, ...) plus a
    ``tracker_slug`` alias and a ``prior_bands`` field — the bands in
    ``recurs_in`` that come strictly before ``band``, sorted ascending.
    Empty ``prior_bands`` means the character first appears in ``band``
    and has no source file in any prior book.

    Returns an empty list when ``band`` is not a valid ``B<N>`` id, when
    the characters directory is missing, or when no trackers match.
    Results are sorted by ``tracker_slug`` for deterministic output.
    """
    if not _RE_VALID_BAND.match(band):
        return []

    target_n = int(band[1:])
    out: list[dict[str, Any]] = []
    for path in find_series_trackers(series_dir):
        tracker = parse_series_tracker(path)
        recurs = [str(b) for b in tracker.get("recurs_in") or []]
        if band not in recurs:
            continue

        # Sort prior bands numerically so B10 comes after B2 (string sort
        # would put B10 between B1 and B2).
        prior_bands = sorted(
            (b for b in recurs if _RE_VALID_BAND.match(b) and int(b[1:]) < target_n),
            key=lambda b: int(b[1:]),
        )
        out.append(
            {
                **tracker,
                "tracker_slug": tracker["slug"],
                "book_slug": resolve_book_slug_for_series_tracker(tracker),
                "prior_bands": prior_bands,
            }
        )

    out.sort(key=lambda t: t["tracker_slug"])
    return out


# ---------------------------------------------------------------------------
# Section parsers — Evolution per Band, Beziehungen, Updates Log
# ---------------------------------------------------------------------------


def _section_body(text: str, start_re: re.Pattern[str]) -> str:
    """Return the body of a top-level section starting at ``start_re``.

    The body extends from the line after the heading match to the next
    H2 heading (exclusive) or end-of-file. Returns an empty string if
    the heading is not present.
    """
    head = start_re.search(text)
    if head is None:
        return ""
    body_start = head.end()
    rest = text[body_start:]
    next_h2 = _RE_H2_ANY.search(rest)
    return rest[: next_h2.start()] if next_h2 else rest


def _is_band_planned(title: str) -> bool:
    """``True`` when a band heading marks the band as planned.

    Triggers on a parenthetical suffix containing "geplant", "plan", or
    "planned" — case-insensitive.
    """
    return bool(re.search(r"\(\s*(geplant|plan(?:ned)?)\s*\)", title, re.IGNORECASE))


def _normalize_key(raw: str) -> str:
    """Map a keyed-bullet key to one of: ``start``, ``ende``, ``geplant``."""
    key = raw.strip().lower()
    if key in {"plan", "planned", "geplant"}:
        return "geplant"
    return key  # "start" or "ende"


def _collect_keyed_value(lines: list[str], idx: int) -> tuple[str, int]:
    """Collect a keyed bullet's value plus indented continuation lines.

    Returns ``(value, next_index)``. The keyed bullet sits at ``lines[idx]``;
    continuation is any subsequent indented line until a blank line or
    a new bullet/heading is reached.
    """
    match = _RE_KEYED_BULLET.match(lines[idx])
    assert match is not None
    parts = [match.group("value").strip()]
    j = idx + 1
    while j < len(lines):
        nxt = lines[j]
        if not nxt.strip():
            break
        if nxt.lstrip().startswith("-") or nxt.lstrip().startswith("#"):
            break
        # Continuation: any line that starts with whitespace.
        if nxt.startswith((" ", "\t")):
            parts.append(nxt.strip())
            j += 1
            continue
        break
    return " ".join(p for p in parts if p), j


def _parse_band_body(body: str, planned: bool) -> dict[str, str]:
    """Parse a single band's body into ``start``/``ende``/``geplant`` slots.

    Heuristic:
    - If any keyed bullet (``**Start:**`` / ``**Ende:**`` / ``**Plan:**``)
      is present, fill those slots from the keyed bullets.
    - Additionally, if the band is heading-marked as planned (e.g.
      ``### B2 Moonrise (geplant)``) and no keyed bullets exist, treat
      every plain bullet as a planning line — joined into ``geplant``.
    - Falls back to the h3 shape elsewhere; this helper is only called
      for the bullet shape.
    """
    slots = {"start": "", "ende": "", "geplant": ""}
    lines = body.splitlines()
    has_keyed = False

    i = 0
    while i < len(lines):
        m = _RE_KEYED_BULLET.match(lines[i])
        if m is None:
            i += 1
            continue
        has_keyed = True
        value, next_i = _collect_keyed_value(lines, i)
        slot = _normalize_key(m.group("key"))
        slots[slot] = value
        i = next_i

    if has_keyed:
        return slots

    if planned:
        # No keyed bullets but the band heading marks the band as planned —
        # treat plain bullets as the geplant content.
        plain: list[str] = []
        for ln in lines:
            pm = _RE_PLAIN_BULLET.match(ln.strip())
            if pm is not None:
                plain.append(pm.group("value").strip())
        slots["geplant"] = " ".join(plain).strip()

    return slots


def parse_evolution_sections(path: Path) -> dict[str, dict[str, Any]]:
    """Parse the ``## Evolution per Band`` section into per-band slots.

    Returns a mapping ``{"B1": {...}, "B2": {...}}`` where each band's
    dict contains:

    - ``band`` — the band id (``"B1"``)
    - ``title`` — the heading text after ``###`` (e.g. ``"B1 Firelight"``)
    - ``shape`` — ``"bullet"`` or ``"h3"``
    - ``start`` / ``ende`` / ``geplant`` — extracted slot values, possibly
      empty strings
    - ``raw_body`` — the band's full body (for diff display in the
      harvest skill)

    Tolerant of both shapes; the shape is reported per band so writers
    preserve the existing structure rather than dual-writing.
    """
    text = path.read_text(encoding="utf-8")
    body = _section_body(text, _RE_H2_EVOLUTION)
    if not body.strip():
        return {}

    matches = list(_RE_BAND_H3.finditer(body))
    if not matches:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for i, m in enumerate(matches):
        band = m.group("band")
        title = (band + (m.group("rest") or "")).strip()
        section_start = m.end()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_body = body[section_start:section_end].strip("\n")

        # Shape detection: if the heading is "B<N> Start|Ende|(geplant)|Plan",
        # treat as h3 shape — body is the whole text under this heading.
        kind_match = re.match(
            r"^B\d+\s+(?P<kind>Start|Ende|Plan|Planned|\(\s*geplant\s*\)|\(\s*plan(?:ned)?\s*\))\s*$",
            title,
            re.IGNORECASE,
        )
        if kind_match is not None:
            slots = {"start": "", "ende": "", "geplant": ""}
            kind_raw = kind_match.group("kind").lower()
            if "geplant" in kind_raw or "plan" in kind_raw:
                slot = "geplant"
            elif kind_raw == "start":
                slot = "start"
            else:
                slot = "ende"
            slots[slot] = section_body.strip()
            entry: dict[str, Any] = {
                "band": band,
                "title": title,
                "shape": "h3",
                "start": slots["start"],
                "ende": slots["ende"],
                "geplant": slots["geplant"],
                "raw_body": section_body,
            }
            # Merge into existing band entry (h3 shape may produce
            # multiple H3s for the same band — Start, Ende, geplant).
            if band in out:
                for k in ("start", "ende", "geplant"):
                    if entry[k] and not out[band][k]:
                        out[band][k] = entry[k]
                out[band]["raw_body"] = (out[band]["raw_body"] + "\n\n" + section_body).strip()
            else:
                out[band] = entry
            continue

        # Bullet shape.
        planned = _is_band_planned(title)
        slots = _parse_band_body(section_body, planned)
        out[band] = {
            "band": band,
            "title": title,
            "shape": "bullet",
            "start": slots["start"],
            "ende": slots["ende"],
            "geplant": slots["geplant"],
            "raw_body": section_body,
        }

    return out


def parse_relationships_section(path: Path) -> str:
    """Return the raw text under ``## Beziehungen ueber die Bande``.

    Tolerates the umlaut variant (``Beziehungen über die Bände``) and
    the English fallback ``## Relationships``. Returns an empty string
    when the section is absent.
    """
    text = path.read_text(encoding="utf-8")
    body = _section_body(text, _RE_H2_RELATIONSHIPS)
    return body.strip()


def parse_updates_log(path: Path) -> list[str]:
    """Return the bulleted entries under ``## Updates Log``.

    Each returned entry is the text after the leading ``-`` and any
    whitespace, stripped. Non-bullet lines (placeholders, prose) are
    ignored. Returns an empty list when the section is absent.
    """
    text = path.read_text(encoding="utf-8")
    body = _section_body(text, _RE_H2_UPDATES_LOG)
    entries: list[str] = []
    for line in body.splitlines():
        m = _RE_PLAIN_BULLET.match(line.strip())
        if m is not None:
            entries.append(m.group("value").strip())
    return entries


# ---------------------------------------------------------------------------
# Section writers — Evolution per Band, Updates Log
# ---------------------------------------------------------------------------


_KIND_LABEL = {"start": "Start", "ende": "Ende", "geplant": "Plan"}


def _section_bounds(text: str, header_re: re.Pattern[str]) -> tuple[int, int] | None:
    """Return ``(body_start, body_end)`` char offsets of a top-level section.

    ``body_start`` points to the first character after the heading line
    (typically a newline). ``body_end`` points to the first character of
    the next H2 heading, or ``len(text)`` for the last section. Returns
    ``None`` when the section is absent.
    """
    head = header_re.search(text)
    if head is None:
        return None
    body_start = head.end()
    rest = text[body_start:]
    next_h2 = _RE_H2_ANY.search(rest)
    body_end = body_start + next_h2.start() if next_h2 else len(text)
    return body_start, body_end


def _find_band_bounds(text: str, body_start: int, body_end: int, band: str) -> list[tuple[int, int, str]]:
    """Return list of ``(heading_start, body_end, title)`` for matching bands.

    A band can appear multiple times under the h3 shape (separate H3s
    for Start/Ende/geplant). The bullet shape produces a single hit.
    Each tuple's ``body_end`` is the offset of the next H3/H2 or the
    section end.
    """
    body = text[body_start:body_end]
    matches = list(_RE_BAND_H3.finditer(body))
    out: list[tuple[int, int, str]] = []
    for i, m in enumerate(matches):
        if m.group("band") != band:
            continue
        heading_start = body_start + m.start()
        next_start = body_start + matches[i + 1].start() if i + 1 < len(matches) else body_end
        title = (m.group("band") + (m.group("rest") or "")).strip()
        out.append((heading_start, next_start, title))
    return out


def _format_keyed_bullet(kind: str, content: str) -> str:
    """Return ``- **{Kind}:** {content}`` with the canonical label."""
    label = _KIND_LABEL[kind]
    return f"- **{label}:** {content.strip()}"


def _is_h3_shape_title(title: str) -> bool:
    """``True`` when the band heading is the spec-style ``B<N> Start|Ende|...``."""
    return bool(
        re.match(
            r"^B\d+\s+(Start|Ende|Plan|Planned|\(\s*geplant\s*\)|"
            r"\(\s*plan(?:ned)?\s*\))\s*$",
            title,
            re.IGNORECASE,
        )
    )


def _h3_title_kind(title: str) -> str | None:
    """Return ``start`` / ``ende`` / ``geplant`` for an h3-shape band title."""
    m = re.match(
        r"^B\d+\s+(?P<kind>Start|Ende|Plan|Planned|\(\s*geplant\s*\)|"
        r"\(\s*plan(?:ned)?\s*\))\s*$",
        title,
        re.IGNORECASE,
    )
    if m is None:
        return None
    raw = m.group("kind").lower()
    if "geplant" in raw or "plan" in raw:
        return "geplant"
    return raw


def _rewrite_band_body_bullet_shape(body: str, kind: str, content: str, planned: bool) -> str:
    """Replace or insert a keyed bullet inside a bullet-shape band body."""
    lines = body.splitlines(keepends=True)

    # Detect existing keyed bullets.
    keyed_indices: dict[str, tuple[int, int]] = {}  # kind -> (start_idx, end_idx_exclusive)
    has_any_keyed = False
    i = 0
    while i < len(lines):
        m = _RE_KEYED_BULLET.match(lines[i].rstrip("\n"))
        if m is None:
            i += 1
            continue
        has_any_keyed = True
        slot = _normalize_key(m.group("key"))
        # Find continuation lines (indented) that belong to this bullet.
        j = i + 1
        while j < len(lines):
            stripped = lines[j].rstrip("\n")
            if not stripped.strip():
                break
            if stripped.lstrip().startswith(("-", "#")):
                break
            if stripped.startswith((" ", "\t")):
                j += 1
                continue
            break
        keyed_indices[slot] = (i, j)
        i = j

    new_bullet_line = _format_keyed_bullet(kind, content) + "\n"

    if kind in keyed_indices:
        # Replace the existing keyed bullet (drop continuation lines too).
        s, e = keyed_indices[kind]
        return "".join(lines[:s]) + new_bullet_line + "".join(lines[e:])

    if planned and not has_any_keyed and kind == "geplant":
        # Planned band with no keyed bullets — replace all plain bullets
        # (those are the existing plan content) with the single new
        # bullet. Preserve any non-bullet lines (rare but possible).
        kept: list[str] = []
        replaced = False
        for ln in lines:
            if _RE_PLAIN_BULLET.match(ln.rstrip("\n").strip()):
                if not replaced:
                    kept.append(new_bullet_line)
                    replaced = True
                # Skip subsequent existing plan bullets.
                continue
            kept.append(ln)
        if not replaced:
            # Body had no bullets at all — append.
            return body + ("\n" if body and not body.endswith("\n") else "") + new_bullet_line
        return "".join(kept)

    # No existing keyed bullet for this kind — insert in canonical order
    # (Start, Ende, Plan) relative to siblings. If a sibling exists,
    # insert after the matching neighbor; otherwise append.
    canonical_order = ["start", "ende", "geplant"]
    after_kinds = canonical_order[: canonical_order.index(kind)]
    insert_at: int | None = None
    for predecessor in reversed(after_kinds):
        if predecessor in keyed_indices:
            _, end = keyed_indices[predecessor]
            insert_at = end
            break
    if insert_at is None:
        # No predecessor — insert before the first keyed sibling, or
        # append at the start of the body.
        for successor in canonical_order[canonical_order.index(kind) + 1 :]:
            if successor in keyed_indices:
                insert_at = keyed_indices[successor][0]
                break
    if insert_at is None:
        # Empty / no keyed bullets — append, ensuring the body ends with
        # a newline before our bullet line.
        suffix = "" if body.endswith("\n") or body == "" else "\n"
        return body + suffix + new_bullet_line

    return "".join(lines[:insert_at]) + new_bullet_line + "".join(lines[insert_at:])


def _rewrite_h3_band(text: str, band_hits: list[tuple[int, int, str]], kind: str, content: str) -> str:
    """Replace or insert an h3-shape body for the given band+kind.

    ``band_hits`` is the list returned by ``_find_band_bounds`` when the
    band uses h3 shape (one hit per existing sub-heading: Start, Ende,
    geplant).
    """
    target_label = _KIND_LABEL[kind]
    target_heading = f"### {band_hits[0][2].split()[0]} {target_label}"

    for hs, he, title in band_hits:
        kind_for_title = _h3_title_kind(title)
        if kind_for_title == kind:
            # Replace the body of this H3 (heading line stays).
            heading_end = text.find("\n", hs)
            if heading_end == -1 or heading_end >= he:
                heading_end = he
            else:
                heading_end += 1
            head_line = text[hs:heading_end]
            new_block = head_line + content.strip() + "\n\n"
            return text[:hs] + new_block + text[he:]

    # No H3 for this kind yet — insert a new H3 at the end of the band's
    # last hit (so Start, then Ende, then geplant order is roughly
    # preserved when authors follow it).
    last_he = band_hits[-1][1]
    new_block = f"{target_heading}\n{content.strip()}\n\n"
    return text[:last_he] + new_block + text[last_he:]


def write_evolution_section(
    path: Path,
    band: str,
    kind: str,
    content: str,
    mode: str = "auto",
) -> None:
    """Write a Start/Ende/geplant value into the right band of a tracker.

    Args:
        path: Tracker file path.
        band: Band id (``"B1"``, ``"B2"``, ...).
        kind: ``"start"``, ``"ende"``, or ``"geplant"``.
        content: Body text for the slot. Stripped before insertion.
        mode: Reserved for future use; currently always auto-detected
            from the existing structure (bullet vs h3).

    Behavior:
        - Replaces an existing keyed bullet or H3 body in place.
        - Preserves freeform bullets and other slots.
        - Creates the ``## Evolution per Band`` section if missing.
        - Appends a new band heading if the band id is not yet present.
    """
    if kind not in _KIND_LABEL:
        raise ValueError(f"kind must be one of {sorted(_KIND_LABEL)} — got {kind!r}")
    if mode not in {"auto", "bullet", "h3"}:
        raise ValueError(f"mode must be auto/bullet/h3 — got {mode!r}")

    text = path.read_text(encoding="utf-8")

    # Ensure ## Evolution per Band exists.
    bounds = _section_bounds(text, _RE_H2_EVOLUTION)
    if bounds is None:
        # Append a new section before any existing top-level section that
        # would normally come after Evolution (Beziehungen / Updates Log),
        # or at the end of the file.
        anchor: int | None = None
        for anchor_re in (_RE_H2_RELATIONSHIPS, _RE_H2_UPDATES_LOG):
            m = anchor_re.search(text)
            if m is not None:
                anchor = m.start()
                break
        new_section = f"## Evolution per Band\n\n### {band}\n" + _format_keyed_bullet(kind, content) + "\n\n"
        if anchor is None:
            sep = "" if text.endswith("\n") else "\n"
            path.write_text(text + sep + new_section, encoding="utf-8")
            return
        path.write_text(text[:anchor] + new_section + text[anchor:], encoding="utf-8")
        return

    body_start, body_end = bounds
    band_hits = _find_band_bounds(text, body_start, body_end, band)

    if not band_hits:
        # Append a new band block at the end of the Evolution section.
        new_block = f"### {band}\n{_format_keyed_bullet(kind, content)}\n\n"
        # Trim trailing whitespace from the section body before insert
        # so we don't end up with multiple blank lines.
        section_text = text[body_start:body_end].rstrip() + "\n\n"
        new_text = text[:body_start] + section_text + new_block + text[body_end:]
        path.write_text(new_text, encoding="utf-8")
        return

    # H3 shape detection: every band_hit's title matches the h3 pattern.
    if all(_is_h3_shape_title(title) for _, _, title in band_hits):
        new_text = _rewrite_h3_band(text, band_hits, kind, content)
        path.write_text(new_text, encoding="utf-8")
        return

    # Bullet shape — exactly one hit (the band heading).
    hs, he, title = band_hits[0]
    # Slice the band body — everything after the heading line, up to he.
    heading_end = text.find("\n", hs)
    if heading_end == -1 or heading_end >= he:
        heading_end = he
        body = ""
    else:
        heading_end += 1
        body = text[heading_end:he]

    planned = _is_band_planned(title)
    new_body = _rewrite_band_body_bullet_shape(body, kind, content, planned)

    new_text = text[:heading_end] + new_body + text[he:]
    path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Updates Log writer
# ---------------------------------------------------------------------------


_PLACEHOLDER_RE = re.compile(
    r"^\s*\(\s*(?:noch\s+keine\s+(?:eintraege|einträge|entries)|"
    r"no\s+entries(?:\s+yet)?|tbd|todo)\s*\)\s*$",
    re.IGNORECASE,
)


def append_updates_log_entry(
    path: Path,
    message: str,
    date: str | None = None,
) -> None:
    """Append ``- {date} — {message}`` to the ``## Updates Log`` section.

    Behavior:
        - Defaults ``date`` to today's UTC date in ISO format
          (``YYYY-MM-DD``).
        - Creates ``## Updates Log`` at the end of the file if missing.
        - Strips a placeholder line such as ``(noch keine Eintraege)``
          when adding the first real entry.
        - Skips writing when an identical entry already exists for the
          same date and message — keeps the skill idempotent on re-run.
    """
    if date is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
    new_line = f"- {date} — {message}"

    text = path.read_text(encoding="utf-8")
    bounds = _section_bounds(text, _RE_H2_UPDATES_LOG)

    if bounds is None:
        # No ## Updates Log section yet — append at the end of the file.
        sep = "" if text.endswith("\n") else "\n"
        path.write_text(
            text + sep + "\n## Updates Log\n\n" + new_line + "\n",
            encoding="utf-8",
        )
        return

    body_start, body_end = bounds
    body = text[body_start:body_end]

    # Idempotency check.
    if new_line in body:
        return

    # Strip placeholder if present.
    cleaned_lines: list[str] = []
    for line in body.splitlines():
        if _PLACEHOLDER_RE.match(line):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).rstrip("\n")

    new_body = cleaned + ("\n" if cleaned else "") + new_line + "\n"
    # Make sure the section body is separated from the heading by at
    # least one blank line.
    if not new_body.startswith("\n"):
        new_body = "\n" + new_body
    # Ensure trailing blank line before next H2 (for readability).
    if not new_body.endswith("\n\n") and body_end < len(text):
        new_body = new_body + "\n"

    path.write_text(text[:body_start] + new_body + text[body_end:], encoding="utf-8")
