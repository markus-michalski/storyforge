---
name: plot-architect-memoir
description: |
  Memoir narrative-arc architect. Picks one of four structure types
  (chronological / thematic / braided / vignette) and shapes the chapter
  spine per that type.
  Use when: (1) `book_category == "memoir"` AND user says "Plot",
  "Handlung", "Struktur", "narrative arc", "Aufbau", (2) After
  book-conceptualizer (memoir mode) has populated the `## Scope` section.
  Fiction books → use `/storyforge:plot-architect` instead.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug>"
---

# Plot Architect (Memoir)

This skill is the memoir variant of `plot-architect`, split out per Issue #126 so memoir-only sessions never load the fiction structure catalog (3-Act, Hero's Journey, Save the Cat, Snowflake) and fiction-only sessions never load the memoir structure types.

The fiction structure catalog does not apply here. Memoir picks one of four structure types and shapes the chapter spine per that type. There is no antagonist phase, no foreshadowing map (memoir does not "plant payoffs" — lived events do not work that way), no subplot architecture.

## Step 0a — Verify memoir mode

Before any other prerequisite load:

1. **Load book data** via MCP `get_book_full(slug)`.
2. Read `book_category`. If it is `fiction` (or missing), stop and tell the user:
   > *This book's `book_category` is `fiction`. Use `/storyforge:plot-architect` for fiction structure work. (To shape this as a memoir, set `book_category: memoir` in the README frontmatter first.)*
3. Otherwise surface a one-line note: *"Working in memoir mode — picking a structure type (chronological / thematic / braided / vignette), no antagonist phase, the chapter spine is shaped by the chosen structure."*

## Prerequisites — MANDATORY LOADS

- **Book data** via MCP `get_book_full()`. **Why:** premise, theme, scope (Phase 3 of `book-conceptualizer` #60), people roster — the structure type must serve what the conceptualizer already locked in.
- **Author profile** via MCP `get_author()` if assigned. **Why:** memoirist's voice and tonal preferences inform structure-type fit.
- **Memoir craft** from `book_categories/memoir/craft/` (resolve via MCP `get_book_category_dir("memoir")`):
  - `memoir-structure-types.md` — **Why:** the four-type catalog with when-it-works / when-it-fails / discipline-required notes; this is the single source of truth for Step M2.
  - `scene-vs-summary.md` — **Why:** the structure type drives scene/summary ratio decisions in the chapter spine (Step M5).
  - `emotional-truth.md` — **Why:** the structure type must serve the felt sense of the lived material, not impose a fictional plot shape on it.
  - `memoir-anti-ai-patterns.md` — **Why:** prevents drift toward "looking back I realize" framing in the through-line statement.
- Read `{project}/README.md` `## Scope` (Phase 3 of `book-conceptualizer` #60) — the time window, structural cast, and exclusions are inputs to structure-type choice.
- Read `{project}/people/INDEX.md` if real-people profiles already exist (`character-creator` memoir mode #59) — structure-type cadence in Step M3 may vary by who carries which thread.

## Workflow

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

Same shape as fiction's tonal document — interview the user, populate the Tonal Arc per structure type (a chronological arc tone-shifts across the period; a thematic arc may keep tone steady within chapters and shift between them; braided demands two distinct tonal palettes; vignette tone may shift per vignette).

Steps:

1. **Interview the user** (use AskUserQuestion or conversational flow):
   - What should this memoir feel like to read? (overall emotional texture)
   - Which memoirists or works should we channel for tone? Which to avoid?
   - Are there non-negotiable rules? (e.g. no retrospective wisdom voice, no therapy vocabulary on past-self)
   - What would be a WARNING sign that the tone is drifting?
2. **Populate the Tonal Arc** based on the chosen structure type.
3. **Define the Litmus Test** — 5-6 yes/no questions the chapter-writer answers after every chapter. Specific to *this* memoir, not generic craft questions.
4. **Non-Negotiable Rules** — Memoir-specific prose rules beyond the author profile's general style.
5. Write the completed document to `{project}/plot/tone.md`.

Update book status to "Plot Outlined" via MCP `update_field()`.

## Rules

- The structure type is one of `chronological`, `thematic`, `braided`, `vignette`. Persist the choice via MCP `set_memoir_structure_type` — never improvise a fifth type. Hybrids belong in the prose, not the metadata.
- The `## Scope` section from `book-conceptualizer` (#60) gates structure choice. Without it, route the user back to the conceptualizer; do not invent a scope here.
- Every memoir chapter spine entry must touch the through-line — chapters that drift away from the through-line are scope-failure dressed as "more material".
- Re-read the failure-mode notes for the chosen structure (in `memoir-structure-types.md`) before drafting Step M5. Structure choice without failure-mode awareness is structure-shopping.
- No foreshadowing map. Memoir does not plant payoffs — lived events do not arrange themselves around climaxes. Use thematic recurrence and image-rhyme instead, captured in the through-line and Step M3 mapping.
- Structure serves story — pick the structure that fits the lived material, not the structure with the prettier examples.
