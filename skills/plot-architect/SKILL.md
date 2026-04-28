---
name: plot-architect
description: |
  Fiction plot architect. Structures the plot with acts, beats, turning
  points, and character arcs across nine standard structures (3-Act,
  Hero's Journey, Save the Cat, Snowflake, etc.).
  Use when: (1) `book_category == "fiction"` (or missing) AND user says
  "Plot", "Handlung", "Struktur", "outline", "plot beats",
  (2) After concept is developed, before character creation.
  Memoir books → use `/storyforge:plot-architect-memoir` instead.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug>"
---

# Plot Architect (Fiction)

This skill is the fiction variant of plot-architect, split out per Issue #126 so fiction-only sessions never load the memoir structure types and memoir-only sessions never load the fiction structure catalog.

## Step 0a — Verify fiction mode

Before any other prerequisite load:

1. **Load book data** via MCP `get_book_full(slug)`.
2. Read `book_category`. Treat missing as `fiction`. If it is `memoir`, stop and tell the user:
   > *This book's `book_category` is `memoir`. Use `/storyforge:plot-architect-memoir` for memoir narrative-arc work — fiction structure (3-Act, Hero's Journey, Snowflake, ...) does not apply to lived material.*
3. Otherwise proceed with the workflow below.

## Prerequisites — MANDATORY LOADS

- **Book data** via MCP `get_book_full()`. **Why:** Existing premise, theme, characters, writing-mode — Step 0b branches on `effective_author_writing_mode` and Step 1 builds on existing concept output.
- **Author profile** via MCP `get_author()` if assigned. **Why:** The author profile may carry structural preferences (e.g. "always uses 5-act tragic arcs") that bias the recommendation in Step 2.
- **Genre README(s)** via MCP `get_genre()`. **Why:** Genre dictates expected structures (romance = 3-Act + HEA, thriller = Fichtean) and beat conventions.
- **Craft references** via MCP `get_craft_reference()`:
  - `story-structure` — **Why:** The structure catalog Step 2 picks from — without it, recommendations default to generic 3-Act.
  - `plot-craft` — **Why:** Beats, foreshadowing, cause-effect logic — Step 3 (beat mapping) and Step 5 (foreshadowing map) are built on this.
  - `tension-and-suspense` — **Why:** Stakes, cliffhangers, pacing — what makes the chapter-by-chapter plan in Step 7 actually keep readers turning pages.
  - `conflict-types` — **Why:** Escalation patterns and moral dilemma structures — Step 4 subplot architecture depends on knowing how conflicts compound.

## Workflow

### Step 0b: Check Writing Mode

Load the book via MCP `get_book_full(slug)` and read `effective_author_writing_mode`.

- **`discovery`** — Stop here. Discovery writers skip `plot-architect` entirely.
  Tell the user: *"Your writing mode is Discovery — you don't need a full outline. Use `/storyforge:rolling-planner` before each writing session instead."*
  Do not proceed unless the user explicitly overrides this.
- **`plantser`** — Proceed, but flag at Step 2 that the goal is a **Minimal Viable Outline only** (6 sentences), not a full beat sheet. Skip Steps 4–6 unless the user asks for them. Suggest Snowflake or 3-Act (minimal) as the default structure.
- **`outliner`** — Proceed with the full workflow below.

### Step 1: Read Existing Work

- Read `{project}/README.md` for premise, themes, concept
- Read `{project}/plot/outline.md` for any existing outline
- Read `{project}/characters/` if characters exist already

### Step 2: Choose Structure

Based on genre and story type, recommend a structure. Use AskUserQuestion.

**Wait for the user's structure choice before proceeding to Step 3.** Each downstream step builds on the chosen structure — guessing here cascades.

