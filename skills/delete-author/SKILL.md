---
name: delete-author
description: |
  Safely delete an author profile and its writing discoveries, with a
  book-reference check and explicit confirmation.
  Use when: (1) User says "Autor löschen", "delete author", "Autorenprofil
  entfernen", "Autor entfernen", (2) A throwaway/test author or a
  mistakenly-created duplicate needs removing, (3) User wants to abandon an
  author profile.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<author-slug>"
---

# Delete Author Profile

## Purpose

Removing an author is rarer and higher-stakes than creating one: it deletes the
whole `~/.storyforge/authors/{slug}/` tree and every writing discovery the author
accumulated, and it can orphan any book whose `author` field still points at the
slug. This skill walks that safety check interactively instead of leaving it to a
bare `rm -rf` or an unguided tool call.

The actual removal is done by the `delete_author(slug, force=False)` MCP tool,
which validates the slug, refuses when books still reference the author (unless
`force=True`), clears the SQLite discoveries, and refreshes the cache. This skill
is the guided wrapper around it.

## Workflow

### Phase 1: Identify the author

1. Call MCP `list_authors()` and confirm the target slug actually exists. If the
   user named an author that isn't in the list, show the available slugs and ask
   which one they mean — never guess a slug.
2. Call MCP `get_author(slug)` and show a compact summary (name, primary genres,
   studied-works count, number of writing discoveries). This is the "here's what
   you're about to destroy" preview.

### Phase 2: Reference check (dry run)

Call `delete_author(slug)` **without** `force`. Two outcomes:

- **No references** → the tool deletes immediately and returns
  `{success, removed_discoveries, ...}`. Skip to Phase 4 and report.
- **Books still reference the author** → the tool returns
  `{error, referencing_books: [...]}` and deletes nothing. Continue to Phase 3.

> Do NOT pass `force=True` on this first call. The unforced call is the reference
> probe — its refusal is the information Phase 3 needs.

### Phase 3: Resolve references (only if blocked)

Show the user the exact list of `referencing_books` returned by the tool and
explain the consequence: force-deleting leaves each of those books with a
dangling `author` field (nothing else about the book is touched). Offer three
options via AskUserQuestion:

1. **Reassign first** — the user reassigns those books to another author before
   deleting (edit each book's `author` field via the book's README / the normal
   book tools), then re-run this skill. Safest.
2. **Force delete anyway** — proceed knowing the books will be orphaned (fine for
   throwaway test books, or when the books are also being deleted).
3. **Cancel** — abandon the deletion.

**Never** force-delete without the user explicitly choosing option 2 for these
specific books.

### Phase 4: Confirm and delete

- If Phase 2 already deleted (no references), there is nothing left to do —
  report the result.
- If the user chose **Force delete**, ask for one final explicit confirmation
  ("Delete author X and orphan N book(s)? yes/no"), then call
  `delete_author(slug, force=True)`.

### Phase 5: Report

Show the tool's result: what was deleted (`deleted_path`), how many discovery
rows were removed (`removed_discoveries`), and — for a forced delete — the
`referencing_books` that are now orphaned, so the user knows exactly what to fix
next. End with the result; no filler.

## Rules

- **The unforced call is the safety probe.** Always call `delete_author(slug)`
  without `force` first; only escalate to `force=True` after the user explicitly
  approves orphaning the specific books the probe reported.
- **Never invent a slug.** Resolve it against `list_authors()` output.
- **Preview before destroying.** Always show the `get_author()` summary so the
  user sees what they're removing.
- **State ops go through MCP.** Do not `rm -rf` the author directory or edit
  `authors.db` directly — the tool handles the directory, the DB rows, and the
  cache refresh atomically from the caller's perspective.
- **Deletion is the user's call.** Present the impact; the user decides. Cancel
  is always a valid outcome.
