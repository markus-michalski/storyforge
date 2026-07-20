---
name: start-session
description: |
  Initialize a StoryForge session: verify setup, load context, report status.
  Use when: (1) User types /start, (2) User says "start session", "Session starten".
model: claude-sonnet-4-6
user-invocable: true
---

# Start Session

## Workflow

1. **Verify setup**
   - Check `~/.storyforge/venv/` exists
   - Check `~/.storyforge/config.yaml` exists
   - If missing: suggest `/storyforge:setup` and STOP

2. **Load session context** via MCP `get_session()`
   - Returns `last_book` (a **book slug**, not a title), `last_chapter` (whatever string a skill last wrote there — usually a chapter slug, never a bare number, and currently absent in practice since no other skill in the pipeline calls `update_session(last_chapter=...)` yet), and `last_phase` (free-text, also rarely set). Any of the three may be missing entirely — the DB drops empty fields from the response rather than returning them as `null`.
   - If `get_session()` reports no active book, note that explicitly — do NOT infer one from `list_books()` (e.g. by picking the most recently modified book)
   - After step 3 has run, cross-check the active book's slug against the `list_books()` results. If it's no longer present (book deleted or renamed since the session was last saved), treat this as **resolved: no active book** for steps 5-6 (same as `get_session()` never having returned one) and say so explicitly — never suggest `/storyforge:resume [stale-slug]` for a book that no longer exists. Steps 5 and 6 below always refer to this *resolved* active-book state, not the raw `get_session()` return.

3. **List projects** via MCP `list_books()`
   - Show all books with status and word count

4. **List authors** via MCP `list_authors()`
   - Show all author profiles

5. **Report status**
   ```
   StoryForge Session
   ==================
   Active Book: [title] (status)
   Authors: [count] profiles
   Books: [count] projects
   
   - [book title] — [status] — [word count] words
   - (one line per book from step 3's list_books() result)
   
   Last worked on: [book title] — [last_chapter] (Phase: [last_phase])
   ```
   - The per-book list is required, not optional — it's how step 3's "show all books with status and word count" actually surfaces in the final report; the `Books: [count] projects` line above it is only the aggregate count, not a substitute for it.
   - `[title]` and `(status)` in the `Active Book` line come from matching `get_session()`'s `last_book` **slug** against the `list_books()` results from step 3 — never print the raw slug in place of the title.
   - The `Last worked on` line degrades gracefully field-by-field: omit the whole line if `last_book` is absent (see below). If `last_book` is present but `last_chapter` and/or `last_phase` are absent (the common case today — see step 2), drop just those segments rather than printing an empty placeholder (e.g. `Last worked on: [book title]` alone is correct when neither is set).
   - If step 2 resolved no active book (whether `get_session()` returned none, or it returned a stale slug not found in `list_books()`): print `Active Book: None yet` and omit the `Last worked on` line entirely rather than leaving a placeholder or fabricating a book.

6. **Suggest action** — Based on session state, checked in this order (first match wins):
   - If no authors: "Create your first author profile with `/storyforge:create-author`"
   - If no books: "Start a new book with `/storyforge:new-book`"
   - If step 2 resolved an active book: "Continue with `/storyforge:resume [slug]`"
   - Otherwise (authors and books both exist, but no active book is set): "What would you like to work on?"