- **3-Act** — Most versatile. Best for: thriller, romance, mystery, contemporary.
- **Hero's Journey** — Quest narratives. Best for: fantasy, sci-fi, adventure.
- **Save the Cat** — Detailed beats. Best for: commercial fiction, thriller, romance.
- **5-Act / Freytag's Pyramid** — Tragic or complex narratives. Best for: literary, drama, historical, corruption/downfall arcs.
- **Fichtean Curve** — Start in action. Best for: thriller, horror.
- **Dan Harmon's Story Circle** — Character transformation first. Best for: character-driven, episodic, comedic stories. 8 steps: comfort → want → unfamiliar → adapt → get want → pay price → return → changed.
- **Seven-Point Structure** — Design from both ends (know your ending first). Best for: fantasy, thriller, adventure. Hook → Plot Point 1 → Pinch 1 → Midpoint → Pinch 2 → Plot Point 2 → Resolution.
- **Kishotenketsu** — No central conflict. Best for: literary, slice-of-life.
- **Snowflake Method** — Iterative/fractal planning. Build story in 10 growing circles, plot and characters in parallel. Best for: writers who want structure but prefer iteration over linear planning; those prone to abandoned first drafts. → If selected, follow the **Snowflake Workflow** below instead of Steps 3–8.

**Recommendation logic:**

- Protagonist doesn't fundamentally change → Flat arc → consider **Hero's Journey** or **Seven-Point**
- Protagonist corrupts or falls → **5-Act / Freytag's Pyramid**
- Story is episodic or comedy-driven → **Dan Harmon's Story Circle**
- Author knows the ending but not the middle → **Seven-Point Structure**
- Pantser / Plantser writing mode → lean toward **3-Act** (minimal) or **Dan Harmon's Story Circle** (8 clear checkpoints)
- Writer struggles with plot holes or abandons drafts → **Snowflake Method**

### Step 3: Map Plot Beats

For the chosen structure, work through each beat WITH the user:

**Per beat, define:**

- What happens (event)
- Why it matters (emotional/thematic purpose)
- Which character(s) are involved
- What changes (stakes, knowledge, relationships)
- Approximate chapter position

Write to `{project}/plot/acts.md`.

**Wait for user approval of the beat map before proceeding to Step 4.** Subplot architecture (Step 4) and foreshadowing (Step 5) depend on locked main-plot beats.

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
3. **Define the Litmus Test** — 5-6 yes/no questions the chapter-writer answers after every chapter. These should be specific to THIS book, not generic craft questions.
4. **Non-Negotiable Rules** — Book-specific prose rules beyond the author profile's general style.
5. Write the completed document to `{project}/plot/tone.md`.

This document guards against tonal drift during long-form writing. Without it, books tend to collapse into generic "literary" mode after ~15 chapters.

---

## Snowflake Workflow

*Use this section instead of Steps 3–8 when the user selects the Snowflake Method.*

*Theory and step descriptions in `reference/craft/story-structure.md` (loaded as prerequisite). This section covers StoryForge-specific execution: file paths, MCP tools, and skill integrations.*

### Snowflake Step 1: One-Sentence Summary

If `book-conceptualizer` has run, confirm or refine the existing premise. Otherwise write it now:

- Maximum 15 words
- Must name: protagonist, what they must do/achieve, and the stakes
- Example: "A disgraced knight must recover a stolen relic before war consumes the kingdom."

Write or update via MCP `update_field(book_slug, "premise", ...)`.

### Snowflake Step 2: One-Paragraph Summary

Expand into one paragraph with four sentences:

1. Setup + inciting incident (Act 1)
2. First major escalation / protagonist's early efforts (Act 2a)
3. Crisis / midpoint reversal (Act 2b)
4. Climax + resolution (Act 3)

Write to `{project}/plot/outline.md` (opening section).

### Snowflake Step 3: Character Summaries (Parallel to Plot)

For each major character write a one-page summary:

- Name, role, one-sentence arc
- Motivation (what they consciously want)
- Goal (concrete objective for this story)
- Conflict (what blocks them)
- Epiphany (what they learn/realize by the end)
- Backstory sentence (one line only at this stage)

**Key philosophy:** Characters and plot develop together. After completing Step 3, **go back and revise Steps 1–2** to reflect what the characters demand.

