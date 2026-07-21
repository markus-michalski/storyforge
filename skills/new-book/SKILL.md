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
4. After creating the book, call MCP `promote_idea(slug, book_slug)` to mark the idea as promoted — do this even after the full standard-flow steps below (project creation, CLAUDE.md, session, series copy) have run; it's easy to forget once several other steps separate it from the idea that started this flow

### Standard flow
1. **Gather information** — Ask the user (use AskUserQuestion):
   - **Title** — What's the working title?
   - **Book category** — `fiction` (default) or `memoir`. Memoir branches scaffold and several skills (Path E #97). Skip the question only when the user has already stated the category in their request.
   - **Genre(s)** — Show available genres via MCP `list_genres()`. Allow 1-3 selections. Mention genre-mixing. For memoir, frame genres as **thematic tags** (memoir-of-illness, memoir-of-place, etc.) — memoir does not use plot-genre conventions. This step is never skipped, even if the user says a genre out loud in their opening message or asks you to "just pick one" — still confirm the selection against a real `list_genres()` result (don't take a user-stated word like "thriller" as a verified slug without checking it against the list).
   - **Book type** — short-story, novelette, novella, novel, epic. Length is independent of category — a "memoir novella" is valid.
   - **Author profile** — Show available authors via MCP `list_authors()`. If none exist, suggest `/storyforge:create-author` first.
   - **Point of view & tense** — Ask (e.g. first-person / third-limited / third-omniscient; past / present). Step 4's `init_book_claudemd()` call needs both — don't reach Step 4 without having asked, and don't silently pass blank or guessed values just because the tool accepts empty strings.
   - **Language** — Default: English
   - **Target word count** — Suggest based on book type:
     - Short Story: 5,000
     - Novelette: 12,000
     - Novella: 30,000
     - Novel: 80,000
     - Epic: 120,000
   - If the user asks you to skip the language or word-count questions ("don't ask, just use whatever"), still apply and state the concrete default (English; the book-type's suggested count above) rather than leaving the field unset with no value.

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

6. **Auto-copy recurring characters from prior book in series** (Issue #196) — If the new book is part of an existing series AND there is a prior book in that series:

   a. Resolve the series link. The user may pass it explicitly: `/storyforge:new-book moonrise --series=blood-and-binary --copy-recurring-from=blood-and-binary-firelight`. Or — if `series:` is set on the new book and there's exactly one prior book in `series/{slug}/books/`, auto-detect it. If there is **more than one** prior book and no explicit `--copy-recurring-from` was given, do NOT guess (not "most recent", not "book 1") and do NOT silently skip the step — list the candidate prior books and ask the user which one to copy from.

   b. Compute the new book's band from `series_number` (set by `add_book_to_series()`): `band = f"B{series_number}"`. Skip this step entirely when `series_number` is missing or `1` (first book — nothing to copy from) — this holds even when the user talks about "the series" in conversation; the skip is driven purely by the actual `series_number` value, not by whether a series was mentioned.

   c. Show the planned copy (use AskUserQuestion to confirm):

      ```
      Found previous book in series: {prev_book_slug}
      Will copy recurring characters from {prev_book_slug} → {new_book_slug} ({band}):

        ✓ {N} files to copy
        ⚠ {M} new chars in {band} need manual creation (no source)
        ⊘ {K} chars excluded (recurs_in does not include {band})
      ```

      Options: **Yes, copy** (default) / **Skip — I'll do it manually**.

   d. On confirmation, call MCP `copy_recurring_chars_to_new_book(series_slug, prev_book_slug, new_book_slug, band, book_category)` — pass all five parameters, including `book_category` (easy to drop since it's last in the list; the tool needs it to know whether to write into `characters/` or `people/`). The tool returns `{copied, skipped, new_chars}`.

   e. Report the result:

      ```
      Copied {len(copied)} character files:
        - {tracker_slug} → characters/{book_slug}.md
        - ...

      Skipped {len(skipped)} (already existed):
        - ...

      Need manual creation ({len(new_chars)} new in {band}):
        - {tracker_slug} (recurs_in: {recurs_in})
        - ...
      ```

   This is the **dumb-copy version** (#196). For smart frontmatter migration based on the series-tracker's `B{prev} Ende` and `B{new} (geplant)` sections, run `/storyforge:bootstrap-book-from-series` (D-2 of #195, future) after this.

7. **Load genre README(s)** — Use MCP `get_genre()` for each selected genre. Show key conventions to the user.

8. **Suggest next steps** — Based on `book_category` and effective `author_writing_mode`:

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
- ALWAYS pass `book_category` explicitly to `create_book_structure()` — never rely on the default for memoir. This holds even if the user asks you to skip it or "just use the tool's defaults" — a fiction-shaped default would scaffold the wrong directories for a memoir (`characters/` + `world/` instead of `people/`)
- If the user provides a title as argument, use it directly
- Lazy migration in step 2a is idempotent — only ask if `author_writing_mode` is truly missing/empty
