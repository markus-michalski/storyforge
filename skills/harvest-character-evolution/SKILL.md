---
name: harvest-character-evolution
description: |
  Harvest end-of-book character state into the series-evolution trackers.
  Reads each recurring character's final state from the book-level files,
  proposes a `B{N} Ende` summary, and writes confirmed entries to
  `series/{slug}/characters/{tracker}.md` with an Updates Log entry.
  Use when: (1) User says "harvest evolution", "evolve characters",
  "harvest character evolution", "Charakter-Evolution ernten", "Tracker
  abgleichen", (2) Book is in `Final` / `Export Ready` / `Published`
  status AND the book is part of a series, (3) After running
  `/storyforge:harvest-author-rules` and before starting the next book.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug]"
---

# Harvest Character Evolution

End-of-book skill that walks every recurring series-tracker, reads the
book-level character end-state, proposes a `B{N} Ende` summary, and
writes it to the tracker after user confirmation. Companion to
`/storyforge:harvest-author-rules` (which promotes book findings to the
author profile). This skill promotes book character-state to the series
tracker so the next book can bootstrap from a verified end-state.

This is **D-1 of Epic #195**. D-2 (`bootstrap-book-from-series`) and
D-3 (brief-source extension) consume what this skill writes.

## When to run

- **Status gate**: book must be `Final`, `Export Ready`, or `Published`.
  Earlier than that, the end-state is still drifting. If `Editing` /
  `Proofread` — warn but offer to run anyway. If `Drafting` / `Revision`
  — block.
- **Series gate**: book must declare `series:` in its README
  frontmatter. If absent, this skill has nothing to do.
- **Sequencing**: ideally after `/storyforge:harvest-author-rules` and
  before starting the next book in the series.

## Step 1: Resolve book + series + band

1. If a book slug was passed as argument, use it. Otherwise check
   `mcp__storyforge-mcp__get_session()` for `book_slug`.
2. Load the book via `mcp__storyforge-mcp__get_book_full(book_slug)`.
   - Validate `book.status` is one of `Final` / `Export Ready` / `Published`.
   - Read `book.series` (must be non-empty) and `book.series_number`
     (must be 1+). Build the band id: `band = f"B{book.series_number}"`.
   - Read `book.book_category` (`fiction` or `memoir`).
3. Status gate (use AskUserQuestion when warning):
   - `Final` / `Export Ready` / `Published` → proceed silently
   - `Editing` / `Proofread` → warn, offer **Run anyway** vs **Cancel**
   - `Drafting` / `Revision` / earlier → block with explanation
4. If `series` is empty: report "Book is not part of a series — nothing
   to harvest" and exit cleanly.

## Step 2: List trackers for this band

```python
mcp__storyforge-mcp__list_series_trackers_for_book(
    series_slug=book.series,
    band=band,  # e.g. "B1"
)
```

Returns `{"trackers": [{tracker_slug, book_slug, name, role, recurs_in,
has_existing_ende, existing_ende, path}, ...]}`.

If `trackers == []`: report "No recurring trackers for {band} in
{series_slug} — nothing to harvest" and exit.

Show summary:

```
Harvest plan for {book_slug} → series {series_slug} ({band}):

  {n} recurring trackers found
    {n_with_existing} already have B{N} Ende content (will diff before write)
    {n_empty} need first-time harvest

I'll walk you through them one at a time.
```

## Step 3: Walk each tracker

For each tracker (1-indexed):

### 3a. Read book-level character state

```python
mcp__storyforge-mcp__read_character_for_harvest(
    book_slug=book.slug,
    character_slug=tracker.book_slug,  # resolved via #194 mapping
    book_category=book.book_category,
)
```

Returns `{name, role, description, snapshot, relationships_text}`. The
snapshot contains the POV-state fields written by
`update_character_snapshot` at chapter close: `current_inventory`,
`current_clothing`, `current_injuries`, `altered_states`,
`environmental_limiters`, `as_of_chapter`.

If the response carries `error` (character not found): show a warning
and offer **Skip this tracker** vs **Provide manual content**.

### 3b. Synthesize the B{N} Ende summary

Compose 2–4 sentences from the book-level data. Lead with state
changes that survive across books (relationship arcs, status shifts,
trauma, irreversible events). Avoid book-specific tactical detail
(specific items, single-scene injuries) unless they carry forward.