Trigger `character-creator` in parallel mode for deep character work if needed.
Store summaries via MCP `update_field()` in each character's file.

### Snowflake Step 4: Plot Skeleton (One-Page Expansion)

Expand the paragraph from Step 2 into one full page:

- ~5 paragraphs (one per major movement)
- Each paragraph: 1–3 disasters or reversals the protagonist faces, plus the final resolution
- Still high-level — identify skeleton, not every scene

Write to `{project}/plot/acts.md`.

### Snowflake Step 5: Character Synopses from Each POV

For each major character, write a 1-page synopsis of the *entire story* from their point of view:

- What do they experience? What do they know vs. not know?
- How do they change across the story?
- This often reveals plot holes and missing motivations

This step frequently forces revision of Step 4. Do it.

### Snowflake Step 6: Four-Page Plot Synopsis

Expand Step 4 into a 4-page detailed synopsis:

- Roughly one paragraph per scene-cluster / story beat
- Name every major turning point, conflict, and reversal
- Include character arc moments aligned to plot beats

Write to `{project}/plot/outline.md` (replace/expand earlier version).

### Snowflake Step 7: Deep Character Charts

Expand character summaries from Step 3 into comprehensive profiles:

- Full backstory relevant to the story
- Physical description, quirks, voice/speech patterns
- Relationship map to other characters
- Detailed arc beat-by-beat

**After Step 7, revise Steps 3–6** to bring plot and characters into full alignment.

Trigger `character-creator` for detailed character work. Update via MCP.

### Snowflake Step 8: Scene List Spreadsheet

This is the highest-value artifact of the Snowflake Method. Create `{project}/plot/scenes.md` via MCP `create_scene_list()`:

```
| # | Chapter | POV | Scene Summary | Est. Words | Status |
|---|---------|-----|---------------|------------|--------|
| 1 | Ch. 01  | Elena | Opens at the market; first signs of the anomaly | 1200 | Planned |
```

For each scene include:

- Sequential scene number
- Chapter assignment (can be approximate at this stage)
- POV character
- One-sentence scene summary (what happens + what changes)
- Estimated word count
- Status (Planned / Written / Revised / Final)

The scene list drives `chapter-writer`: load it before writing any chapter.
Scenes can be updated later via MCP `update_scene()`.

### Snowflake Step 9: Narrative Scene Descriptions (Optional)

For scenes where the writing presents specific challenges (complex backstory delivery, difficult POV, multi-character confrontation), write a paragraph-level narrative description before drafting.

This is optional — skip if the scene is straightforward.

### Snowflake Step 10: First Draft

Proceed to `chapter-writer`. The scene list from Step 8 is the primary reference.
Load scenes via MCP before writing each chapter — not the general outline.

### Snowflake Iteration Protocol

Revision between steps is **built into the method**, not a failure signal:

- After Step 3 → revise Steps 1–2
- After Step 5 → revise Steps 4 if plot holes emerge
- After Step 7 → revise Steps 3–6 to align character depth with plot
- MCP `update_field()` supports updating synopsis/outline documents without version loss
- The scene list from Step 8 is a living document — update via `update_scene()` as the draft evolves

After completing Step 8, update book status to "Plot Outlined" via MCP `update_field()`.
Then proceed to Steps 9–10 (optional scene descriptions + first draft).
Also create the tonal document (original Step 9 of the standard workflow) at this point.

## Rules

- Resolve `book_category` in Step 0a before any prerequisite load. Memoir books route to `/storyforge:plot-architect-memoir`.
- Structure serves story — pick the structure that fits, not the structure on the bestseller list.
- Every beat must have emotional PURPOSE, not just plot function.
- The "Therefore/But" test: every event must cause the next. "And then" sequencing means the plot is just a list.
- Midpoint is NOT halfway through the events — it's the REVERSAL that changes everything.
- Foreshadowing map is mandatory — every climax payoff needs a prior plant. Deus ex machina is a craft failure.
