---
name: chapter-writer-memoir
description: |
  Write a memoir chapter in the author's voice, guided by memoir craft:
  scene-vs-summary, emotional truth, consent gates, and memoir anti-AI patterns.
  Use when: (1) `book_category == "memoir"` AND user says "Kapitel schreiben",
  "write chapter", (2) Book is in Drafting status with chapters outlined.
  Fiction books → use `/storyforge:chapter-writer` instead.
model: claude-opus-4-8
user-invocable: true
argument-hint: "<book-slug> <chapter-number>"
---

# Chapter Writer (Memoir)

This skill is the memoir variant of `chapter-writer`, split out per Issue #174 so memoir sessions load the memoir prerequisite set (scene-vs-summary, emotional-truth, consent gates, people-log) instead of the fiction prerequisite set. The fiction craft catalog, Travel Matrix, and series-canon steps do not apply here — memoir uses real settings, real chronology, and real people with consent obligations and factual-truth standards fiction does not carry.

## Step 0 — Verify memoir mode

Before any other prerequisite load, read `book_category` from the chapter writing brief (Step 1).

If `book_category` is `fiction` or missing → stop and tell the user:
> *This book's `book_category` is `fiction`. Use `/storyforge:chapter-writer` for fiction work.*

Otherwise surface a one-line note: *"Working in memoir mode — loading memoir craft (scene-vs-summary, emotional-truth, anti-AI patterns), checking consent_status before drafting any scene with named living people."*

## Prerequisites — MANDATORY LOADS

Before writing a single word:

1. **Chapter writing brief** — MCP `get_chapter_writing_brief(book_slug, chapter_slug)`. **Why:** One call that bundles all writing context. Load and honor every populated field; empty fields and `errors` entries → degrade gracefully (see **Abstain from invention** rule). Fields with critical actions:
   - `pov_character_inventory` — POV's carried items; if `warnings` non-empty → surface to user, do not invent.
   - `pov_character_state` — clothing / injuries / altered_states / environmental_limiters; if `warnings` → surface; consumed by Pre-Scene Audit category 5.
   - `canon_brief` — scoped people-log projection; `pov_relevant_facts` is your primary writing signal; if `pov_relevant_facts_truncated` → call standalone `get_canon_brief()`; if `warnings` → surface; consumed by Pre-Scene Audit category 3.
   - `consent_status_warnings` — if any `refused` tier → halt drafting immediately; route user to `/storyforge:character-creator-memoir` to decide cut / anonymize / re-frame.
   - `review_handle` — store as `{review_handle}`.
2. **Author profile** — MCP `get_author()`. **Why:** Drives tone, vocabulary, rhythm, voice. Without it prose defaults to generic AI register. **The profile's `writing_discoveries` field carries `recurring_tics` to suppress, `style_principles` to lean into, `donts` to avoid. Apply BEFORE drafting any prose.**
   **Style Suppressions:** Check book CLAUDE.md `## Style Suppressions` section (available in brief or via `get_book_claudemd`). Any `style_principles` heading matching an entry is **skipped for this book** — omit from Audit 4.5, don't apply. Missing section = all principles apply.
3. **Book data** — MCP `get_book_full()`. **Why:** Memoir category context, scope, themes — the frame the chapter must fit.
4. **Genre README(s)** — MCP `get_genre()` for each genre, framed as **thematic tags** (memoir-of-illness, memoir-of-place). **Why:** Memoir uses genre as theme, not as plot-convention contract. Skip plot-genre conventions (HEA, ticking-clock) — they do not apply.
5. **Craft references — universal** — MCP `get_craft_reference()`:
   - `chapter-construction` — **Why:** Hooks and chapter endings still apply; memoir scenes still need shape.
   - `dialog-craft` — **Why:** Reconstructed dialogue in memoir is still dialogue and must not all sound the same. Subtext + beats apply identically.
   - `show-dont-tell` — **Why:** Memoir's failure mode is reflective summary; show-don't-tell is the antidote.
   - `pacing-guide` — **Why:** The scene/summary ratio is the central memoir-craft decision per page.
   - `anti-ai-patterns` — **Why:** The fiction anti-AI catalog still applies for prose-level tells (delve, tapestry, smooth-but-flat rhythm).
   - `prose-style` — **Why:** Sentence-level craft is identical across categories.
   - `simile-discipline` — **Why:** The two-question test still gates Step 6c pre-save scan.
