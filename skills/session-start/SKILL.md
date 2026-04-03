---
name: session-start
description: |
  Initialize a StoryForge session: verify setup, load context, report status.
  Use when: (1) User types /start, (2) User says "start session", "Session starten".
model: claude-sonnet-4-6
user-invocable: true
---

# Session Start

## Workflow

1. **Verify setup**
   - Check `~/.storyforge/venv/` exists
   - Check `~/.storyforge/config.yaml` exists
   - If missing: suggest `/storyforge:setup` and STOP

2. **Load session context** via MCP `get_session()`
   - Show last active book, chapter, phase

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
   
   Last worked on: [book] — Chapter [N]
   ```

6. **Suggest action** — Based on session state:
   - If no authors: "Create your first author profile with `/storyforge:create-author`"
   - If no books: "Start a new book with `/storyforge:new-book`"
   - If active book: "Continue with `/storyforge:resume [slug]`"
   - If unclear: "What would you like to work on?"
