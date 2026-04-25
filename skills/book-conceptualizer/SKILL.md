---
name: book-conceptualizer
description: |
  Develop a book concept through 5 phases: premise, theme, conflict, structure, pitch.
  Use when: (1) User says "Konzept", "develop concept", "Buchkonzept",
  (2) After brainstorming, to deepen an idea into a workable concept.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug>"
---

# Book Conceptualizer

## Prerequisites — MANDATORY LOADS
- Book project must exist (via `/storyforge:new-book`).
- **Book data** via MCP `get_book_full()`. **Why:** Project state, genre selection, existing premise/theme drafts — anchors the conversation in what already exists.
- **Genre README(s)** via MCP `get_genre()` for each genre. **Why:** Genre conventions shape premise expectations (e.g. romance HEA, thriller ticking-clock) and structural recommendations in Phase 4.
- **Craft references** via MCP `get_craft_reference()`:
  - `story-structure` — **Why:** Phase 4 structure selection — different concepts fit different structures (3-act vs. 5-act vs. Save-the-Cat).
  - `plot-craft` — **Why:** Conflict-stakes-decision logic for Phase 3 conflict architecture.
  - `theme-development` — **Why:** Theme-as-question (not theme-as-lesson) — the framing that keeps Phase 2 from going preachy.

## Workflow — 5 Phases

### Phase 1: Premise Refinement
Start with whatever the user has. Ask probing questions:
- "What's the ONE thing that excites you about this story?"
- "If a reader remembers only one thing, what should it be?"
- "What's the emotional experience you want to create?"

Refine into a clear **Premise** (2-3 sentences): Character + Situation + Central Conflict.

Write to `{project}/README.md` under "## Premise".

**Wait for user response and explicit premise approval. Do not proceed to Phase 2 without input.**

### Phase 2: Theme Discovery
Ask probing questions. Listen first:
- "What question does this story ask?" (Not "what lesson does it teach")
- "What do your protagonist and antagonist disagree about?"
- "What's the argument your story is making — without being preachy?"

Reference `theme-development.md` — theme as QUESTION, not answer.

Write to `{project}/README.md` under "## Themes".

**Wait for user response. Do not proceed to Phase 3 without input.**

### Phase 3: Conflict Architecture
Using `conflict-types.md` as reference:
- **External conflict:** What stands in the protagonist's way?
- **Internal conflict:** What's the protagonist's fatal flaw? What lie do they believe?
- **How do they mirror each other?** The external journey should reflect the internal one.
- **Stakes:** What happens if they fail? (Personal → Relational → Community → Existential)

Target: ~200-400 Wörter Konflikt-Architektur als Output, kompakt — die Tiefe entsteht in Phase 4 + Charakter-Skill, nicht hier.

**Wait for user response. Do not proceed to Phase 4 without input.**

### Phase 4: Structure Selection
Using `story-structure.md`:
- Recommend a structure based on genre and story type
- Show the user 2-3 options with pros/cons (max ~150 Wörter pro Option)
- Map the concept to the chosen structure's beats

Write initial outline to `{project}/plot/outline.md`.

**Wait for user response and structure choice. Do not proceed to Phase 5 without input.**

### Phase 5: Pitch Creation
Generate:
- **Logline:** One sentence ([Character] must [action] or [stakes])
- **Elevator pitch:** 2-3 sentences
- **Comparable titles:** "X meets Y"
- **Back-cover blurb:** 150-200 Wörter (does NOT reveal ending)

Write to `{project}/synopsis.md`.

Update book status to "Concept" via MCP `update_field()`.

## Rules
- Discover theme through questions. Imposed themes feel preachy and AI-generated.
- The concept must emerge from DIALOG with the user, not from AI generation alone.
- Every concept needs ALL three: premise + theme + conflict. Skipping one ships an incomplete concept.
- Load genre conventions — they shape structural expectations.
