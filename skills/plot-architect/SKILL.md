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
- **5-Act / Freytag's Pyramid** — Tragic or complex narratives. Best for: literary, drama, historical, corruption/downfall arcs.
- **Fichtean Curve** — Start in action. Best for: thriller, horror.
- **Dan Harmon's Story Circle** — Character transformation first. Best for: character-driven, episodic, comedic stories. 8 steps: comfort → want → unfamiliar → adapt → get want → pay price → return → changed.
- **Seven-Point Structure** — Design from both ends (know your ending first). Best for: fantasy, thriller, adventure. Hook → Plot Point 1 → Pinch 1 → Midpoint → Pinch 2 → Plot Point 2 → Resolution.
- **Kishotenketsu** — No central conflict. Best for: literary, slice-of-life.

**Recommendation logic:**
- Protagonist doesn't fundamentally change → Flat arc → consider **Hero's Journey** or **Seven-Point**
- Protagonist corrupts or falls → **5-Act / Freytag's Pyramid**
- Story is episodic or comedy-driven → **Dan Harmon's Story Circle**
- Author knows the ending but not the middle → **Seven-Point Structure**
- Pantser / Plantser writing mode → lean toward **3-Act** (minimal) or **Dan Harmon's Story Circle** (8 clear checkpoints)

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

### Step 8: Initialize Story Timeline
Create `{project}/plot/timeline.md` from the template `plot-timeline.md`:
1. Ask the user: "Wann beginnt die Geschichte? Brauchst du ein konkretes Datum oder reicht ein Wochentag?"
2. Establish the **Anchor Point** (Story Day 1 = which day of week, optionally a real date)
3. Pre-fill the Event Calendar with the major plot beats from Step 3 (rough day estimates)
4. Mark all pre-filled entries as `[PLANNED]` — the chapter-writer will refine them

This step is MANDATORY. A book without a timeline anchor cannot maintain temporal consistency.

Update book status to "Plot Outlined" via MCP `update_field()`.

### Step 9: Create Tonal Document
Create `{project}/plot/tone.md` from template `plot-tone.md`. This step is MANDATORY for new books.

1. **Interview the user** (use AskUserQuestion or conversational flow):
   - What should this book feel like to read? (overall emotional texture)
   - Which authors or works should we channel for tone? Which to avoid?
   - Are there non-negotiable rules? (e.g. humor must always be present, certain characters always felt)
   - What would be a WARNING sign that the tone is drifting?

2. **Populate the Tonal Arc** based on the act structure from Step 3:
   - Map dominant/secondary tone per act/stage
   - Define warning signs per stage (what would be WRONG)
   - The tonal arc should SHIFT across the story — monotone is death

3. **Define the Litmus Test** — 5-6 yes/no questions the chapter-writer answers after every chapter.
   These should be specific to THIS book, not generic craft questions.

4. **Non-Negotiable Rules** — Book-specific prose rules beyond the author profile's general style.

5. Write the completed document to `{project}/plot/tone.md`.

This document guards against tonal drift during long-form writing. Without it, books tend to collapse into generic "literary" mode after ~15 chapters.

## Rules
- Structure serves story — never force a story into a structure that doesn't fit
- Every beat must have emotional PURPOSE, not just plot function
- The "Therefore/But" test: every event must cause the next, not "and then"
- Midpoint is NOT halfway through the events — it's the REVERSAL that changes everything
- Foreshadowing map is mandatory — no deus ex machina allowed
