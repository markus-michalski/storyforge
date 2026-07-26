---
name: migrate-source-genres
description: |
  Backfill source_genres on existing author_discoveries DB rows by reading the
  source_genres (or legacy genres) field from studied-works analysis file frontmatter.
  Use when: (1) User says "migrate source genres", "source_genres backfill",
  "/storyforge:migrate-source-genres", (2) Writing Discoveries in the DB have no
  source_genres set because they were created before Phase 5 (#283),
  (3) chapter-writer or author-check genre filter is not working as expected.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[author-slug]"
---

# migrate-source-genres

Backfill `source_genres` on author_discoveries DB rows that were written before
Phase 5 (Issue #283) added the `source_genres:` frontmatter field to analysis files.

## When to use

- You ran `study-author` before Phase 5 and the `genres=` parameter was not passed
  to `write_author_discovery`
- `chapter-writer` Audit 4.5 genre filter skips all style_principles (no genres set)
- `author-check` genre filter finds nothing to check

## Step 1: Identify author

If no author slug was passed as argument, show list via MCP `list_authors()` and
ask the user which author to process.

## Step 2: Scan analysis files

List all files in `~/.storyforge/authors/{slug}/studied-works/analysis-*.md`.

For each file:
1. Read the first ~30 lines (frontmatter section only)
2. Extract `source_genres:` — preferred field (set by study-author Phase 1 post-#283)
3. If `source_genres:` is absent, fall back to `genres:` field (legacy)
4. Strip surrounding quotes and whitespace from the extracted value (study-author writes
   `source_genres: "dark-fantasy, lgbtq"` with quotes — see `study-author/SKILL.md`).
   Split on commas and trim each slug. The value passed to `update_discovery_metadata`
   must be a bare comma-separated slug list with no quote characters — a literal quote
   in the DB value breaks genre-overlap matching for every consumer (chapter-writer
   Audit 4.5, author-check).
5. Validate each slug against the genre registry via MCP `get_genre(slug)`. For any
   slug not found in the registry, mark it `(unknown genre — will not filter)` in the
   preview below instead of silently writing it. An unrecognized slug (typo, free
   text, title-cased name) can turn a previously-universal discovery (empty
   `source_genres` → always applied) into one that overlaps no book's genres and is
   permanently filtered out everywhere — the opposite of this skill's purpose.
6. Derive `book_slug` from the filename: `analysis-{book_slug}.md` → `{book_slug}`

Report what was found before making changes:

```
Author: {slug}
Analysis files found: {N}

  analysis-firelight.md          source_genres: light-supernatural, comedy-supernatural
  analysis-some-book.md          source_genres: (none found — will skip)
  analysis-other-book.md         genres: dark-fantasy  (legacy field)
  analysis-typo-book.md          source_genres: dark-fantsy  (unknown genre — will not filter)

Proceed? (yes/no)
```

If `Analysis files found: 0`, or every file found lacks a usable `source_genres`/
`genres` value, skip the `Proceed?` question — there is nothing to confirm. Report the
empty result per the template in Step 4 (zero counts, abort reason "no files" or "no
usable genre field") and stop; do not continue to Step 3.

Stop here and wait for the user's reply. Do not call any write tool, and do not call
`update_discovery_metadata` in this same turn, before an explicit affirmative answer
to `Proceed?` is received.

## Step 3: Apply updates

Only run this step if the user answered "yes" to the `Proceed?` prompt in Step 2. If
they answered "no" (or anything else that isn't an affirmative), stop here — do not
call `update_discovery_metadata` for any file, and report per the Step 4 template with
zero counts and abort reason "user declined".

For each file where a validated `source_genres` or `genres` was found, call:

```
update_discovery_metadata(
  author_slug=<slug>,
  book_slug=<derived-slug>,
  source_genres=<comma-separated genres>
)
```

This sets `source_genres` on ALL discovery rows for that `book_slug` in one SQL UPDATE.
It does not touch rows from other books.

Files with no genre field are skipped (not updated).

If a call returns `{"error": ...}` instead of `{"updated": N}` (e.g. the author profile
could not be resolved), stop the loop immediately — do not process remaining files.
Report using the Step 4 template with the counts accumulated so far, and add an explicit
line naming which files were already applied before the error and which files were never
attempted.

## Step 4: Report

Use this template for every outcome — success, the Step 2 zero-result abort, and the
Step 3 user-declined or mid-loop-error abort. The Step 2 zero-result and Step 3
user-declined aborts have `0` for "DB rows updated" and "Files processed" (nothing
was attempted); the mid-loop-error abort reports whatever partial counts were
accumulated before the error. Add the `Aborted:` line only when the run did not reach
a normal completion — omit it entirely on success.

```
migrate-source-genres complete: {slug}
────────────────────────────────────────
Files processed:     {N}
DB rows updated:     {total from all update_discovery_metadata responses}
Files skipped:       {N} (no source_genres / genres field)
Aborted:             {reason, e.g. "no analysis files found" / "no usable genre field" /
                       "user declined at Proceed?" / "update_discovery_metadata error after
                       {N} files — remaining files not attempted"}
────────────────────────────────────────
```

On a successful (non-aborted) run, remind the user: chapter-writer and author-check
now apply the genre filter automatically. No session restart needed.

## Notes

- `update_discovery_metadata` is idempotent — running twice sets the same value again
- Only `source_genres` is updated; `text`, `example`, `universal`, and other fields
  are untouched
- For the special case `universal: true` rows: these are not affected by genre filtering
  regardless of `source_genres` — they apply to all books always
