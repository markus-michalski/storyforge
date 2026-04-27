---
name: plot-architect
description: |
  Fiction: structure the plot with acts, beats, turning points, character arcs.
  Memoir: shape narrative arc by structure type (chronological / thematic / braided / vignette).
  Use when: (1) User says "Plot", "Handlung", "Struktur", "outline", "narrative arc",
  (2) After concept is developed, before character / people creation.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug>"
---

# Plot Architect

This skill branches on `book_category` (Path E #97 Phase 2 #58). Fiction runs the historical Step-0..9 workflow with the standard structure catalog (3-Act, Hero's Journey, Save the Cat, etc.). Memoir runs a memoir-aware narrative-arc workflow that picks one of four structure types and shapes the chapter spine per that type.

## Step 0a — Resolve book category

Before any other prerequisite load:

1. **Load book data** via MCP `get_book_full(slug)`.
2. Read `book_category`. Treat missing as `fiction`.
3. Branch the workflow on `book_category`. The fiction and memoir flows are non-overlapping — no acts/beats for memoir, no structure-type for fiction.

If `book_category == "memoir"`, surface a one-line note: *"Working in memoir mode — picking a structure type (chronological / thematic / braided / vignette), no antagonist phase, the chapter spine is shaped by the chosen structure."*

## Prerequisites — MANDATORY LOADS

### Fiction mode (`book_category == "fiction"`)
- **Book data** via MCP `get_book_full()`. **Why:** Existing premise, theme, characters, writing-mode — Step 0b branches on `effective_author_writing_mode` and Step 1 builds on existing concept output.
- **Author profile** via MCP `get_author()` if assigned. **Why:** The author profile may carry structural preferences (e.g. "always uses 5-act tragic arcs") that bias the recommendation in Step 2.
- **Genre README(s)** via MCP `get_genre()`. **Why:** Genre dictates expected structures (romance = 3-Act + HEA, thriller = Fichtean) and beat conventions.
- **Craft references** via MCP `get_craft_reference()`:
  - `story-structure` — **Why:** The structure catalog Step 2 picks from — without it, recommendations default to generic 3-Act.
  - `plot-craft` — **Why:** Beats, foreshadowing, cause-effect logic — Step 3 (beat mapping) and Step 5 (foreshadowing map) are built on this.
  - `tension-and-suspense` — **Why:** Stakes, cliffhangers, pacing — what makes the chapter-by-chapter plan in Step 7 actually keep readers turning pages.
  - `conflict-types` — **Why:** Escalation patterns and moral dilemma structures — Step 4 subplot architecture depends on knowing how conflicts compound.

### Memoir mode (`book_category == "memoir"`)
- **Book data** via MCP `get_book_full()`. **Why:** premise, theme, scope (Phase 3 of `book-conceptualizer` #60), people roster — the structure type must serve what the conceptualizer already locked in.
- **Author profile** via MCP `get_author()` if assigned. **Why:** Memoirist's voice and tonal preferences inform structure-type fit.
- **Memoir craft** from `book_categories/memoir/craft/` (resolve via MCP `get_book_category_dir("memoir")`):
  - `memoir-structure-types.md` — **Why:** the four-type catalog with when-it-works / when-it-fails / discipline-required notes; this is the single source of truth for Step M2.
  - `scene-vs-summary.md` — **Why:** the structure type drives scene/summary ratio decisions in the chapter spine (Step M5).
  - `emotional-truth.md` — **Why:** the structure type must serve the felt sense of the lived material, not impose a fictional plot shape on it.
  - `memoir-anti-ai-patterns.md` — **Why:** prevents drift toward "looking back I realize" framing in the through-line statement.
- Read `{project}/README.md` `## Scope` (Phase 3 of `book-conceptualizer` #60) — the time window, structural cast, and exclusions are inputs to structure-type choice.
- Read `{project}/people/INDEX.md` if real-people profiles already exist (`character-creator` memoir mode #59) — structure-type cadence in Step M3 may vary by who carries which thread.

## Workflow — Fiction

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

3. **Define the Litmus Test** — 5-6 yes/no questions the chapter-writer answers after every chapter.
   These should be specific to THIS book, not generic craft questions.

4. **Non-Negotiable Rules** — Book-specific prose rules beyond the author profile's general style.

5. Write the completed document to `{project}/plot/tone.md`.

This document guards against tonal drift during long-form writing. Without it, books tend to collapse into generic "literary" mode after ~15 chapters.

---

## Workflow — Memoir

The fiction structure catalog (3-Act, Hero's Journey, etc.) does not apply. Memoir picks one of four structure types and shapes the chapter spine per that type. There is no antagonist phase, no foreshadowing map (memoir does not "plant payoffs" — lived events do not work that way), no subplot architecture.

The memoir flow has 6 steps. Step M5 preserves the chapter-spine concept; Step M6 keeps the timeline anchor (memoir uses real chronology, but the timeline file still anchors story-time for `chapter-writer`).

### Step M0: Read existing concept

- Read `{project}/README.md` for premise, theme, **and the `## Scope` section** that `book-conceptualizer` (#60) wrote in Phase 3 (time window, structural cast, deliberate exclusions). The scope decisions gate Step M2 — a memoir whose scope is "thematic exclusions across decades" cannot honestly choose chronological.
- If `## Scope` is missing, stop and route to `/storyforge:book-conceptualizer` first. Memoir plot-architect builds on scope; building it without scope produces structure-shopping, not structure-choosing.
- Read `{project}/plot/outline.md` for any existing through-line draft (the `book-conceptualizer` Phase 4 sketch — Step M3 below refines it).
- Read `{project}/people/INDEX.md` if it exists (post-`character-creator` memoir mode #59).

### Step M1: Confirm or refine the through-line

The through-line is the **single sentence** that says what the memoir is *about* — not the events, but the question or claim. The conceptualizer's Phase 1 premise is the raw material; the through-line is the operational form that drives structure choice.

Ask the user:

- *"Read your premise back to yourself. What is the one sentence that, if a stranger asked what your memoir is about, you would say?"*
- *"Does that sentence point at a time-window question (chronological-friendly), a conceptual question (thematic-friendly), a then-vs-now question (braided-friendly), or a mosaic-of-fragments question (vignette-friendly)?"*

Write the through-line to `{project}/plot/outline.md` under "## Through-line". This is what the chapter spine in Step M5 will serve.

**Wait for user confirmation of the through-line before Step M2. Structure choice cascades from this sentence.**

### Step M2: Choose structure type

Reference `memoir-structure-types.md` (loaded as prerequisite). Use AskUserQuestion with the four options. Show concrete pros/cons rooted in *this user's* scope and through-line — generic descriptions are not enough.

| Type | Picks itself when… |
|------|--------------------|
| `chronological` | Period is bounded and short, causality is tight, suspense of not-yet-knowing is part of the experience |
| `thematic` | Central question is conceptual not temporal, multiple decades inform it, memory clusters by topic |
| `braided` | Past + present-day vantage comment on each other, dramatic irony is structural |
| `vignette` | Lived material is fragmented in memory, mosaic accumulation is the meaning, each scene bears weight alone |

Reference the **decision tree** at the bottom of `memoir-structure-types.md` if the user is torn between two types — pick the one whose **failure modes you can avoid**, not the one with the prettier examples.

After the user picks, persist the choice via MCP `set_memoir_structure_type(book_slug, structure_type)`. The tool validates against the four allowed values and writes to `plot/structure.md` frontmatter so downstream skills (`chapter-writer` memoir mode #57, `rolling-planner`) can read it.

**Wait for the user's structure-type selection before Step M3.** Every downstream step branches on this choice.

### Step M3: Map the narrative arc per structure type

The arc-mapping shape depends on the structure type. Pick the matching sub-step:

#### M3-chronological — Time-bounded arc

- **Begin point** — *not* the chronological start, the **narrative** start. *In medias res* is the default. Where does the reader enter?
- **Hinge moments** — name 3–6 events that turned the period. Compress aggressively between them.
- **End point** — where does the narrative close? Has the question the through-line raises been *answered*, *re-framed*, or deliberately *left open*?
- **Compression strategy** — for each gap between hinges, decide: paragraph / scene cluster / single image / cut.

Write to `{project}/plot/outline.md` under "## Narrative arc — chronological".

#### M3-thematic — Conceptual chapters with a through-line

- **Theme list** — typically 5–9 concrete themes. *Money / Faith / Bodies / Hunger / Silence* — concrete, not abstract. Kill *Truth / Beauty / Love* and pick substitutes.
- **Through-line thread** — what runs across the themes? A relationship, a place, a recurring question. Visible by Chapter 3 or the reader bails.
- **Argumentative order** — chapter sequence is an argument, not a list. Why does Chapter 5 need to come *after* Chapter 4?
- **Scene-spine per theme** — each thematic chapter still needs scene work; theme alone is essay-shaped.

Write to `{project}/plot/outline.md` under "## Narrative arc — thematic" (theme list + through-line) and "## Argument order" (chapter sequence rationale).

#### M3-braided — Two threads in conversation

- **Thread A** — name it (e.g. "the year of the diagnosis"). Specify timeframe and POV.
- **Thread B** — name it (e.g. "present-day reckoning"). Specify timeframe and what vantage point it carries.
- **Cadence** — strict alternation? weighted (e.g. 2:1 toward Thread A)? variable per chapter cluster? Pick a pattern and commit.
- **Transition principle** — image / theme / echo / question. Never "meanwhile, decades later". Define the working principle and apply it consistently.
- **Earn-test** — for each thread, write one sentence saying what would be lost if it were cut. Vague answers mean the braid is decorative; one thread should probably go.

Write to `{project}/plot/outline.md` under "## Narrative arc — braided".

#### M3-vignette — Mosaic with a through-line

- **Through-line** — recurring image, place, relationship, unanswered question. Visible by Chapter 3.
- **Vignette inventory** — list 12–25 candidate vignettes (more than you'll use). For each: one-line summary + emotional weight + which through-line element it touches.
- **Selection** — cut to 8–18 strong vignettes. Weak vignettes stop the read; vignette memoirs cannot carry filler.
- **Order as argument** — vignettes are arranged, not collected. The order is craft. Group by theme, contrast, or cumulative weight — the pattern is itself a craft choice.

Write to `{project}/plot/outline.md` under "## Narrative arc — vignette" (through-line + ordered vignette list).

### Step M4: Identify the structure-specific failure modes

Re-read the **failure modes** section of the chosen structure in `memoir-structure-types.md`. For each failure mode, write one sentence to `{project}/plot/outline.md` under "## Structure failure-mode watch" stating how *this specific memoir* will avoid it. This is the prose equivalent of Phase 4 from `book-conceptualizer` — committing to discipline, in writing, before drafting.

Examples:

- Chronological → *"Decades-long span: I will compress 2003-2010 to two paragraphs in Chapter 4. The story is the diagnosis year, not my whole adulthood."*
- Thematic → *"Module risk: Chapter 5 (Money) and Chapter 7 (Bodies) both touch the same hospital scene. I will plant the recurring image in Chapter 5 and pay it off in Chapter 7 to thread them."*
- Braided → *"Lazy transition risk: I will not use date-stamps as crutches. Every cut carries an image bridge."*
- Vignette → *"Anecdote-collection risk: by Vignette 4, the reader will know the through-line question. If they don't, the order is wrong."*

### Step M5: Chapter spine

The fiction concept of a chapter spine — the running list of chapters with title, focus, and rough word target — is preserved for memoir. The shape varies per structure type:

| Type | Chapter spine shape |
|------|---------------------|
| `chronological` | Linear chapter list with date or season anchors per chapter, hinge events flagged |
| `thematic` | Chapter list = theme list (one theme per chapter, or a theme cluster spanning 2–3 chapters) |
| `braided` | Chapter list with thread tags (A / B / both) and cadence pattern noted |
| `vignette` | Vignette list with grouping/clustering noted; "chapters" may bundle 2–4 short vignettes |

For each chapter:

- Number + working title
- Focus (event / theme / vignette / braid pair)
- Through-line touchpoint — how this chapter advances the through-line
- POV vantage — past-self, present-self, or both (relevant for chronological + braided especially)
- Rough word target

Offer to create chapter directories via MCP `create_chapter()` once the spine is locked.

Write the chapter spine to `{project}/plot/outline.md` under "## Chapter spine".

### Step M6: Initialize timeline + tonal document

These two universal steps still apply to memoir.

#### M6a: Timeline anchor

Memoir uses **real chronology** for `plot/timeline.md`, not invented story-days. But the file still serves the same purpose: anchoring story-time for `chapter-writer` so cross-chapter temporal references stay consistent.

1. Ask the user: *"What is the real start date (or month/year) of the period your memoir covers?"*
2. Establish the **Anchor Point** as that real date. Story Day 1 = first scene's date.
3. Pre-fill the Event Calendar with the hinge moments / themed-chapter clusters / vignette dates from Step M3. Mark all entries `[PLANNED]`.
4. For braided memoir, the timeline tracks **both** threads — note Thread A and Thread B dates separately.

This step is MANDATORY. A memoir without a timeline anchor produces cross-chapter time drift the same way fiction does.

#### M6b: Tonal document

Same as fiction Step 9 — interview the user, populate the Tonal Arc per structure type (a chronological arc tone-shifts across the period; a thematic arc may keep tone steady within chapters and shift between them; braided demands two distinct tonal palettes; vignette tone may shift per vignette).

Write to `{project}/plot/tone.md`.

Update book status to "Plot Outlined" via MCP `update_field()`.

---

## Snowflake Workflow

*Use this section instead of Steps 3–8 when the user selects the Snowflake Method (fiction only).*

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

---

## Rules

### Universal
- Resolve `book_category` in Step 0a before any prerequisite load.
- Structure serves story — pick the structure that fits, not the structure on the bestseller list.

### Fiction
- Every beat must have emotional PURPOSE, not just plot function.
- The "Therefore/But" test: every event must cause the next. "And then" sequencing means the plot is just a list.
- Midpoint is NOT halfway through the events — it's the REVERSAL that changes everything.
- Foreshadowing map is mandatory — every climax payoff needs a prior plant. Deus ex machina is a craft failure.

### Memoir
- The structure type is one of `chronological`, `thematic`, `braided`, `vignette`. Persist the choice via MCP `set_memoir_structure_type` — never improvise a fifth type. Hybrids belong in the prose, not the metadata.
- The `## Scope` section from `book-conceptualizer` (#60) gates structure choice. Without it, route the user back to the conceptualizer; do not invent a scope here.
- Every memoir chapter spine entry must touch the through-line — chapters that drift away from the through-line are scope-failure dressed as "more material".
- Re-read the failure-mode notes for the chosen structure (in `memoir-structure-types.md`) before drafting Step M5. Structure choice without failure-mode awareness is structure-shopping.
- No foreshadowing map. Memoir does not plant payoffs — lived events do not arrange themselves around climaxes. Use thematic recurrence and image-rhyme instead, captured in the through-line and Step M3 mapping.
