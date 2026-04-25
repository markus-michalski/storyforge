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

### Step 2: Create Series
Use MCP `create_series()` with collected info.

### Step 3: Series Arc
For sequential/trilogy series — plan the OVERARCHING arc:
- What's the BIG question across all books?
- How does each book answer a piece of it?
- What escalates between books?
- How does the protagonist grow across the series?

Write to `{series}/series-arc.md`.

### Step 4: Book Planning
For each planned book:
- Working title
- Focus/theme of this installment
- Where it sits in the overarching arc
- New characters introduced
- Plot threads carried from previous books

### Step 5: Canon Management
Set up `{series}/world/canon.md`:
- Established facts that CANNOT be contradicted
- Character details (appearances, ages, abilities)
- World rules (magic systems, technology, geography)
- Timeline of events across books

Set up `{series}/characters/`:
- Recurring character profiles that track CHANGES across books
- Relationship evolution

### Step 6: Link Books
As books are created, link them via MCP `add_book_to_series()`.

## Rules
- Canon.md is sacred — once established, it's permanent
- Each book must work as a standalone reading experience (even in a trilogy)
- Series-level foreshadowing needs a PLANT & PAYOFF map across books
- Track what each character KNOWS at each point in the series — avoid info inconsistencies
