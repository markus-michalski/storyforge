---
name: backfill-promises
description: |
  Backfill the ## Promises section in already-drafted chapters by
  extracting setup-elements via LLM pass over each draft.
  Use when: (1) User says "backfill promises", "promises nachfüllen",
  "/storyforge:backfill-promises", (2) Book was drafted before #150
  shipped and has no Promises sections yet, (3) Author imported a
  finished book and wants chekhov_gun detection to work.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug] [--force]"
---

# Backfill Promises

Walks every drafted chapter in a book and identifies setup-elements
that should land in the chapter's `## Promises` section. Chapters
already carrying a populated section are skipped unless `--force` is
passed.

This is the one-time-per-book bridge for plot-logic checking on
books drafted before issue #150 shipped. Going forward,
`chapter-writer` populates promises automatically at the
Draft → Review transition.

## What Counts as a Promise

A **promise** is a setup-element that the chapter prominently introduces
and that creates a reader expectation of payoff:

- A locked drawer, hidden room, sealed letter, or other physical object
  that demands opening or reading.
- A character's claim about a skill, history, or capability that the
  story sets up to be tested ("I can shoot a rifle"; "I've never lied").
- A cryptic warning, prophecy, threat, or deadline that the story has
  not yet honored.
- An introduced relationship dynamic that the chapter foregrounds as
  unstable or unresolved (a feud, a debt, a secret between two
  characters).
- A clue, hint, or piece of evidence that the chapter calls attention
  to but does not resolve.

**Not a promise:**

- Atmospheric texture, world-building, voice work that doesn't shape
  reader expectation of *what comes next*.
- Routine scene description.
- A character trait or backstory detail that's painted as
  characterization, not as a setup for later events.
