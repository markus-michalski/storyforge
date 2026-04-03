---
name: resume
description: |
  Resume work on an existing book project. Shows detailed status and recommends next steps.
  Use when: (1) User mentions a book name, (2) User says "weiter", "resume", "fortsetzen".
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<book-slug>"
---

# Resume Book

## Workflow

1. **Find book** — Use MCP `find_book()` with the user's query
   - If multiple matches: show list, ask user to pick
   - If no match: suggest `/storyforge:new-book`

2. **Load full data** — Use MCP `get_book_full()` with the slug

3. **Load progress** — Use MCP `get_book_progress()` for completion stats

4. **Load author profile** — If book has an author assigned, use MCP `get_author()`. Show active author.

5. **Update session** — Use MCP `update_session()` with this book as active

6. **Show status overview**
   ```
   [Book Title]
   ============
   Status: [status]
   Author: [author name]
   Genres: [genre list]
   Words: [current]/[target] ([%])
   Chapters: [drafted]/[total] ([final] final)
   Characters: [count]
   ```

7. **Show chapter status table**
   ```
   | # | Title | Status | Words |
   |---|-------|--------|-------|
   ```

8. **Recommend next action** — Based on book status:

   | Book Status | Recommended Skill |
   |-------------|-------------------|
   | Idea | `/storyforge:book-conceptualizer` |
   | Concept | `/storyforge:plot-architect` |
   | Research | `/storyforge:researcher` |
   | Plot Outlined | `/storyforge:character-creator` |
   | Characters Created | `/storyforge:world-builder` |
   | World Built | `/storyforge:chapter-writer [book] 1` |
   | Drafting | `/storyforge:chapter-writer [book] [next]` |
   | Revision | `/storyforge:chapter-reviewer` |
   | Editing | `/storyforge:voice-checker` |
   | Proofread | `/storyforge:export-engineer` |
   | Export Ready | `/storyforge:export-engineer [book] epub` |
