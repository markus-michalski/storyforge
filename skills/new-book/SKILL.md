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
   - **Book category** — `fiction` (default) or `memoir`. Memoir branches scaffold and several skills (Path E #97). Skip the question only when the user has already stated the category in their request.
   - **Genre(s)** — Show available genres via MCP `list_genres()`. Allow 1-3 selections. Mention genre-mixing. For memoir, frame genres as **thematic tags** (memoir-of-illness, memoir-of-place, etc.) — memoir does not use plot-genre conventions.
   - **Book type** — short-story, novelette, novella, novel, epic. Length is independent of category — a "memoir novella" is valid.
   - **Author profile** — Show available authors via MCP `list_authors()`. If none exist, suggest `/storyforge:create-author` first.
   - **Language** — Default: English
   - **Target word count** — Suggest based on book type:
     - Short Story: 5,000
     - Novelette: 12,000
     - Novella: 30,000
     - Novel: 80,000
     - Epic: 120,000

2. **Resolve writing mode** — Load the author profile via MCP `get_author(slug)`:

   **a) Lazy migration** — If `author_writing_mode` is missing or empty in the returned data:
   - Ask once: *"How do you approach writing? — Outliner (plan everything) / Plantser (key beats + discovery) / Discovery Writer (no outline)"*
   - Write back via MCP `update_author(slug, "author_writing_mode", value)`
   - This is a one-time migration; it never asks again once set.

   **b) Per-book override** — Show the author's default and ask:
   *"Your default writing style is [mode]. Same for this book, or override?"*
   - If override: store in book README frontmatter via MCP `update_field(book_readme_path, "author_writing_mode", value)`
   - If same: leave book `author_writing_mode` empty (inherits from author)

   **c) Route based on effective mode:**
   - `outliner` → suggest `/storyforge:plot-architect` for full outline
   - `plantser` → suggest `/storyforge:plot-architect` (user will choose minimal outline or Snowflake there)
   - `discovery` → suggest `/storyforge:rolling-planner` instead of `plot-architect`

3. **Create project** — Use MCP `create_book_structure()` with collected info. ALWAYS pass `book_category` explicitly (fiction or memoir) — the server branches the scaffold on this field (memoir uses `people/` instead of `characters/` and skips `world/`).

4. **Create CLAUDE.md** — Use MCP `init_book_claudemd(book_slug, book_title, pov, tense, genre, writing_mode)` to scaffold the per-book context file. Ask the user for `writing_mode` if not obvious: `scene-by-scene` (default), `chapter`, or `book`. Note: this `writing_mode` controls how Claude composes chapters — it is different from `author_writing_mode` which controls the planning workflow.

5. **Update session** — Use MCP `update_session()` with the new book as active

6. **Load genre README(s)** — Use MCP `get_genre()` for each selected genre. Show key conventions to the user.

7. **Suggest next steps** — Based on `book_category` and effective `author_writing_mode`:

   **Fiction:**
   - **Outliner:** "Start with `/storyforge:book-conceptualizer` → then `/storyforge:plot-architect` for the full outline"
   - **Plantser:** "Start with `/storyforge:book-conceptualizer` → then `/storyforge:plot-architect` (choose minimal outline or Snowflake)"
   - **Discovery:** "Start with `/storyforge:book-conceptualizer` (concept only, no plot) → then `/storyforge:rolling-planner` before each writing session"

   **Memoir:**
   - Mention that memoir-aware skills land in Phase 2+ (#97). Until then, manually load `book_categories/memoir/README.md` and the relevant `craft/*.md` docs at the start of each creative skill.
   - **Outliner:** "Start with `/storyforge:book-conceptualizer` → then `/storyforge:plot-architect` to pick a structure type (chronological / thematic / braided / vignette)"
   - **Plantser:** "Start with `/storyforge:book-conceptualizer` → then `/storyforge:plot-architect` for a chapter spine matching your structure type"
   - **Discovery:** "Start with `/storyforge:book-conceptualizer` (concept only) → then `/storyforge:rolling-planner` before each writing session. Skip `plot-architect`."

## Rules
- ALWAYS create the author profile BEFORE the book if none exists
- NEVER skip genre selection — it drives the entire writing process
- ALWAYS pass `book_category` explicitly to `create_book_structure()` — never rely on the default for memoir
- If the user provides a title as argument, use it directly
- Lazy migration in step 2a is idempotent — only ask if `author_writing_mode` is truly missing/empty
