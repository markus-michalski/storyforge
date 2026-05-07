---
name: series-planner
description: |
  Plan a book series: overarching arc, book connections, canon management.
  Use when: (1) User says "Serie planen", "series", "book series",
  (2) User wants to write multiple connected books.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<series-name>"
---

# Series Planner

## Workflow

### Step 1: Series Concept
Ask the user:
- Series title
- How many books planned?
- Genre(s) — consistent across series
- What type of series?
  - **Sequential:** Same protagonist, ongoing plot (Harry Potter)
  - **Standalone-connected:** Same world, different protagonists per book (Discworld)
  - **Duology/Trilogy:** Tight arc across 2-3 books
  - **Episodic:** Same characters, standalone plots per book (mystery series)

**Wait for user input on all four points before proceeding to Step 2.** Series type changes everything downstream — guessing here forces a rewrite at Step 3.

### Step 2: Create Series
Use MCP `create_series()` with collected info.

### Step 3: Series Arc
For sequential/trilogy series — plan the OVERARCHING arc:
- What's the BIG question across all books?
- How does each book answer a piece of it?
- What escalates between books?
- How does the protagonist grow across the series?

Write to `{series}/series-arc.md`.

**Wait for user approval of the series arc before proceeding to Step 4.** Per-book planning depends on a locked overarching arc.

### Step 4: Book Planning
For each planned book:
- Working title
- Focus/theme of this installment
- Where it sits in the overarching arc
- New characters introduced
- Plot threads carried from previous books

**Wait for user approval of the book plan before proceeding to Step 5 (Canon Management).** Canon facts are derived from book plans — building canon before plans exist creates orphan facts.

### Step 5: Canon Management
Set up `{series}/world/canon.md`:
- Established facts that CANNOT be contradicted
- Character details (appearances, ages, abilities)
- World rules (magic systems, technology, geography)
- Timeline of events across books

Set up `{series}/characters/` from `templates/series-character-tracker.md`:
- One tracker file per recurring character (`recurs_in: [B1, B2, ...]`)
- `## Snapshot` (essence at series scope), `## Evolution per Band` (B1 Start/Ende, B2 geplant), `## Beziehungen über die Bände`, `## Updates Log`
- `tracker_type: thin` for characters whose full profile lives in their home book; `full` is rare and only for characters that span books equally without a home book

**`book_slug:` mapping (Issue #194).** When you propose a tracker slug that differs from the slugified character name (and from the existing book-level character slug — e.g. you pick `king-caelan` for a character whose book-level file is `caelan.md`), write the optional `book_slug:` frontmatter field on the tracker. This is what the future harvest, bootstrap, and brief-source tooling (Issue #195) consumes to bridge between scopes:

```yaml
---
name: "King Caelan"
slug: "king-caelan"
book_slug: "caelan"        # ← explicit book-level equivalent
role: "supporting"
recurs_in: ["B1", "B2", "B3"]
tracker_type: "thin"
---
```

When the tracker slug already matches the book-level slug (e.g. `kael` ↔ `kael.md`), omit `book_slug:` — the resolver falls back to the tracker slug. Zero-config for the common case.

### Step 6: Link Books
As books are created, link them via MCP `add_book_to_series()`.

## Rules
- Canon.md is sacred — once established, treat it as permanent. Changes require a series-level revision pass.
- Each book must work as a standalone reading experience (even in a trilogy).
- Series-level foreshadowing needs a PLANT & PAYOFF map across books.
- Track what each character KNOWS at each point in the series — info inconsistencies are the most common series-level failure.
