---
name: book-dashboard
description: |
  Show progress overview for a book or all books.
  Use when: (1) User says "Dashboard", "Status", "Fortschritt", "Übersicht".
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug]"
---

# Book Dashboard

## Workflow

### If book slug provided (or active book in session):

Before falling back to the no-book overview branch below, actively check whether the session
already has an active book set (`get_session()`) — do not treat "no slug typed this turn" as
equivalent to "no book to show." An active session book resolves the target exactly like an
explicit slug argument would; only fall through to the overview branch if there is truly neither.

1. **Load book progress** — MCP `get_book_progress()` (carries `book_category`)
2. **Load book full** — MCP `get_book_full()` for characters/people and details
3. **Display detailed dashboard:**

```
=== [Book Title] ===
Status: [status]
Category: [book_category]   ← fiction or memoir
Author: [author] | Genres: [genres] | Length: [book_type]

Words: [current]/[target] [████████░░░░] [%]%

Chapters ([final]/[total] final):
| #  | Title          | Status   | Words | Canon |
|----|----------------|----------|-------|-------|
| 1  | The Beginning  | Final    | 3,200 | 4     |
| 2  | Into the Dark  | Draft    | 2,800 | 0     |
| 3  | —              | Outline  | 0     | —     |

Characters ([count]):  ← header reads "Real People" when book_category == "memoir"
| Name      | Role        | Status      |
|-----------|-------------|-------------|
| Alex      | Protagonist | Arc Defined |
| The Shape | Antagonist  | Profile     |

Next: /storyforge:chapter-writer [slug] 2
```

("Alex" / "The Shape" above are illustrative placeholder names for this template only — always
source real names from `get_book_full()`; if it returns zero characters/people, render the table
with zero rows (e.g. `Characters (0):`), never carry these example names into an actual render.)

**Next line:** point at the first chapter (in ascending chapter-number order) whose status is NOT
`Final` — i.e. the first `Draft` or `Outline` chapter, whichever comes first numerically. This is
the rule the example above demonstrates (ch1 Final, ch2 Draft, ch3 Outline → "Next: ... 2"): a
chapter already in `Draft` still counts as "next" even though it has prose, since it isn't `Final`
yet. If every chapter is `Final`, omit the Next line (nothing left to write).

Memoir-aware adjustments:

- Header says **Length:** instead of **Type:** so `book_type` (length class) and `book_category` are not confused.
- Characters table header reads **Real People** for memoir (Phase 2 #59 will move the underlying data to `people/`; until then the indexer still scans `characters/` for both categories).
- Suggest the matching memoir-mode next-step skill once Phase 2 lands; for now mirror the fiction routing.

**Canon column:**
- `get_book_progress()`'s per-chapter map now carries `canon_facts_count` (Issue #476, resolved) —
  a server-side `COUNT(*) FROM canon_facts WHERE chapter_num = N` for this book. Read it directly;
  do not call `get_canon_brief()` for this purpose — its `current_facts` is a backward-looking
  context window that always excludes the target chapter's own facts, structurally the wrong tool
  for a per-chapter count.
- **"Has prose" means `words > 0` (or `get_book_full()`'s per-chapter `has_draft: true`), NOT
  `status != "Outline"`.** Confirmed live against real sandbox chapters: a chapter can carry
  `status: "Outline"` while already having a nonzero word count (both `zz-sandbox-book`'s and
  `zz-sandbox-book-memoir`'s chapters currently do — `words: 110`/`41`/`44` respectively, all still
  `status: "Outline"`). Using status alone as the "has prose" proxy would wrongly render `—` for a
  chapter that already has drafted content.
- Render the chapter's `canon_facts_count` for any chapter that has prose — including `0`, which is
  a legitimate ("no facts recorded yet for this chapter") result now, not a placeholder.
- `—` — chapter has `words == 0`, nothing drafted yet to record facts from

### If no specific book:

1. **List all books** — MCP `list_books()` (each entry carries `book_category`)
2. **List all authors** — MCP `list_authors()`
3. **Show overview:**

```
=== StoryForge Dashboard ===

Books ([count]):
| Title          | Category | Status   | Words  | Chapters |
|----------------|----------|----------|--------|----------|
| My Horror Novel| fiction  | Drafting | 24,000 | 8/25     |
| Year of Glass  | memoir   | Concept  | 0      | 0/12     |
| Short Story    | fiction  | Concept  | 0      | 0/1      |

Authors ([count]):
| Name           | Genres          | Studied |
|----------------|-----------------|---------|
| dark-narrator  | horror, fantasy | 3 works |

Ideas: [count] in backlog
```

When the user passes `--category fiction` or `--category memoir`, filter the books table to that category before rendering. If the filter matches zero books, say so explicitly (e.g. "No memoir books found") rather than showing an empty table with no explanation or silently falling back to unfiltered results.

With no flag, show all and group by category (separate labeled sections) only if there are entries in both categories. If every book shares one category, show a single combined table — do not add per-category group headers when there's nothing to distinguish.
