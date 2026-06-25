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
4. Derive `book_slug` from the filename: `analysis-{book_slug}.md` → `{book_slug}`

Report what was found before making changes:

```
Author: {slug}
Analysis files found: {N}

  analysis-firelight.md          source_genres: light-supernatural, comedy-supernatural
  analysis-some-book.md          source_genres: (none found — will skip)
  analysis-other-book.md         genres: dark-fantasy  (legacy field)

Proceed? (yes/no)
```

## Step 3: Apply updates

For each file where `source_genres` or `genres` was found, call:

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

## Step 4: Report

```
migrate-source-genres complete: {slug}
────────────────────────────────────────
Files processed:     {N}
DB rows updated:     {total from all update_discovery_metadata responses}
Files skipped:       {N} (no source_genres / genres field)
────────────────────────────────────────
```

Remind the user: chapter-writer and author-check now apply the genre filter
automatically. No session restart needed.

## Notes

- `update_discovery_metadata` is idempotent — running twice sets the same value again
- Only `source_genres` is updated; `text`, `example`, `universal`, and other fields
  are untouched
- For the special case `universal: true` rows: these are not affected by genre filtering
  regardless of `source_genres` — they apply to all books always
