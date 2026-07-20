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
   - Show last active book, chapter, phase
   - If `get_session()` reports no active book, note that explicitly — do NOT infer one from `list_books()` (e.g. by picking the most recently modified book)

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
   
   Last worked on: [book] — Chapter [N]
   ```
   - The per-book list is required, not optional — it's how step 3's "show all books with status and word count" actually surfaces in the final report; the `Books: [count] projects` line above it is only the aggregate count, not a substitute for it.
   - If `get_session()` reported no active book: print `Active Book: None yet` and omit the `Last worked on` line entirely rather than leaving a placeholder or fabricating a book.

6. **Suggest action** — Based on session state, checked in this order (first match wins):
   - If no authors: "Create your first author profile with `/storyforge:create-author`"
   - If no books: "Start a new book with `/storyforge:new-book`"
   - If `get_session()` returned an active book: "Continue with `/storyforge:resume [slug]`"
   - Otherwise (authors and books both exist, but no active book is set): "What would you like to work on?"