- Reactions to past events (those resolve, they don't set up).

When in doubt, ask: *would a careful reader feel cheated if this
element never returned?* If yes, it's a promise. If no, it's texture.

## Step 1: Resolve the Book

If the user passed a book slug as the first argument, use it directly.
Otherwise:

1. Check the active session via MCP `get_session()` — if there's a
   current book, propose it.
2. If no session book or user wants a different one, use
   AskUserQuestion with the output of `list_books()` (active books
   only).

Verify via `find_book(slug)` that the book exists. If not, exit with
a clear error.

## Step 2: Parse Arguments

- `--force` — re-extract promises even if a chapter already has a
  populated `## Promises` section. Existing entries are merged via
  `register_chapter_promises` semantics (matching description+target
  is preserved; new ones append). Default is to skip populated
  chapters.

When `--force` is set, `get_chapter_promises()` alone isn't a
reliable signal of prior manual edits — the underlying parser keys
only on pipe-table rows and ignores surrounding prose, so a
hand-edited section (rewritten table, renamed/added columns, freeform
notes instead of a table) can come back empty or partial through that
call, silently masking the edit. Before entering the Step 4 extraction
loop, `Read` the `README.md` of every chapter Step 3 will process and
check its raw `## Promises` section:

- **No `## Promises` section at all** — this chapter hasn't been
  backfilled yet. Not a hand-edit; proceed normally.
- **Section present, table intact** (the standard blurb plus either
  the `_No promises this chapter._` placeholder or a
  `| Promise | Target | Status |` table) — untouched; proceed.
- **Section present but deviating** — table columns added or
  renamed, table replaced with freeform content, or otherwise
  reshaped — this has been hand-edited.

If the last case fires on any in-scope chapter, confirm with the user
before proceeding, rather than force-overwriting silently. If it
fires on none, proceed without an extra confirmation.

## Step 3: Build the Chapter List

Call MCP `list_chapters(book_slug)` and filter to chapters with
status in `{"Draft", "Revision", "review", "Polished", "Final"}`.

Skip chapters at `Outline` status — promises live in prose, not
outlines.

If the result is empty:

> "No drafted chapters yet. Backfill nothing to do."

Exit.

## Step 4: Per-Chapter Extraction Loop

For each chapter in the filtered list, in order:

### 4.1 Pre-check existing promises

Call MCP `get_chapter_promises(book_slug, chapter_slug)`.

- If `promises` is non-empty AND `--force` is not set → skip with
  message: `[Ch NN] Already populated (M promises). Skipping.`
- Otherwise proceed.

### 4.2 Read the draft

Read directly from
`{content_root}/projects/{book_slug}/chapters/{chapter_slug}/draft.md`.

If the file is missing or empty → skip with message:
`[Ch NN] No draft.md, skipping.`

Also read the chapter's `README.md` in the same directory. Step 4.3's
target-chapter rule depends on its outline text — draft.md alone never
tells you which later chapter a setup-element pays off in.

### 4.3 Identify promises

Walk the draft once. List every setup-element that meets the
"What Counts as a Promise" criteria above. For each:

- **Description:** A short, concrete phrase (8–14 words) that names
  the element specifically enough that a checker can scan later
  chapters for it. Bad: "a dramatic moment". Good: "the locked drawer
  in Marcus's office".
- **Target chapter:** If the chapter README's outline mentions the
  payoff chapter explicitly, use its slug (e.g. `14-the-letter`). If
  the chapter outline is silent, use `unfired` — the checker will
  flag it for either payoff or retirement.
- **Status:** Always `active` for backfill. The author can later
  set `satisfied` or `retired` manually or via the chapter-reviewer.

If the chapter places **no** promises, that's a valid result. Pass
an empty list to `register_chapter_promises` — this writes a
`_No promises this chapter._` placeholder so the next pass knows
the chapter has been processed.

### 4.4 Persist

Call MCP:

```
register_chapter_promises(
  book_slug=...,
  chapter_slug=...,
  promises=[
    {"description": "...", "target": "...", "status": "active"},
    ...
  ]
)
```

Output to user:
`[Ch NN] {N} promise(s) registered. (added: {a}, updated: {u}, unchanged: {un})`

Append a trailing note to that same line whenever one of these applies
— neither case is complete without it, since this per-chapter line is
the only place the user actually sees the result for this chapter:

- Zero promises (the Step 4.3 empty-list case): append
  ` — no promises this chapter, placeholder written.`
- Cap triggered (Step 4.5's eight-promise cap): append
  ` — {K} candidates found, kept the strongest 8.`

### 4.5 Discipline

- Cap at **eight promises per chapter**. More than that and the
  signal is drowned in noise. If the chapter genuinely has more, list
  only the strongest eight and say so in the Step 4.4 output line
  (the cap-triggered suffix above) — the count of dropped candidates
  must reach the user, not just live in your own reasoning.
- Avoid restating earlier-chapter promises. Each promise should
  originate in *this* chapter.
- Phrase promises as objects/claims/dynamics, not as plot points.
  "The locked drawer" — yes. "Marcus discovers the truth" — no, that's
  a payoff statement.

## Step 5: Report

After the loop completes, output a summary:

```
Backfill complete: {book-slug}
- Chapters scanned: {N}
- Chapters skipped (populated): {M}
- Promises registered: {total}
- Chapters with placeholder (no promises): {p}
```

If any chapters had errors (missing draft, file read failure),
list them at the end.

Tell the user that `/storyforge:manuscript-checker` will now pick up
chekhov_gun findings when the book is next scanned, and that
`/storyforge:chapter-reviewer` will surface plot-logic findings on
the next chapter close.

## Cost Note

This skill makes one LLM pass per drafted chapter. For a 30-chapter
novel that's 30 reads of full prose (~45k words total), plus one small
README read per chapter for the outline (Step 4.2) and, under
`--force`, one more per in-scope chapter for the manual-edit check
(Step 2). The pass is deterministic enough for Sonnet — no Opus
needed.

## Related

- `register_chapter_promises` MCP tool — the persistence path.
- `get_chapter_promises` MCP tool — the read-only inspection path.
- `chapter-writer` Step 7 — the forward-going extractor for new
  chapters (no backfill needed).
- `reference/craft/plot-logic.md` — full taxonomy of plot-logic
  failures and the promise mechanism's role.
