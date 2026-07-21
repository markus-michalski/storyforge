---
name: bootstrap-book-from-series
description: |
  Bootstrap a new book's recurring character files from the prior book
  in the series. Reads each tracker's `B{prev} Ende` (what
  /storyforge:harvest-character-evolution wrote) and `B{new} (geplant)`
  (what /storyforge:series-planner wrote), synthesizes a starting
  snapshot for the new book, walks char-by-char with the author for
  confirmation. Use when: (1) User says "bootstrap from series",
  "bootstrap book", "Charaktere aus Serie initialisieren",
  (2) User starts a B2/B3 of a multi-book series and wants smart state
  migration (vs. the dumb #196 auto-copy that runs at new-book time).
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<prev-book-slug> <new-book-slug>"
---

# Bootstrap Book From Series

Start-of-book skill. The opposite-end companion to
`/storyforge:harvest-character-evolution`: that skill takes book
end-state up into the series-tracker; this skill takes series-tracker
plan-state down into the new book's character files.

This is **D-2 of Epic #195**. It builds on:

- **#194** — `book_slug:` resolver bridges tracker slugs to book file slugs
- **#196** — dumb-copy at `/storyforge:new-book` time
  (already populates `new_book/characters/` with prior-book copies)
- **D-1 (#200)** — harvest already wrote `B{prev} Ende` content

## When to run

- After `/storyforge:new-book moonrise --series=blood-and-binary --copy-recurring-from=firelight` has scaffolded the new book and copied recurring char files (#196).
- After `/storyforge:harvest-character-evolution firelight` has populated the series-trackers' `B{prev} Ende` sections (D-1 of #195).
- Before the author starts writing chapters in the new book — character snapshots need to reflect B2-start state, not B1-end state.

If `/storyforge:new-book` has not run yet for the new book, this skill cannot proceed (no destination). If `/storyforge:harvest-character-evolution` has not run, the `B{prev} Ende` content is whatever the author hand-edited (may be incomplete).

## Step 1: Resolve books + bands

1. Read both arguments: `prev_book_slug` and `new_book_slug` (positional).
2. Load both via `mcp__storyforge-mcp__get_book_full(slug)`.
3. Validate:
   - `prev_book.status` must be `Final` / `Export Ready` / `Published`. Else warn (AskUserQuestion: **Run anyway** vs **Cancel**).
   - `new_book` must exist (already scaffolded).
   - `prev_book.series == new_book.series` (else error: not in same series).
4. Determine bands:
   - `prev_band = "B{prev_book.series_number}"`
   - `new_band = "B{new_book.series_number}"`
   - Confirm `new_band > prev_band`. If it isn't, this is very likely a reversed
     argument order (author passed `<new-book-slug> <prev-book-slug>` instead of
     `<prev-book-slug> <new-book-slug>`) — say so explicitly and use
     AskUserQuestion to confirm the intended prev/new order rather than erroring
     out generically or silently proceeding.
5. Determine `book_category` (must match between prev and new — error if not).

## Step 2: List recurring trackers

```python
mcp__storyforge-mcp__list_series_trackers_for_book(
    series_slug=prev_book.series,
    band=new_band,
)
```

Returns trackers that recur in `new_band`. Show summary:

```
Bootstrap plan for {new_book_slug} ({new_band}):

  {n} recurring trackers found
    {n_with_prior} have a source file in {prev_book_slug} (will mutate)
    {n_new} are first-appearance in {new_band} (skip — author creates)

I'll walk you through them one at a time.
```

If list is empty: "No recurring trackers for {new_band}" and exit.

## Step 3: Walk each tracker

For each tracker (1-indexed):

### 3a. Skip first-appearance characters

If the character first appears in `new_band` (no prior bands in `recurs_in`), they have no source file to bootstrap from. Surface as:

```
Tracker {n}/{total} — {tracker_slug} (first appearance in {new_band})

  This character has no source in any prior book. Create them manually
  via /storyforge:character-creator before drafting chapters that
  feature them.

  [Skip and continue]
```

Do not call `read_tracker_for_bootstrap` for these — there is no prior-book
source to read, so Step 3b does not apply to first-appearance characters.

### 3b. Read tracker bootstrap data

```python
mcp__storyforge-mcp__read_tracker_for_bootstrap(
    series_slug=prev_book.series,
    tracker_slug=tracker.tracker_slug,
    prev_band=prev_band,
    new_band=new_band,
    prev_book_slug=prev_book_slug,
)
```

Returns: `{tracker_slug, book_slug, name, role, prev_band: {start, ende, geplant, title}, new_band: {start, ende, geplant, title}, prev_book_snapshot}`.

### 3c. Synthesize starting snapshot

Compose new starting-state values for the six snapshot fields:

| Field | Default for B{N+1} start | When to override |
|-------|-------------------------|------------------|
| `current_inventory` | carried forward from `prev_book_snapshot.current_inventory` if it has entries, else `[]` | Items the tracker text (`ende`/`geplant`) says are gained, lost, or destroyed override the carried-forward value |
| `current_clothing` | carried forward from `prev_book_snapshot.current_clothing` if it has entries, else `[]` | Symbolic outfits noted in `geplant` (mourning black, royal regalia) override |
| `current_injuries` | carried forward from `prev_book_snapshot.current_injuries` if it has entries, else `[]` (default heal) | Permanent scars / lingering wounds noted in `ende` or `geplant` override; a source explicitly saying an injury healed clears it |
| `altered_states` | `[]` | New psychological state from B{prev} Ende (grief, trauma, confidence shift) |
| `environmental_limiters` | `[]` | New setting context from `geplant` (now in mountains, no signal, etc.) |
| `as_of_chapter` | `""` | Empty — new book hasn't started |

**Source-discipline rule (Rule #14):** the proposed snapshot values must trace to either (a) the `prev_band.ende` text, (b) the `new_band.geplant` text, or (c) the `prev_book_snapshot` carry-overs. Don't invent items, scars, or states not grounded in those sources. **`prev_book_snapshot` carry-overs are a DEFAULT, not merely a fallback** — a character keeps their end-of-book-N inventory/clothing/injuries into book N+1 unless `ende` or `geplant` explicitly says otherwise (gained, lost, destroyed, healed). Don't silently reset a carried field to `[]` just because `ende`/`geplant` didn't repeat it.

### 3d. Show diff and prompt

```
Tracker {n}/{total} — {tracker_slug} ({name}, {role})

  Source: projects/{prev_book_slug}/{characters|people}/{book_slug}.md
  Dest:   projects/{new_book_slug}/{characters|people}/{book_slug}.md
          [{exists | missing — will copy from prev}]

  {prev_band} Ende (from tracker):
    {prev_band.ende or "(empty)"}

  {new_band} (geplant) (from tracker):
    {new_band.geplant or "(empty)"}

  {prev_book_snapshot.as_of_chapter}: chapter snapshot at end of {prev_band}:
    inventory:   {prev_book_snapshot.current_inventory}
    clothing:    {prev_book_snapshot.current_clothing}
    injuries:    {prev_book_snapshot.current_injuries}
    states:      {prev_book_snapshot.altered_states}

  Proposed {new_band} start snapshot:
    inventory:   {proposed.current_inventory}
    clothing:    {proposed.current_clothing}
    injuries:    {proposed.current_injuries}
    states:      {proposed.altered_states}
    limiters:    {proposed.environmental_limiters}
    as_of:       {proposed.as_of_chapter or "(empty)"}
```

Use AskUserQuestion:

- **Accept proposed** — write the proposed snapshot
- **Edit before writing** — collect refined values from user
- **Skip this tracker** — leave the new book file untouched (file may still exist via #196 dumb-copy)

### 3e. Write on accept / edit

```python
mcp__storyforge-mcp__bootstrap_character_for_new_book(
    series_slug=prev_book.series,
    tracker_slug=tracker.tracker_slug,
    prev_book_slug=prev_book_slug,
    new_book_slug=new_book_slug,
    prev_band=prev_band,
    snapshot_json=json.dumps(final_snapshot),
    book_category=book_category,
)
```

The MCP tool atomically:

1. Copies the prev book character file to the new book if not already there
2. Applies the snapshot to the new book file's frontmatter
3. Adds `series_evolution_imported_from: {prev_band}` marker
4. Appends a dated entry to the series-tracker's Updates Log

## Step 4: Final summary

```
Bootstrap complete for {new_book_slug} ({new_band}):

  Total trackers: {total}
    Bootstrapped:           {n_accepted}
    Edited and bootstrapped: {n_edited}
    Skipped:                 {n_skipped}
    First-appearance noted:  {n_new}

  Updated character files:
    - {new_book_slug}/characters/{book_slug}.md
    - ...

  First-appearance characters to create manually:
    - {tracker_slug} (recurs_in: {recurs_in})
    - ...

Next steps:
  - Review each new character file's frontmatter snapshot
  - Run /storyforge:character-creator for first-appearance characters
  - Then start writing: /storyforge:plot-architect or /storyforge:rolling-planner
```

## Rules

- **Source-discipline (Rule #14)**: never invent state that isn't in the source. Proposed snapshots trace to `prev_band.ende`, `new_band.geplant`, or `prev_book_snapshot`.
- **No silent overwrites**: every accepted bootstrap writes a marker `series_evolution_imported_from: {prev_band}`. Re-running the skill replaces the marker (overwrites snapshot) — but each write goes through the per-char prompt.
- **One tracker at a time**: no batch mode. Holds even if the author explicitly
  asks to apply the same choice (e.g. "accept" or "skip") to all remaining
  trackers — explain that each tracker still gets its own Step 3d diff-and-prompt
  rather than silently batching the rest.
- **First-appearance characters are skipped**: bootstrap can't help with characters that have no prior source. The summary surfaces them so the author runs `/storyforge:character-creator` next.
- **Memoir books**: `book_category=memoir` swaps `characters/` → `people/` automatically.

## Out of scope

- **B{N} Start writes back to the tracker** — D-1 writes Ende; D-2 writes the new book file. The tracker's `B{new} Start` slot stays as the series-planner's planning text and is not modified by this skill.
- **Three-way conflict resolution** when the author has hand-edited both the tracker AND the new book file. The skill shows both and lets the user choose.
- **Auto-trigger on new-book** — the skill is intentionally manual so the author runs it after harvest is complete, not at scaffold time.

## References

- Epic: #195
- Sub-issue: #203 (D-2 Bootstrap)
- Prerequisites: ✅ #194 (resolver), ✅ #200 (D-1 harvest), ✅ #196 (dumb-copy at new-book)
- Companion: `/storyforge:harvest-character-evolution`
- Future: D-3 brief-source extension consumes the `series_evolution_imported_from` marker for chapter-writing brief
