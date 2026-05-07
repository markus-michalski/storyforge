---
name: "{{name}}"
slug: "{{tracker-slug}}"
# Optional: explicit book-level slug if it differs from the tracker slug.
# Bridges this series-tracker to the book-level character file
# `projects/{book}/characters/{book_slug}.md` for the harvest, bootstrap,
# and brief-source tooling (Issue #195). When absent, the tracker slug
# IS the book-level slug — the zero-config default for the common case
# (e.g. tracker `kael` ↔ book file `kael.md`).
# Set this field when the series-planner picked a role/title-prefixed
# slug (e.g. `king-caelan`) for a character whose book-level file uses
# the bare name (e.g. `caelan.md`).
# book_slug: "{{book-level-slug}}"
role: "{{role}}"
species: "{{species}}"
status: "Profile"
recurs_in: ["B1"]
# Tracker depth. ``thin`` = essence + per-book Evolution sections only,
# full character profile lives in the book-level file. ``full`` = the
# tracker IS the source of truth (rare; only when a character spans
# books equally without a "home" book).
tracker_type: "thin"
---

# {{name}} — Series Evolution Tracker

> Volles Profil pro Buch in [{{book-slug}}/characters/{{book-level-slug}}.md](../../projects/{{book-slug}}/characters/{{book-level-slug}}.md).

## Snapshot

*One-paragraph essence at series scope. What is constant about this character across all books? Capture identity, role, key relationship anchors. Not plot, not arc-per-book — the through-line.*

## Evolution per Band

### B1 Start
*Where the character begins in Book 1. Initial state, defining wound or driver, current situation. Filled at planning time.*

### B1 Ende
*Where the character ends in Book 1. Filled by the harvest tool at end-of-book from book-level frontmatter snapshot fields and relationships.*

### B2 (geplant)
*Planned arc for Book 2. What changes? What carries forward? What new external pressure forces growth? Filled at planning time.*

<!-- Repeat per planned book: B2 Ende (post-harvest), B3 (geplant), etc. -->

## Beziehungen über die Bände

*Cross-book relationship arcs. Capture how each significant pairing evolves across the series, not just within one book. Format:*

- **{{Other Character}}**: {{B1 dynamic}} → {{B2 shift}} → {{B3 resolution}}

## Updates Log

*Append-only chronological log of changes to this tracker. Each entry: date + what changed + source (manual edit / harvest tool / bootstrap tool).*

- {{YYYY-MM-DD}} — Tracker scaffolded by series-planner
