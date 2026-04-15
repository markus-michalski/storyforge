---
name: new-book
description: |
  Create a new book project with full directory scaffold.
  Use when: (1) User says "neues Buch", "new book", "Projekt anlegen",
  (2) User wants to start writing something new.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[title]"
---

# Create New Book

## Workflow

### If called with `--from-idea {slug}`
1. Load the idea via MCP `get_idea(slug)`
2. Pre-fill title, genres, and logline from the idea's frontmatter
3. Skip re-asking for fields that are already populated (ask only for missing ones)
4. After creating the book, call MCP `promote_idea(slug, book_slug)` to mark the idea as promoted

### Standard flow
1. **Gather information** — Ask the user (use AskUserQuestion):
   - **Title** — What's the working title?
   - **Genre(s)** — Show available genres via MCP `list_genres()`. Allow 1-3 selections. Mention genre-mixing.
   - **Book type** — short-story, novelette, novella, novel, epic
   - **Author profile** — Show available authors via MCP `list_authors()`. If none exist, suggest `/storyforge:create-author` first.
   - **Language** — Default: English
   - **Target word count** — Suggest based on book type:
     - Short Story: 5,000
     - Novelette: 12,000
     - Novella: 30,000
     - Novel: 80,000
     - Epic: 120,000

2. **Create project** — Use MCP `create_book_structure()` with collected info

3. **Update session** — Use MCP `update_session()` with the new book as active

4. **Load genre README(s)** — Use MCP `get_genre()` for each selected genre. Show key conventions to the user.

5. **Suggest next steps** — Based on the genre and book type:
   - "Start with `/storyforge:book-conceptualizer` to develop your concept"
   - "Or jump to `/storyforge:plot-architect` if you already know the story"
   - "Need characters first? Try `/storyforge:character-creator`"

## Rules
- ALWAYS create the author profile BEFORE the book if none exists
- NEVER skip genre selection — it drives the entire writing process
- If the user provides a title as argument, use it directly
