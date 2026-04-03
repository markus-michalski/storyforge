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

1. **Load book progress** — MCP `get_book_progress()`
2. **Load book full** — MCP `get_book_full()` for characters and details
3. **Display detailed dashboard:**

```
=== [Book Title] ===
Status: [status]
Author: [author] | Genres: [genres] | Type: [book_type]

Words: [current]/[target] [████████░░░░] [%]%

Chapters ([final]/[total] final):
| #  | Title          | Status   | Words |
|----|----------------|----------|-------|
| 1  | The Beginning  | Final    | 3,200 |
| 2  | Into the Dark  | Draft    | 2,800 |
| 3  | —              | Outline  | 0     |

Characters ([count]):
| Name      | Role        | Status      |
|-----------|-------------|-------------|
| Alex      | Protagonist | Arc Defined |
| The Shape | Antagonist  | Profile     |

Next: /storyforge:chapter-writer [slug] 2
```

### If no specific book:

1. **List all books** — MCP `list_books()`
2. **List all authors** — MCP `list_authors()`
3. **Show overview:**

```
=== StoryForge Dashboard ===

Books ([count]):
| Title          | Status   | Words  | Chapters |
|----------------|----------|--------|----------|
| My Horror Novel| Drafting | 24,000 | 8/25     |
| Short Story    | Concept  | 0      | 0/1      |

Authors ([count]):
| Name           | Genres          | Studied |
|----------------|-----------------|---------|
| dark-narrator  | horror, fantasy | 3 works |

Ideas: [count] in backlog
```
