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

4. **Load author profile** — If `get_book_full()` shows an author assigned, use MCP `get_author()` and show the resolved author name in the overview. If **no author is assigned**, skip `get_author()` and show `Author: None` — don't drop the line silently and don't fabricate a name.

5. **Update session** — Use MCP `update_session()` with this book as active (required — actually call it; do not skip even though the step-6 report template has no visible slot for it)

6. **Show status overview** — fill the Words/Chapters lines from `get_book_progress()`'s pre-computed fields, don't re-derive them: `Words` = `total_words`/`target_words` (`word_progress_percent`), `Chapters` = `chapters_drafted`/`chapters_total` (`chapters_final` final). `chapters_drafted` already counts every chapter with written content (i.e. past outline — both `Drafted` and `Final` statuses), so a chapter's raw status string alone is not a reliable proxy; trust the returned field.
   ```
   [Book Title]
   ============
   Status: [status]
   Author: [author name]
   Genres: [genre list]
   Words: [total_words]/[target_words] ([word_progress_percent]%)
   Chapters: [chapters_drafted]/[chapters_total] ([chapters_final] final)
   Characters: [count]
   ```

7. **Show chapter status table**
   ```
   | # | Title | Status | Words |
   |---|-------|--------|-------|
   ```

8. **Load per-book CLAUDE.md** — MCP `get_book_claudemd(book_slug)`. If it exists, show a compact summary, sourcing each list from its **DB-backed** section. The file also contains same-named static template sections (`## Workflow`, `## Rules`, `## Callback Register`) that are generic boilerplate, NOT the book's real entries — do not summarize those:
   - Active **Workflow** entries from `## Workflow Instructions (from DB)` (verbatim)
   - Active **Rules** from `## Rules (from DB)` (verbatim, up to the 10 most recent — the section is ordered oldest-first, so "most recent" means the last 10 entries, not the first 10)
   - Pending **Callbacks** from `## Callback Register (from DB)` (verbatim)

   If the file is missing (older book predating this feature, or `get_book_claudemd()` returns a not-found error): say so, and offer to run `init_book_claudemd` with the already-collected book facts (title/genre) — don't re-ask the user for them and don't fabricate a summary.

9. **Recommend next action** — Based on book status:

   | Book Status | Recommended Skill |
   |-------------|-------------------|
   | Idea | `/storyforge:book-conceptualizer` |
   | Concept | `/storyforge:plot-architect` |
   | Research | `/storyforge:researcher` |
   | Plot Outlined | `/storyforge:character-creator` |
   | Characters Created | `/storyforge:world-builder` |
   | World Built | `/storyforge:chapter-writer [book] 1` |
   | Drafting | `/storyforge:chapter-writer [book] [next]` |
   | Revision | `/storyforge:chapter-reviewer` → `chapter-humanizer` → `chapter-proofreader` |
   | Editing | `/storyforge:manuscript-checker` + optionally `/storyforge:voice-checker` |
   | Proofread | `/storyforge:export-engineer` |
   | Export Ready | `/storyforge:export-engineer [book] epub` |

   - `[next]` = the highest existing chapter number + 1 (from `get_book_progress()`), e.g. if chapters 1–14 exist, recommend `... [book] 15` — never a hardcoded `1` or the highest existing number itself.
   - When a status's cell lists more than one skill (e.g. Revision's `chapter-reviewer → chapter-humanizer → chapter-proofreader`, or Editing's `manuscript-checker` + optional `voice-checker`), show the **whole** chain in the given order — don't collapse it to just the first skill.
   - If the book's status matches **no** row in this table (e.g. `Archived`), say plainly that no specific next-step recommendation applies for that status — don't force-fit an unrelated row and don't silently omit the section.
