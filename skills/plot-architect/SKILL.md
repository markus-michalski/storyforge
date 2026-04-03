---
name: plot-architect
description: |
  Structure the plot with acts, beats, turning points, and character arcs.
  Use when: (1) User says "Plot", "Handlung", "Struktur", "outline",
  (2) After concept is developed, before character creation.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<book-slug>"
---

# Plot Architect

## Prerequisites
- Load book data via MCP `get_book_full()`
- Load author profile via MCP `get_author()` if assigned
- Load genre README(s) via MCP `get_genre()`
- Load craft references via MCP `get_craft_reference()`:
  - `story-structure` (structures and when to use them)
  - `plot-craft` (beats, foreshadowing, cause-effect)
  - `tension-and-suspense` (stakes, cliffhangers, pacing)
  - `conflict-types` (escalation, moral dilemmas)

## Workflow

### Step 1: Read Existing Work
- Read `{project}/README.md` for premise, themes, concept
- Read `{project}/plot/outline.md` for any existing outline
- Read `{project}/characters/` if characters exist already

### Step 2: Choose Structure
Based on genre and story type, recommend a structure. Use AskUserQuestion:
- **3-Act** — Most versatile. Best for: thriller, romance, mystery, contemporary.
- **Hero's Journey** — Quest narratives. Best for: fantasy, sci-fi, adventure.
- **Save the Cat** — Detailed beats. Best for: commercial fiction, thriller, romance.
- **5-Act** — Tragic or complex narratives. Best for: literary, drama, historical.
- **Fichtean Curve** — Start in action. Best for: thriller, horror.
- **Kishotenketsu** — No central conflict. Best for: literary, slice-of-life.

### Step 3: Map Plot Beats
For the chosen structure, work through each beat WITH the user:

**Per beat, define:**
- What happens (event)
- Why it matters (emotional/thematic purpose)
- Which character(s) are involved
- What changes (stakes, knowledge, relationships)
- Approximate chapter position

Write to `{project}/plot/acts.md`.

### Step 4: Subplot Architecture
For each subplot:
- Purpose (mirror, contrast, or complicate the main plot)
- Characters involved
- How it weaves into the main plot
- Resolution timing (before, during, or after climax)

Reference `plot-craft.md` on subplot integration.

### Step 5: Foreshadowing Map
Create a Plant & Payoff table:

| Plant (Chapter) | Payoff (Chapter) | Element | Type |
|-----------------|-------------------|---------|------|
| Ch. 3 | Ch. 22 | The locked door | Direct |
| Ch. 5 | Ch. 18 | Character's fear of water | Symbolic |

Write to `{project}/plot/outline.md`.

### Step 6: Character Arc Alignment
Map each major character's arc beats to plot beats:
- Where does their Lie get challenged?
- Where is their Midpoint "moment of truth"?
- How does their climax align with the plot climax?

Write to `{project}/plot/arcs.md`.

### Step 7: Chapter Plan
Generate a chapter-by-chapter plan with:
- Chapter number
- Working title
- POV character
- Key events
- Subplot threads active
- Approximate word count

Offer to create chapter directories via MCP `create_chapter()`.

Update book status to "Plot Outlined" via MCP `update_field()`.

## Rules
- Structure serves story — never force a story into a structure that doesn't fit
- Every beat must have emotional PURPOSE, not just plot function
- The "Therefore/But" test: every event must cause the next, not "and then"
- Midpoint is NOT halfway through the events — it's the REVERSAL that changes everything
- Foreshadowing map is mandatory — no deus ex machina allowed
