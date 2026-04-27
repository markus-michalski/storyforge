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
| #  | Title          | Status   | Words |
|----|----------------|----------|-------|
| 1  | The Beginning  | Final    | 3,200 |
| 2  | Into the Dark  | Draft    | 2,800 |
| 3  | —              | Outline  | 0     |

Characters ([count]):  ← header reads "Real People" when book_category == "memoir"
| Name      | Role        | Status      |
|-----------|-------------|-------------|
| Alex      | Protagonist | Arc Defined |
| The Shape | Antagonist  | Profile     |

Next: /storyforge:chapter-writer [slug] 2
```

Memoir-aware adjustments:

- Header says **Length:** instead of **Type:** so `book_type` (length class) and `book_category` are not confused.
- Characters table header reads **Real People** for memoir (Phase 2 #59 will move the underlying data to `people/`; until then the indexer still scans `characters/` for both categories).
- Suggest the matching memoir-mode next-step skill once Phase 2 lands; for now mirror the fiction routing.

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

When the user passes `--category fiction` or `--category memoir`, filter the books table to that category before rendering. With no flag, show all and group by category if there are entries in both.
