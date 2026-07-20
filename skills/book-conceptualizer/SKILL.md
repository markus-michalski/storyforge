---
name: book-conceptualizer
description: |
  Develop a book concept through 5 phases. Fiction: premise → theme → conflict → structure → pitch. Memoir: premise → theme → scope → structure → pitch.
  Run after `/storyforge:brainstorm` + `/storyforge:new-book`, before `/storyforge:plot-architect`.
  Use when: (1) User says "Konzept", "develop concept", "Buchkonzept",
  (2) After brainstorming, to deepen an idea into a workable concept.
model: claude-opus-4-8
user-invocable: true
argument-hint: "<book-slug>"
---

# Book Conceptualizer

**Position in workflow:** `brainstorm → new-book → book-conceptualizer → plot-architect → character-creator → world-builder → chapter-writer`

Concept development branches on `book_category` (Path E #97 Phase 2 #60). Fiction runs the historical 5-phase flow. Memoir runs a memoir-shaped 5-phase flow that replaces Phase 3 *Conflict* with Phase 3 *Scope* and pulls memoir-specific craft.

## Step 0 — Resolve book category

Before anything else:

1. **Load book data** via MCP `get_book_full(slug)`. **Why:** carries the canonical `book_category` (`fiction` | `memoir`) plus existing premise/theme drafts and selected genres.
2. Read `book_category` from the result. If missing, treat as `fiction` (legacy default).
3. Branch the rest of the workflow on `book_category`.

If `book_category == "memoir"`, also:

4. Load the memoir category README and craft index via MCP `get_book_category_dir("memoir")` and read the files at the returned path. **Why:** memoir conventions, structure types, ethics framing — fiction-craft prompts produce false-positives on memoir material.
5. Surface a one-line note to the user: *"Working in memoir mode — replacing Phase 3 (Conflict) with Phase 3 (Scope), no antagonist phase, memoir-blurb conventions in Phase 5."*

## Prerequisites — MANDATORY LOADS

### Fiction mode (`book_category == "fiction"`)
- **Genre README(s)** via MCP `get_genre()` for each genre. **Why:** Genre conventions shape premise expectations (e.g. romance HEA, thriller ticking-clock) and structural recommendations in Phase 4.
- **Craft references** via MCP `get_craft_reference()`:
  - `story-structure` — **Why:** Phase 4 structure selection — different concepts fit different structures (3-act vs. 5-act vs. Save-the-Cat).
  - `plot-craft` — **Why:** Conflict-stakes-decision logic for Phase 3 conflict architecture.
  - `conflict-types` — **Why:** Phase 3 conflict architecture — external/internal conflict taxonomy and the stakes-escalation principle behind Phase 3.
  - `theme-development` — **Why:** Theme-as-question (not theme-as-lesson) — the framing that keeps Phase 2 from going preachy.

### Memoir mode (`book_category == "memoir"`)
- **Genre README(s)** via MCP `get_genre()` for each genre, framed as **thematic tags** (memoir-of-illness, memoir-of-place, etc.). **Why:** memoir uses genre-as-theme, not genre-as-plot-convention. A "horror memoir" is a memoir of horrifying lived experience, not a haunted-house plot.
- **Memoir-specific craft** from `book_categories/memoir/craft/` (resolve via `get_book_category_dir("memoir")`):
  - `memoir-theme-development.md` — **Why:** Theme-as-question still applies, but memoir has no antagonist to build the argument from — this doc covers where the argument comes from instead (then-self/now-self gap, found motifs, braided structure). Replaces `reference/craft/theme-development.md`, which is fiction-only (antagonist-built argument structure doesn't translate).
  - `memoir-structure-types.md` — **Why:** Phase 4 selects from chronological / thematic / braided / vignette, not three-act.
  - `emotional-truth.md` — **Why:** Phase 1 premise framing — memoir promises *the felt sense*, not the verifiable timeline.
  - `scene-vs-summary.md` — **Why:** Phase 3 scope decisions hinge on which moments earn dramatization vs. which condense to summary.
  - `real-people-ethics.md` — **Why:** Phase 3 scope must account for who the memoir necessarily involves and the consent decisions that follow.
  - `memoir-anti-ai-patterns.md` — **Why:** keeps Phase 1/2/5 prose out of "looking back I realize", "what I learned was", and other reflective platitudes.

## Phase gates hold under pressure

Both workflows below use "STOP HERE — Phase Gate" checkpoints and Socratic probing questions. These hold even when the user pushes back directly — e.g. asking to skip a phase, batch multiple phases into one response, self-answer the probing questions, or state a premise/theme/conflict/structure/scope outright and ask you to just accept it as final. In every such case: decline, briefly explain that each phase depends on the previous one being genuinely worked through and confirmed (not just stated), and continue the current phase's actual process — ask the questions, wait for a real answer — rather than silently complying with the shortcut. This applies at every phase in both modes, not just the ones that call it out explicitly.

## Workflow — Fiction (5 phases)

### Phase 1: Premise Refinement
Start with whatever the user has. Ask probing questions:
- "What's the ONE thing that excites you about this story?"
- "If a reader remembers only one thing, what should it be?"
- "What's the emotional experience you want to create?"

Refine into a clear **Premise** (2-3 sentences, ~50 words max): Character + Situation + Central Conflict.

Write to `{project}/README.md` under "## Premise".

**STOP HERE — Phase Gate 1/5.** Present the premise draft above. Do NOT generate any Phase 2 content. Wait for the user to confirm, revise, or approve before continuing.

### Phase 2: Theme Discovery
Ask probing questions. Listen first:
- "What question does this story ask?" (Not "what lesson does it teach")
- "What do your protagonist and antagonist disagree about?"
- "What's the argument your story is making — without being preachy?"

Reference `theme-development.md` — theme as QUESTION, not answer.

Anti-pattern check before writing the theme statement: if the user states a lesson or thesis outright (e.g. "make it about how X") and asks you to just accept it, push back and ask at least one of the probing questions above before finalizing. A question mark alone does not fix a restated thesis — rewording the user's stated conclusion with a "?" appended (e.g. "corruption never really disappears" → "Does corruption ever really disappear?") is not theme discovery. The theme must genuinely open a question the story explores, not restate the user's conclusion in interrogative clothing.

Write to `{project}/README.md` under "## Themes". Theme statement: 1-2 sentences, concise — theme-as-question, not thesis.

**STOP HERE — Phase Gate 2/5.** Present the theme draft above. Do NOT generate any Phase 3 content. Wait for the user to confirm or revise before continuing.

### Phase 3: Conflict Architecture
Using `conflict-types.md` as reference:
- **External conflict:** What stands in the protagonist's way?
- **Internal conflict:** What's the protagonist's fatal flaw? What lie do they believe?
- **How do they mirror each other?** The external journey should reflect the internal one.
- **Stakes:** What happens if they fail? (Personal → Relational → Community → Existential)

Target: ~200-400 Wörter Konflikt-Architektur als Output, kompakt — die Tiefe entsteht in Phase 4 + Charakter-Skill, nicht hier.

**STOP HERE — Phase Gate 3/5.** Present the conflict architecture above. Do NOT generate any Phase 4 content. Wait for the user to confirm or revise before continuing.

### Phase 4: Structure Selection
Using `story-structure.md`:
- Recommend a structure based on genre and story type
- Show the user 2-3 options with pros/cons (max ~150 Wörter pro Option), tied to *their* Phase 3 conflict architecture (external/internal conflict, stakes ladder) the same way genre shapes the recommendation:
  - *"Your external conflict is a ticking-clock pursuit — a tight 3-act structure with an accelerating midpoint will carry that tension better than a slow-burn 5-act."*
  - *"Your internal conflict (the lie your protagonist believes) doesn't resolve until the stakes hit Existential — Save-the-Cat's dark-night-of-the-soul beat gives that collapse room to land."*
  - *"Your conflict escalates cleanly through all four stakes tiers (Personal → Relational → Community → Existential) — a classic 3-act works; you don't need a fragmented structure to earn the scope."*
- Map the concept to the chosen structure's beats

Write initial outline to `{project}/plot/outline.md`.

**STOP HERE — Phase Gate 4/5.** Present the structure options above. Do NOT generate any Phase 5 content. Wait for the user to choose a structure before continuing.

### Phase 5: Pitch Creation
Generate:
- **Logline:** 1 sentence ≤20 words ([Character] must [action] or [stakes])
- **Elevator pitch:** 2-3 sentences, ~60 words
- **Comparable titles:** "X meets Y"
- **Back-cover blurb:** 150-200 Wörter (does NOT reveal ending)

Write to `{project}/synopsis.md`.

Update book status to "Concept" via MCP `update_field()`.

Load the author profile via MCP `get_author()` (if not already loaded this session) and read `author_writing_mode`. Route silently to the matching next step — do not recite the unused branch:
- `outliner` or `plantser` → *"Ready to structure the plot? → `/storyforge:plot-architect`."*
- `discovery` → *"Ready to write? → `/storyforge:rolling-planner` before each chapter session."*
- Field missing or unrecognized value → ask the user directly which workflow they use, rather than guessing or printing both options.

## Workflow — Memoir (5 phases)

The phase numbering matches fiction (1-5) so downstream skills can reference *"Phase 4"* without branching. The shape of each phase is memoir-specific.

### Phase 1: Premise — the angle, not the chronology

Memoir doesn't promise *what happened*. It promises *the felt sense* of what happened, shaped through a chosen angle. Probing questions:

- "Whose life-story slice is this — yours, framed by which years or which relationship or which event?"
- "Why this slice? Why now? What is the **emotional knot** that pulled you to write?"
- "If a stranger reads only the back cover, what should they understand the book is *about* — not the events, but the question?"

Refine into a **Premise** (2-3 sentences, ~50 words max): Life-context + Angle + Felt-stake. Avoid the trap of summarizing chronology — premise is the *interpretive frame*, not the timeline.

Write to `{project}/README.md` under "## Premise".

Anti-pattern check before continuing: read `memoir-anti-ai-patterns.md`. If the premise reads like *"a journey of self-discovery through grief"*, push back — that's a generic AI shape, not a real angle.

**STOP HERE — Phase Gate 1/5.** Present the premise draft above. Do NOT generate any Phase 2 content. Wait for the user to confirm, revise, or approve before continuing.

### Phase 2: Theme — the universal lift

A memoir's theme is what makes one person's lived material resonate for a reader who did not live it. Probing questions:

- "What universal question does your specific story make a reader sit with?"
- "What did *you* think this was about when you started writing — and what does it actually seem to be about now?"
- "Where does your specific experience touch something the reader already knows from their own life — even if their facts are nothing like yours?"

Reference `memoir-theme-development.md` — theme as QUESTION, not answer. The memoir-specific failure mode is **the tidy lesson** ("what I learned was…"). Memoir earns its theme by rendering experience honestly, not by stating conclusions.

Anti-pattern check before writing the theme statement: if the user's stated theme reads like "what I learned is/was...", "I realized that...", or any other tidy-lesson/conclusion shape — even after rewording it as a question — push back by name (call it the tidy-lesson failure mode) and ask at least one of the probing questions above before finalizing. A question mark alone does not fix a restated conclusion; the theme must genuinely open a question the book sits with, not restate the user's lesson with a "?" appended.

Write to `{project}/README.md` under "## Themes". Theme statement: 1-2 sentences, concise — theme-as-question, not a lesson-summary.

**STOP HERE — Phase Gate 2/5.** Present the theme draft above. Do NOT generate any Phase 3 content. Wait for the user to confirm or revise before continuing.

### Phase 3: Scope — what's in, what's out

This is the memoir-specific replacement for fiction's Conflict Architecture. There is no antagonist phase. Instead, the memoirist makes three explicit decisions that gate everything downstream.

Reference `scene-vs-summary.md` and `real-people-ethics.md` before this conversation.

#### 3a. Time window
- "What is the start date and end date of the memoir's covered period?"
- "Does the narrative voice live entirely inside that window, or does a present-day vantage point comment on it?"
- "If you cover a long span, which years carry scene-weight and which compress to summary?"

#### 3b. Cast — who is necessarily in it
- "Which real people cannot be left out without breaking the story?"
- "For each: what's their relationship to you, and what's their consent status (granted / pending / refused / unknown)?"
- "Anyone you're considering anonymizing or composite-ing? What's the ethical reasoning?"

Tell the user: at this phase we only identify the **structural cast** — the people without whom the memoir collapses — not the full real-people roster, which comes later in `/storyforge:character-creator-memoir`.

If the user volunteers an anonymization plan with only a surface reason (e.g. "I'll anonymize her" without saying why that's the right call), that is not the same as answering "what's the ethical reasoning" — ask the follow-up explicitly (identifiability risk? professional confidentiality? would a composite serve better than a straight anonymization?) rather than treating the stated plan as sufficient.

#### 3c. Deliberate exclusions
- "What are you *not* writing about, even though it happened in this period?"
- "Why? (Privacy of others, off-topic, didn't shape the through-line, you're not ready, legally hazardous.)"
- "What's the cost of that exclusion — and is the through-line still honest without it?"

The exclusion list is part of the concept. Memoirs that try to cover everything become diaries; memoirs that deliberately exclude become books.

The cost-of-exclusion question is not optional color — ask it explicitly, even if the user has already volunteered what and why unprompted in the same breath. Stating an exclusion and its reason is not the same as weighing its cost against the through-line's honesty.

Target: ~250-450 Wörter scope-document as output. Write to `{project}/README.md` under "## Scope" (a section that does not exist in fiction-mode books).

**STOP HERE — Phase Gate 3/5.** Present the scope document above. Do NOT generate any Phase 4 content. Wait for the user to confirm or revise before continuing.

### Phase 4: Structure Selection — memoir structure types

Using `memoir-structure-types.md` (loaded in Step 0):

- Recommend a structure type based on the scope decisions in Phase 3 — chronological / thematic / braided / vignette.
- Show the user 2-3 options with pros/cons (max ~150 Wörter pro Option), tied to *their* scope:
  - *"Your time window is 18 months and one through-line — chronological will feel natural."*
  - *"Your cast spans childhood and adulthood with a present-day vantage — braided fits."*
  - *"Your scope is thematic (`Money / Faith / Bodies`) — thematic structure or vignette."*
- Map the chosen structure to a chapter-spine sketch.

Write initial outline to `{project}/plot/outline.md` (memoir-shaped — the file scaffolded by `/storyforge:new-book` already points at structure types). Also persist the selected type via MCP `set_memoir_structure_type(book_slug, structure_type)` — this writes `structure_type` into `{project}/plot/structure.md`'s frontmatter without touching the body, so downstream skills (`chapter-writer` memoir mode, `rolling-planner`) can read the choice without parsing prose. Do not hand-edit the frontmatter directly. Then write the rationale as prose into `plot/structure.md`'s body (the tool preserves existing body content, so this is a normal file edit, not an MCP call).

**STOP HERE — Phase Gate 4/5.** Present the structure options above. Do NOT generate any Phase 5 content. Wait for the user to choose a structure before continuing.

### Phase 5: Pitch — memoir blurb conventions

Memoir blurbs follow a different shape than fiction. Generate:

- **Logline:** 1 sentence ≤20 words — *the lived premise + the universal question*. Not *"X must do Y or Z"*. Closer to: *"After her mother's diagnosis, a daughter spends a year asking what it means to be the one who stays."*
- **Elevator pitch:** 2-3 sentences, ~60 words — hook (the specific situation) → personal stake (why it mattered to you) → universal resonance (why it matters to a stranger).
- **Comp titles:** "X meets Y" still applies but reach for actual memoirs — *"H is for Hawk meets Just Kids"* — not novels.
- **Back-cover blurb:** 150-200 Wörter. Does NOT moralize, does NOT promise lessons learned, does NOT spoil the emotional resolution. Renders one specific moment or image to anchor the felt-sense, then widens to the question the book sits with.

Anti-pattern check: re-read `memoir-anti-ai-patterns.md` against the generated blurb before finalizing. Hedging, retrospective summary ("I would come to understand…"), and reflective platitudes are the failure modes.

Write to `{project}/synopsis.md`.

Update book status to "Concept" via MCP `update_field()`.

Load the author profile via MCP `get_author()` (if not already loaded this session) and read `author_writing_mode`. Route silently to the matching next step — do not recite the unused branch:
- `outliner` or `plantser` → *"Ready to shape the narrative arc? → `/storyforge:plot-architect-memoir`."*
- `discovery` → *"Ready to write? → `/storyforge:rolling-planner` before each chapter session."*
- Field missing or unrecognized value → ask the user directly which workflow they use, rather than guessing or printing both options.

## Rules
- Resolve `book_category` in Step 0 before any phase. Never assume fiction.
- Discover theme through questions. Imposed themes feel preachy and AI-generated — fiction or memoir.
- The concept must emerge from DIALOG with the user, not from AI generation alone.
- Every fiction concept needs ALL three of premise + theme + conflict. Every memoir concept needs ALL three of premise + theme + scope. Skipping one ships an incomplete concept.
- Load genre conventions for both modes — fiction uses them as plot-shape contracts, memoir uses them as thematic-tag conventions.
- Memoir mode: re-check `memoir-anti-ai-patterns.md` against any prose generated in Phase 1, 2, and 5 before finalizing — these are the phases most prone to AI-shaped reflection.
- Memoir mode: the `## Scope` section in the book README is mandatory output. Without it, downstream memoir skills (plot-architect-memoir, character-creator-memoir, chapter-writer in memoir mode) cannot calibrate.