6. **Memoir craft** from `book_categories/memoir/craft/` (resolve via MCP `get_book_category_dir("memoir")`):
   - `scene-vs-summary.md` — **Why:** The first decision per page — dramatize or reflect — drives every memoir scene's shape.
   - `emotional-truth.md` — **Why:** Factual / emotional / narrative truth, in that order of priority. Failure mode: facts without felt sense.
   - `memoir-anti-ai-patterns.md` — **Why:** Memoir-specific tells the universal anti-AI doc misses — "looking back I realize", reflective platitudes, tidy lessons learned, hedged intimacy.
   - `real-people-ethics.md` — **Why:** Consent gate enforcement before any scene with a named living person; framing for anonymized portrayals; defamation-trigger awareness.
7. **Memoir structure type** — Read `plot/structure.md` frontmatter (`structure_type:` — set by `plot-architect-memoir` #58). **Why:** The chapter's scene/summary ratio and POV vantage vary by structure type (chronological / thematic / braided / vignette). For braided memoir, the chapter spine in `plot/outline.md` flags which thread (A or B) this chapter belongs to.
8. **Story timeline** — Read `{project}/plot/timeline.md`. **Why:** Memoir uses real chronology; the timeline file anchors story-time so cross-chapter references stay consistent.
9. **People facts** — Use `canon_brief` from the chapter writing brief (DB-backed since Issue #297 — `plot/people-log.md` is no longer read directly). **Why:** Large logs truncate context. The inlined brief carries `pov_relevant_facts` (trimmed newest-first to 30k char budget) and `changed_facts`. For the unfiltered list call standalone `get_canon_brief(book_slug, chapter_slug)`. If `extraction_method == "none"`, no facts are in DB yet — run `scripts/migrate_canon_log_to_db.py` to import from `plot/people-log.md`, or call `add_canon_fact()` to add facts. Surface `warnings`; do not invent person facts.
10. **Consent status check** — Read `consent_status_warnings` from the brief. **MANDATORY GATE.** If any warning has tier `refused`, halt drafting and route to `/storyforge:character-creator-memoir`. Tier `missing` requires an explicit user decision before drafting (surface the gap and ask the user how to proceed — e.g. cut, anonymize, or confirm consent is in fact fine to assume — not a routine confirmation). Tier `pending` requires the lighter user confirmation that drafting can proceed while consent is still outstanding.

**Shared procedures** — MCP `get_craft_reference("chapter-writing-shared")`. **Why:** The shared procedures doc is the single source of truth for the Pre-Logic Audit (§ Pre-Logic Audit), the EA-Scan Protocol (§ EA-Scan Protocol), the user review loop (§ User Review Loop), scene-plan persistence (§ Scene Plan Persistence), chapter completion (§ Chapter Completion), and POV snapshot (§ POV Snapshot Procedure). Without it, every downstream § reference in this skill has no defined behavior — the skill cannot complete Modes A or B. Contains mode selection, the pre-logic audit, scene-plan persistence, the EA-scan protocol, user review loop, chapter completion, POV snapshot procedure, and user feedback handling — all referenced inline later by section name (`§`).

Note: memoir does **not** read `world/setting.md` (real settings live in `research/sources.md`). Both fiction and memoir read canon facts from DB only (Issue #297) — neither `plot/canon-log.md` nor `plot/people-log.md` is read directly.

## Writing Process

### Step 1: Review Chapter Plan
Read the chapter README.md outline:
- What's the chapter's PURPOSE?
- What CHANGES by the end?
- Which people appear?
- POV character and their emotional state entering this chapter?
- How does this chapter connect to the previous and next?

### Step 2: Choose Writing Mode

→ **§ Mode Selector** in `chapter-writing-shared.md`.

### Step 2b: Mark Chapter as In-Progress

→ **§ Mode Selector / Step 2b** in `chapter-writing-shared.md`.

---

### Pre-Logic Audit (MANDATORY, both modes)

→ **§ Pre-Logic Audit** in `chapter-writing-shared.md`. Category 2 (Geography) and category 3 (Character biography & relationships) use the memoir-source branch documented there (`research/sources.md` instead of `world/setting.md`; `people/{slug}.md` instead of `characters/{slug}.md`). Category 4.5 (style_principles activation) and category 6 (scene arc) apply identically to memoir.

Emit bulleted block before any prose. Mode A: per scene (Step A1b). Mode B: once per chapter (Step 2c). If any category surfaces a gap, ask the user — never paper over it.

---

### Mode A: Scene-by-Scene Writing (Recommended)

#### Step A1: Scene Plan
**Check for existing plan first:** Read the chapter's `README.md`. If a `## Scene Plan` section already exists, load it and present it to the user for confirmation or adjustments — do NOT re-derive from scratch. A scene marked `Written ✓` is locked; offer to re-open it only if the user explicitly asks.

**If no `## Scene Plan` exists — check writing mode:** Read `author_writing_mode` from the loaded author profile.

- If `author_writing_mode` is `plantser` or `discovery`: ask the user (AskUserQuestion):
  - **Rolling Planner first (Recommended)** — Invoke `/storyforge:rolling-planner` to collaboratively develop and stress-test the scene beats before writing. Stops here; resume chapter-writer after rolling-planner completes.
  - **Skip, derive directly** — Build the scene plan now from the outline beats and proceed.

  If the user chooses Rolling Planner: tell them to run `/storyforge:rolling-planner {book_slug} {chapter_slug}` and **STOP**. Do not proceed further in this session.

- If `author_writing_mode` is `outliner` or missing: proceed directly.

If no `## Scene Plan` section exists (and proceeding directly): break the chapter outline into scenes based on the Scene Beats in `README.md`. Present the plan: `Scene N: [description] (~XXX words)`. Target ~900 words/scene (vary 600-1200 as needed); total should approximate the chapter's target.

#### Step A1c: Persist Scene Plan

→ **§ Scene Plan Persistence** in `chapter-writing-shared.md`. (One-line summary includes: POV, location, memory or scene-vs-summary decision.)

#### Step A1b: Pre-Scene Logic Audit
Run the **Pre-Logic Audit** (above) **per scene**. Emit the bulleted block to chat before appending to `draft.md`, then proceed to Step A2.

#### Step A2: Write One Scene
Apply ALL craft rules (Steps 3-6 from Mode B). Write ONLY this scene (~900 words, range 600-1200).

**Pre-append:** run the Step 6c Simile Discipline Scan (model fixes autonomously), then the Step 6d Elegant Abstraction Scan (interactive hard-gate — user resolves every hit before appending). No scene enters `draft.md` until both scans are complete and all EA hits resolved or explicitly skipped.

After writing:
1. **Append directly to `{project}/chapters/{chapter}/draft.md`** — never paste prose into chat. If `draft.md` doesn't exist, create it with `# Chapter N: Title` above the first scene. Separate scenes with a blank line.
2. Report in chat ONLY: scene number, word count, one-line summary.
3. **WAIT for user feedback** as `{review_handle}:` blocks inside `draft.md`.

**GATE: Do NOT proceed to the next scene until the user explicitly confirms approval (e.g., "approved", "next scene", "weiter"). A correction cycle is NOT approval — process corrections, re-append, then re-wait. Only a clean approval or explicit "next" instruction unlocks Step A1 for Scene N+1.**

#### Step A3: User Review Loop

→ **§ User Review Loop** in `chapter-writing-shared.md`.

**GATE: After processing all `{review_handle}:` corrections and re-appending the revised scene, WAIT for explicit approval before unlocking Scene N+1. Do NOT treat a correction acknowledgement as approval.**

#### Step A4: Chapter Completion

→ **§ Chapter Completion** in `chapter-writing-shared.md`.

---

### Mode B: Full Chapter Writing

#### Step 2c: Pre-Chapter Logic Audit
Run the **Pre-Logic Audit** (above) **once per chapter**, covering the chapter as a whole. Emit the bulleted block before any prose enters `draft.md`.

#### Step 3: Opening Hook
Open with action/voice/tension (not weather or waking-up). Ground the reader subtly. Create a micro-question. Match the author's voice from the FIRST sentence. See `openings-and-endings.md`.

**Write the full chapter in ONE PASS. Target the word count from the chapter README (default ~3,000-4,000 words unless specified).**

#### Step 4: Scene-Sequel Structure (memoir-adapted)
Per `chapter-construction.md`. Memoir scenes still need shape: **Scene:** Situation → Stakes → Outcome. **Sequel:** Reflection → Dilemma → Decision (or Acceptance). Real events may not resolve neatly — the sequel is where the memoirist's processing lives.

#### Step 5: Apply Author Voice
For EVERY paragraph: tone (matches descriptors), sentence rhythm (varied per style), vocabulary (preferred list only — banned hits trigger rewrite), dialog (reconstructed — carries the substance, not a transcript), all five senses, specificity over generic.

#### Step 6: Anti-AI Checks (continuous)
Wildly varied sentence length. No AI-tells (`delve`, `tapestry`, `nuanced`, `vibrant`). Asymmetric paragraphs. No triads. No tidy lessons. No "looking back I realize" hinges. Emotions shown through action/body. Specific details. Not every scene wraps neatly.

#### Step 6b: Chapter Ending (see `chapter-construction.md`)
Revelation, decision, question, or emotional beat. Memoir endings can be unresolved — real life is. Connect to the next chapter's opening when planned.

---

### Step 6c: Simile Discipline Scan (MANDATORY, both modes, pre-save)

Runs BEFORE any prose is appended to `draft.md`. Scene-by-scene mode: per scene before Step A2's append. Full-chapter mode: on the complete chapter text before Step 7.

Reference: `simile-discipline.md` for the full heuristic. The scan enforces its two-question test (literal resemblance + real work) plus book-CLAUDE.md simile bans (already in the brief's `rules_to_honor`).

Scan markers: `like [noun/clause]`, `as [adj] as`, `as if/as though`, `the way [subj] [verb]`, `moved/felt/sounded/looked/seemed like`, `resembled`, `reminded ___ of`, `gave the impression of`, `had the air of`, and the failure pattern `the kind of [noun] that [clause]`.

For each hit: answer literal-resemblance and real-work honestly. Reject dead similes on sight. For clean scenes, silence is fine.

---

### Step 6d: Elegant Abstraction Scan — Interactive Hard-Gate (MANDATORY, both modes, pre-save)

Runs IMMEDIATELY AFTER the Simile Discipline Scan (Step 6c). **No prose enters `draft.md` until this scan is fully resolved.** Applies identically to memoir — reflective/reconstructed prose is exactly where these abstraction shapes cluster (a "smooth-but-flat" reflective passage often *is* an unresolved EA hit).

→ **§ EA-Scan Protocol** in `chapter-writing-shared.md`.

After all hits resolved: append to `draft.md` and add `EA-Scan: N fixed, M skipped` to the chat metadata line.

---

### Step 7: Save and Update (both modes)
1. Draft is at `{project}/chapters/{chapter}/draft.md`. Count words — report to user.
2–3. **Extract promises + People Fact Recording Gate.** → **§ Fact Recording Gate** in `chapter-writing-shared.md` for both sub-steps in full — promise extraction, and the people-fact scan/record/checklist gate that blocks the status update in step 4. Skip both when staying at `Draft`.

→ **§ Step 7 Draft-Skip Scope** in `chapter-writing-shared.md` for exactly which of steps 1–9 are gated to Review/Final vs. run unconditionally.

4. Chapter status: MCP `update_field()` on `chapter.yaml` → `Review` / `Final` (per user) or leave `Draft`.
5. **Update session** — MCP `update_session(last_book=book_slug, last_chapter=chapter_slug, last_phase=<short next-step phrase>)`. `last_phase` is a forward-looking "what's next" pointer, not a bare status echo — derive it from step 4's status: `Draft` → `"Draft in progress — resume writing"`, `Review` → `"Ready for chapter-reviewer-memoir"`, `Final` → `"Chapter complete — plan the next chapter"`. **Why:** Keeps the session's ephemeral pointer current so `get_current_story_anchor`'s session-fallback resolves to the chapter just worked on instead of erroring empty, and `start-session`'s status line reflects real, actionable progress instead of staying permanently empty (Issue #378). Matches `rolling-planner`'s `last_phase` convention — both writers describe where to pick up next, not just an enum value (a bare `Final` tells the user nothing about what to do next).
6. **Update `plot/timeline.md`** — one real-date row per story-day. MANDATORY.
7. **No route-matrix update** — memoir documents real settings via research. Note new place names in `research/sources.md` instead.
8. **Update Chapter Timeline** in this chapter's `README.md` — every time-anchored event with real clock times (`~HH:MM`). MANDATORY (future chapters depend on it).
9. **Update POV character snapshot** — **§ POV Snapshot Procedure** in `chapter-writing-shared.md`.

### Step 8: Self-Review (both modes)
- Does the opening hook?
- Does the ending land (even if unresolved)?
- Is there *stakes* in every scene — the lived equivalent of conflict?
- Does the POV character's emotional state change or deepen?
- Would a reader know which person is speaking without dialog tags?
- **Simile discipline** — Confirm the Step 6c scan ran. No decorative comparisons survived.
- **Elegant abstraction** — Confirm the Step 6d scan ran on every scene/section. Any surviving Section 11 shapes are user-approved skips — not oversights. If any shape is present that was not surfaced in the EA-Scan, that is a failure.
- **Litmus test** — If `plot/tone.md` exists, answer EVERY question. If more than 1 answer is "no", flag to user before proceeding.
- **Time consistency** — Verify every time reference is consistent with the Chapter Timeline from Step 7.

Suggest: `/storyforge:chapter-reviewer` for detailed review.

### Step 9: Stop While Ahead (both modes)
After the chapter is saved and the user signals satisfaction, end the session on momentum.

**Closing reminder to the user:**
> "Tipp für die nächste Session: Stopp jetzt, solange der Schwung da ist. Fang das nächste Kapitel NICHT an — hör mittendrin auf, wenn du weißt wie es weitergeht."

If the user is blocked or struggling: redirect to `/storyforge:unblock` instead of pushing through.

## Rules

- **Abstain from invention.** If you cannot point to a source in the brief, `people/*.md`, `plot/timeline.md`, `research/sources.md`, or a previous `draft.md` for a concrete detail — do not write it. Surface the gap and ask. Every invented detail in memoir is fabrication.
- Author profile is LAW. Every scene needs *stakes* — the lived equivalent of conflict. Dialog has subtext. Banned words trigger sentence rewrite.
- **Simile Discipline (Step 6c) is non-negotiable.** Every scene survives the two-question test before it enters `draft.md`. See `simile-discipline.md`.
- **Elegant Abstraction Scan (Step 6d) is a non-negotiable interactive hard-gate.** No scene enters `draft.md` until every Section 11 hit is either fixed or explicitly skipped by the user. The model does not fix autonomously — each hit is presented, a replacement proposed, user approves. These shapes look literary but render emotion through abstraction — in memoir this is the "reflective platitude smoothed into elegant prose" failure mode overlapping with `memoir-anti-ai-patterns.md`. See `anti-ai-patterns.md` Section 11.
- Honor every entry in the brief's `rules_to_honor` (book CLAUDE.md ## Rules). Honor `tone_litmus_questions` (from `plot/tone.md`) when present.
- Never write a relative time reference without checking against the brief's `story_anchor` and `recent_chapter_timelines`. Adjust prose — not the timeline.
- The Chapter Timeline section in `README.md` is MANDATORY at review status.
- Full-chapter mode: write in ONE PASS, then offer revision.
- Scene-by-scene mode: write ONLY the current scene, STOP and WAIT for explicit user approval. Scene text goes into `draft.md`, never chat.
- **Read the full `draft.md` for review (GH#27).** When the user signals `{review_handle}:` blocks are ready, ALWAYS call `Read` on the whole file first. Count the blocks you see and report the count.
- **Max. 2 scenes per session (Mode A).** Correction cycles burn context fast — after 2 approved scenes, proactively tell the user to start a new session before continuing with the next scene. Do not wait for compaction to hit silently; degraded context means degraded prose. The `## Scene Plan` in README.md preserves state across sessions.
- **Stop if context pressure mounts.** End and resume fresh rather than shipping a degraded scene.
- **Consent gate is non-negotiable.** Before drafting any scene, read `consent_status_warnings`. Tier `refused` halts drafting — route to `/storyforge:character-creator-memoir`. Tier `missing` requires explicit user decision. Tier `pending` requires user confirmation.
- **Real names are sacred.** Frontmatter `real_name` stays in the people file; never render it into prose. Use the `name` field (which may be a pseudonym).
- **Scene-vs-summary discipline.** The first decision per page is dramatize or reflect. Default to mix; never default to one alone. See `book_categories/memoir/craft/scene-vs-summary.md`.
- **Emotional truth, not just factual truth.** Reconstructed dialogue carries the substance of remembered conversation, not a fabricated transcript. Felt-sense first; rendered events second; verifiable facts third.
- **No invented details.** If you don't know what someone wore, said, smelled like — leave it out. The instinct to "fill in" is the fiction reflex; in memoir it produces fabrication.
- **No tidy lessons.** "Looking back I realize…", "what I learned was…", reflective platitudes — these are the memoir AI-tells. See `memoir-anti-ai-patterns.md`.
- **DB is the continuity log.** Memoir facts live in `canon_facts` DB alongside fiction facts (Issue #297). Inconsistency across chapters is factual error. `plot/people-log.md` is a read-only archive after migration.
- **No route matrix.** Real places go in `research/sources.md`, not `world/setting.md`.
- **Genres are themes, not contracts.** A "horror memoir" is a memoir of horrifying experience, not a haunted-house plot.
- Target word count from the chapter README.

## User Feedback Handling — CRITICAL

→ **§ User Feedback Handling** in `chapter-writing-shared.md`.
