---
name: book-conceptualizer
description: |
  Develop a book concept through 5 phases: premise, theme, conflict, structure, pitch.
  Use when: (1) User says "Konzept", "develop concept", "Buchkonzept",
  (2) After brainstorming, to deepen an idea into a workable concept.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<book-slug>"
---

# Book Conceptualizer

## Prerequisites
- Book project must exist (via `/storyforge:new-book`)
- Load book data via MCP `get_book_full()`
- Load genre README(s) via MCP `get_genre()` for each genre
- Load craft references: `story-structure`, `plot-craft`, `theme-development` via MCP `get_craft_reference()`

## Workflow — 5 Phases

### Phase 1: Premise Refinement
Start with whatever the user has. Ask probing questions:
- "What's the ONE thing that excites you about this story?"
- "If a reader remembers only one thing, what should it be?"
- "What's the emotional experience you want to create?"

Refine into a clear **Premise** (2-3 sentences): Character + Situation + Central Conflict.

Write to `{project}/README.md` under "## Premise".

### Phase 2: Theme Discovery
Don't tell — ask:
- "What question does this story ask?" (NOT "what lesson does it teach")
- "What do your protagonist and antagonist disagree about?"
- "What's the argument your story is making — without being preachy?"

Reference `theme-development.md` — theme as QUESTION, not answer.

Write to `{project}/README.md` under "## Themes".

### Phase 3: Conflict Architecture
Using `conflict-types.md` as reference:
- **External conflict:** What stands in the protagonist's way?
- **Internal conflict:** What's the protagonist's fatal flaw? What lie do they believe?
- **How do they mirror each other?** The external journey should reflect the internal one.
- **Stakes:** What happens if they fail? (Personal → Relational → Community → Existential)

### Phase 4: Structure Selection
Using `story-structure.md`:
- Recommend a structure based on genre and story type
- Show the user 2-3 options with pros/cons
- Map the concept to the chosen structure's beats

Write initial outline to `{project}/plot/outline.md`.

### Phase 5: Pitch Creation
Generate:
- **Logline:** One sentence ([Character] must [action] or [stakes])
- **Elevator pitch:** 2-3 sentences
- **Comparable titles:** "X meets Y"
- **Back-cover blurb:** 150-200 words (does NOT reveal ending)

Write to `{project}/synopsis.md`.

Update book status to "Concept" via MCP `update_field()`.

## Rules
- NEVER impose a theme — discover it through questions
- The concept must emerge from DIALOG with the user, not from AI generation alone
- Every concept needs ALL three: premise + theme + conflict. Don't skip any.
- Load genre conventions — they shape structural expectations