**Source-discipline rule (Rule #14):** invent nothing. Every claim must
trace back to the snapshot fields, the relationships text, or to facts
the user states explicitly during this skill run. If a meaningful Ende
summary cannot be drawn from the source, skip the tracker rather than
fabricate.

Voice: match the existing tracker's tone (compact, present tense,
declarative). Look at the band's `**Start:**` bullet (via `parse`-ed
sections shown to you in 3c) for register guidance.

### 3c. Show the diff

```
Tracker {n}/{total} — {tracker_slug} ({name}, {role})

  Book file: projects/{book_slug}/{characters|people}/{book_slug}.md
  Snapshot as of: {snapshot.as_of_chapter or "—"}
  Recurs in: {recurs_in}

  Existing {band} Ende:
    {existing_ende or "(none)"}

  Proposed {band} Ende:
    {proposed_summary}

  Source signals used:
    - inventory: {snapshot.current_inventory[:3]}{"..." if more}
    - clothing: {...}
    - injuries: {...}
    - states: {snapshot.altered_states}
    - relationships: {first 2 bullets from relationships_text}
```

Use AskUserQuestion with these options:

- **Accept proposed** — write the proposed summary as-is
- **Edit before writing** — collect a refined version from user (free text)
- **Skip this tracker** — don't write, don't log
- **Keep existing** — preserve the hand-edited Ende, log a "kept-as-is" entry

### 3d. Write on accept / edit / keep

For **Accept proposed** or **Edit before writing**:

```python
mcp__storyforge-mcp__write_series_evolution_section(
    series_slug=book.series,
    tracker_slug=tracker.tracker_slug,
    band=band,
    kind="ende",
    content=final_text,
    log_message=f"Harvested from {band} final state",
)
```

For **Keep existing**:

```python
mcp__storyforge-mcp__write_series_evolution_section(
    series_slug=book.series,
    tracker_slug=tracker.tracker_slug,
    band=band,
    kind="ende",
    content=tracker.existing_ende,  # round-trip the existing value
    log_message=f"{band} Ende reviewed at harvest — kept hand-edited content",
)
```

For **Skip**: do nothing.

## Step 4: Final summary

After the walkthrough:

```
Harvest complete for {book_slug} ({band}):

  Total trackers: {total}
    Accepted proposed:  {n_accepted}
    Edited then written: {n_edited}
    Kept existing:       {n_kept}
    Skipped:             {n_skipped}

  Updated trackers:
    - {series_slug}/characters/{tracker_slug}.md
    - ...

Next steps:
  - Review the updated trackers visually
  - When ready, /storyforge:bootstrap-book-from-series {book_slug} {next_book_slug}
    to scaffold the next book's characters from {band+1} planned state
```

## Rules

- **Source-discipline (Rule #14)**: never invent state that isn't in the
  source. If the snapshot is empty AND relationships are empty, propose
  "(no harvestable end-state — manual entry required)" and route the
  user to **Edit before writing** or **Skip**.
- **No silent overwrites**: every existing Ende value is shown to the
  user before any write. The "Keep existing" path round-trips the
  current text so the Updates Log still records the review event.
- **One tracker at a time**: no batch mode. Authors need to see each
  diff to catch drift between draft and final state.
- **Memoir books**: `book_category=memoir` swaps `characters/` →
  `people/` automatically via the MCP read tool. Person consent
  obligations don't apply at series-tracker scope (the tracker is
  internal author tooling, not published content), but if a person's
  consent_status is `refused` you should skip them — they should not
  be appearing in series-evolution material.

## Out of scope

- **B{N} Start** writes — Start is set at planning time, not harvested
  from book end-state. The skill ignores the Start slot.
- **Cross-band drift detection** — comparing what the tracker had in
  `B{N} (geplant)` vs. what the book actually delivered. Save for a
  follow-up.
- **Auto-harvest on status transition** — manual trigger is intentional
  per the epic spec; authors should review before persisting.

## References

- Epic: #195 (Series-Level Character Evolution Tracking)
- Sub-issue: #200 (D-1 Harvest)
- Prerequisite: #194 (book_slug resolver) — merged
- Companion skills: `/storyforge:harvest-author-rules`,
  `/storyforge:bootstrap-book-from-series` (D-2, future)
