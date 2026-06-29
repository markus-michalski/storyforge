---
name: chapter-writer
description: |
  Write a chapter in the author's voice, guided by craft knowledge and genre conventions.
  THE core creative skill. Use when: (1) User says "Kapitel schreiben", "write chapter",
  (2) Book is in Drafting status with chapters outlined.
model: claude-opus-4-8
user-invocable: true
argument-hint: "<book-slug> <chapter-number>"
---

# Chapter Writer

## Step 0 — Resolve book category

If `book_category == "memoir"` (read from the chapter writing brief, Step 1) → invoke `/storyforge:chapter-writer-memoir` instead. Treat missing `book_category` as `fiction` (legacy default).

## Prerequisites — MANDATORY LOADS

Before writing a single word:

1. **Chapter writing brief** — MCP `get_chapter_writing_brief(book_slug, chapter_slug)`. **Why:** One call that bundles all writing context. Load and honor every populated field; empty fields and `errors` entries → degrade gracefully (see **Abstain from invention** rule). Fields with critical actions:
   - `pov_character_inventory` — POV's carried items; if `warnings` non-empty → surface to user, do not invent.
   - `pov_character_state` — clothing / injuries / altered_states / environmental_limiters; if `warnings` → surface; consumed by Pre-Scene Audit category 5.
   - `canon_brief` — scoped canon-log (fiction) or people-log (memoir) projection; `pov_relevant_facts` is your primary writing signal; if `pov_relevant_facts_truncated` → call standalone `get_canon_brief()`; if `warnings` → surface; consumed by Pre-Scene Audit category 3.
   - `consent_status_warnings` *(memoir only)* — if any `refused` tier → halt drafting immediately.
   - `review_handle` — store as `{review_handle}`.
2. **Author profile** — MCP `get_author()`. **Why:** Drives tone, vocabulary, rhythm, voice. Memoirist's voice is the same load. Without it prose defaults to generic AI register. **The profile's `writing_discoveries` field (Issue #151) carries cross-book findings — `recurring_tics` to actively suppress, `style_principles` to lean into, `donts` to avoid. Apply these BEFORE drafting any prose; they are author identity, not optional.** The `style_notes` field (Issue #294) contains the hand-crafted Voice, Tone Profile, Signature Moves, and Dialog Voice sections from `profile.md` — read them for concrete voice texture that the frontmatter fields alone cannot convey. Empty `style_notes` is fine; skip silently.
   **Style Suppressions:** Check book CLAUDE.md `## Style Suppressions` section (available in brief or via `get_book_claudemd`). Any `style_principles` heading matching an entry is **skipped for this book** — omit from Audit 4.5, don't apply. Missing section = all principles apply.
3. **Book data** — MCP `get_book_full()`. **Why:** Genres / category context, plot or scope, the frame the chapter must fit.

### Fiction mode (`book_category == "fiction"`)

4. **Genre README(s)** — MCP `get_genre()` for each genre. **Why:** Reader-expected conventions; violations need to be deliberate.
5. **Craft references** — MCP `get_craft_reference()`:
   - `chapter-construction` — **Why:** Hooks, scene-sequel, endings — the structural skeleton of every chapter.
   - `dialog-craft` — **Why:** Subtext, beats, voice differentiation — the most common AI-tell is dialog where everyone sounds the same.
   - `show-dont-tell` — **Why:** Techniques and five senses — telling collapses prose into report-mode.
   - `pacing-guide` — **Why:** Scene vs. summary, rhythm — wrong pacing is what makes drafts feel flat.
   - `anti-ai-patterns` — **Why:** The negative-space catalog — what to NOT do at all costs.
   - `prose-style` — **Why:** Word choice, rhythm, devices — sentence-level craft.
   - `simile-discipline` — **Why:** The two-question test for every comparison — mandatory for the pre-save scan in Step 6c.
6. **World files** — Read `{project}/world/setting.md`. **Why:** Travel Matrix and location facts — invented travel times break continuity. Mandatory when the chapter involves travel or specific places.
7. **Story timeline** — Read `{project}/plot/timeline.md`. **Why:** Canonical day/date calendar — the brief's `recent_chapter_timelines` covers intra-day grids; `timeline.md` covers the macro arc.
8. **Canon log** — Use `canon_brief` from the chapter writing brief. Provides `pov_relevant_facts` (POV-filtered primary signal) + `changed_facts` (all `CHANGED` entries). `warnings` non-empty → surface to user, do not invent. `pov_relevant_facts_truncated == true` or need broader context → call standalone `get_canon_brief(book_slug, chapter_slug, scope_chapters=N)`; returns same projection + `current_facts`.
9. **Series canon** — If part of a series, read `{series}/world/canon.md`. **Why:** Series-level facts and constraints carry across books.
9b. **World Rules** — Read `{project}/world/rules.md` if it exists. **Why:** Documents canonically fragile facts the model would otherwise fill with plausible-sounding inventions: species biology, room inventories, character-specific timeline details, distances, healing rates. Any fact documented here overrides model defaults and the "Abstain from invention" rule treats it as a valid source. Missing file → skip silently; do NOT invent rules for uncovered categories.
10. **Previous chapter draft** — `brief.prev_chapter_draft` (Issue #342). Already bundled in the brief — no separate Read needed. Contains the last ~600–700 words (3500 chars) of the directly preceding chapter's `draft.md`. `null` = Chapter 1 or predecessor has no draft yet. **Why:** Canon-log gives you facts; the previous draft gives you voice-in-relationship. The prose reveals how these specific characters talk to each other — their sentence rhythm, physical shorthand, what gets left unsaid, who deflects and who pushes. Without this, dialog defaults to briefing mode: characters explaining things both parties already know. **Critical:** Before writing Scene 1, check what emotional state, facts, and events the previous chapter established — do not re-establish them. If the predecessor covered a conversation or conflict in detail, this chapter opens *after* that resolution, not by replaying it.

**Shared procedures** — MCP `get_craft_reference("chapter-writing-shared")`. Contains mode selection, scene-plan persistence, user review loop, chapter completion, POV snapshot procedure, and user feedback handling — all referenced inline later by section name (`§`).

## Writing Process

### Step 1: Review Chapter Plan
Read the chapter README.md outline:
- What's the chapter's PURPOSE?
- What CHANGES by the end?
- Which characters appear?
- POV character and their emotional state entering this chapter?
- How does this chapter connect to the previous and next?

### Step 2: Choose Writing Mode

→ **§ Mode Selector** in `chapter-writing-shared.md`.

### Step 2b: Mark Chapter as In-Progress

→ **§ Mode Selector / Step 2b** in `chapter-writing-shared.md`.

---

### Pre-Logic Audit (MANDATORY, both modes)

→ **§ Pre-Logic Audit** in `chapter-writing-shared.md`.

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

→ **§ Scene Plan Persistence** in `chapter-writing-shared.md`.

#### Step A1b: Pre-Scene Logic Audit
Run **§ Pre-Logic Audit** from `chapter-writing-shared.md` **per scene**. Emit the bulleted block to chat before appending to `draft.md`, then proceed to Step A2.

#### Step A2: Write One Scene

**Anti-Checklist Warning:** The Pre-Scene Audit is planning — prose doesn't follow beat sequence. Hold all beats as a constellation and write the scene organically. After writing, check each beat found its place; note unplaced beats in chat metadata.

Apply ALL craft rules (Steps 3-6 from Mode B). Write ONLY this scene.

**Pre-write tactical check:** if the scene involves combat OR group movement (`walk`, `hike`, `drive`, `attack`, `mission`, `enter the building`, `approach`, multi-character formation), the brief's `tactical_constraints` may already be populated. If not — or if the scene's specific outline differs — call MCP `verify_tactical_setup(book_slug, scene_outline_text, characters_present)` and resolve every warn-severity warning before drafting.

**Pre-append:** run the Step 6c Simile Discipline Scan (model fixes autonomously), then the Step 6d Elegant Abstraction Scan (interactive hard-gate — user resolves every hit before appending). No scene enters `draft.md` until both scans are complete and all EA hits resolved or explicitly skipped.

After writing:
1. **Append directly to `{project}/chapters/{chapter}/draft.md`** — never paste prose into chat. If `draft.md` doesn't exist, create it with `# Chapter N: Title` above the first scene. Separate scenes with a blank line.
2. Report in chat ONLY: scene number, word count, one-line summary.
3. **WAIT for user feedback** as `{review_handle}:` blocks inside `draft.md`.

> **--- WAIT GATE ---**
> Stop here. Do NOT proceed to the next scene or any Step A3/A4 actions.
> Resume only when the user provides explicit written approval or a `{review_handle}:` block in `draft.md`.
> Silence is not approval.
> **--- END GATE ---**

#### Step A3: User Review Loop

→ **§ User Review Loop** in `chapter-writing-shared.md`.

#### Step A4: Chapter Completion

→ **§ Chapter Completion** in `chapter-writing-shared.md`.

---

### Mode B: Full Chapter Writing

#### Step 2c: Pre-Chapter Logic Audit
Run **§ Pre-Logic Audit** from `chapter-writing-shared.md` **once per chapter**, covering the chapter as a whole. Emit the bulleted block before any prose enters `draft.md`.

#### Step 3: Opening Hook
Open with action/voice/tension (not weather or waking-up). Ground the reader subtly. Create a micro-question. Match the author's voice from the FIRST sentence. See `openings-and-endings.md`. If Chapter 1: review and plan the 13-Point First Chapter Checklist from `openings-and-endings.md`.

#### Step 4: Scene-Sequel Structure
Per `chapter-construction.md`. **Scene:** Goal → Conflict → Disaster/Outcome. **Sequel:** Reaction → Dilemma → Decision.

#### Step 5: Apply Author Voice
For EVERY paragraph: tone (matches descriptors), sentence rhythm (varied per style), vocabulary (preferred list only — banned hits trigger rewrite), dialog (distinguishable voices, subtext, minimal tags), all five senses, specificity over generic.

#### Step 6: Anti-AI Checks (continuous; see `anti-ai-patterns.md`)
Wildly varied sentence length. No AI-tells (`delve`, `tapestry`, `nuanced`, `vibrant`). Asymmetric paragraphs. No triads. Dialog like real people, not speeches. Emotions shown through action/body. Specific details. Author's tics intact. Not every scene wraps neatly.

#### Step 6b: Chapter Ending (see `chapter-construction.md`)
Cliffhanger, revelation, decision, question, or emotional beat. Must make the reader turn the page. Connect to the next chapter's opening when planned.

---

### Step 6c: Simile Discipline Scan (MANDATORY, both modes, pre-save)

Runs BEFORE any prose is appended to `draft.md`. Scene-by-scene mode: per scene before Step A2's append. Full-chapter mode: on the complete chapter text before Step 7.

Reference: `simile-discipline.md` for the full heuristic. The scan enforces its two-question test (literal resemblance + real work) plus book-CLAUDE.md simile bans (already in the brief's `rules_to_honor`).

Apply author-voice bias from the author profile — simile-heavy voices get more leeway than sparse ones. The brief's `recent_simile_count_per_chapter` shows what the last 3 chapters used — if a paragraph would push above ~3-4, cut harder. Book CLAUDE.md ## Rules in `rules_to_honor` override author-voice leniency. See `simile-discipline.md` for the full marker list, failure modes, and revision moves.

For clean scenes, silence is fine. When cuts happen, optionally note "Simile-Scan: N cut, M revised" alongside the scene metadata line. Do not skip — decorative similes are the recurring failure mode `prose-style.md` and `anti-ai-patterns.md` cannot catch alone.

---

### Step 6d: Elegant Abstraction Scan — Interactive Hard-Gate (MANDATORY, both modes, pre-save)

Runs IMMEDIATELY AFTER the Simile Discipline Scan (Step 6c). **No prose enters `draft.md` until this scan is fully resolved.**

→ **§ EA-Scan Protocol** in `chapter-writing-shared.md`.

After all hits resolved: append to `draft.md` and add `EA-Scan: N fixed, M skipped` to the chat metadata line.


---

### Step 7: Save and Update (both modes)
1. Draft is at `{project}/chapters/{chapter}/draft.md`. Count words — report to user.
2. **Extract promises (Issue #150)** — Before flipping status to `Review` or `Final`, walk the completed draft and identify setup-elements (locked drawers, character claims, cryptic warnings, unresolved clues — full taxonomy in `reference/craft/plot-logic.md`). For each: short concrete description (8–14 words), target chapter slug if the chapter outline names it else `unfired`, status `active`. Cap at 8 per chapter. Persist via MCP `register_chapter_promises(book_slug, chapter_slug, promises)`. If the chapter places no promises, pass an empty list — this writes a placeholder so the index knows the chapter was processed. Skip this step when staying at `Draft` (mid-chapter saves don't lock in promises).
3. **Canon Fact Recording Gate — required before advancing to Review or Final. Skip only when staying at `Draft`.** This gate blocks the status update in step 4 — do not call `update_field()` until the gate is complete.

   a. **Check existing coverage** — Call `get_canon_brief(book_slug, chapter_slug)`. Note the `facts_count` for the current chapter slug. Even when facts already exist (incremental save), still scan the current session's prose for anything added since the last save.

   b. **Scan the completed draft** for canon-relevant events. Check every category:
      - **Characters** — new names, physical descriptions, abilities, injuries, deaths, status changes
      - **Locations** — new rooms, buildings, routes, distances, first-visit establishments
      - **Relationships** — connections established or changed between characters
      - **Objects** — named items introduced, ownership transfers, destruction
      - **Timeline** — exact dates/times, durations, relative anchors established
      - **Events** — plot-significant actions, revelations, decisions with lasting consequences
      - **Backstory** — origins, histories, past events first revealed in this chapter

   c. **Record each fact** — Call `add_canon_fact(book_slug, chapter_slug, subject, fact, domain)` for every item identified above.
      - `domain`: `character` | `location` | `relationship` | `object` | `timeline` | `event` | `backstory`
      - For revisions to existing facts: add `is_revision=True`, `old_value=<previous text>`, `revision_impacts=[downstream_chapter_slug, ...]`

   d. **Emit a Canon Fact Checklist** in chat — mandatory, even when the list is short:
      ```
      Canon Facts Recorded — Ch. {N}:
      [✓] subject: <X> | fact: <...> | domain: <...>
      [✓] subject: <Y> | fact: <...> | domain: <...>
      ```
      If zero canon-relevant events exist, declare it explicitly: *"Canon Recording: no new facts established in this chapter beyond what is already in DB."* This is a deliberate statement, not a silent skip.

4. Chapter status: MCP `update_field()` on `chapter.yaml` → `Review` / `Final` (per user) or leave `Draft`. Book-level status auto-derives via the #21 indexer.
5. **Update `plot/timeline.md`** — one row per story-day. MANDATORY.
6. **Update Travel Matrix** in `world/setting.md` if new routes appeared.
7. **Update Chapter Timeline** in this chapter's `README.md` — every time-anchored event with `~HH:MM`. MANDATORY (future chapters depend on it).

8. **Update POV character snapshot** — **§ POV Snapshot Procedure** in `chapter-writing-shared.md`.

### Step 8: Self-Review (both modes)
Before presenting to user (in full-chapter mode) or after all scenes assembled (in scene-by-scene mode), quick-check:
- Does the opening hook?
- Does the ending compel?
- Is there conflict in every scene?
- Does the POV character's emotional state change?
- Would a reader know which character is speaking without dialog tags?
- **Simile discipline** — Confirm the Step 6c scan ran on every scene/section. No decorative or illogical comparisons survived. No stacked similes. No dead similes. `the kind of X that Y` constructions inspected.
- **Elegant abstraction** — Confirm the Step 6d scan ran on every scene/section. Any surviving Section 11 shapes are user-approved skips — not oversights. If any shape is present that was not surfaced in the EA-Scan, that is a failure.
- **Litmus test** — If `plot/tone.md` exists, answer EVERY question from the Litmus Test section. If more than 1 answer is "no", flag it to the user and suggest specific revisions before proceeding.
- **Time consistency** — Verify that every time reference in the chapter (explicit or relative) is consistent with the Chapter Timeline you created in Step 7.

Suggest: `/storyforge:chapter-reviewer` for detailed review.

### Step 9: Stop While Ahead (both modes)
After the chapter is saved and the user signals satisfaction, end the session. Remind the user: stop now, don't start the next chapter — stopping mid-momentum gives a warm entry next session (Jerry Jenkins / Stephen King technique).

If the user is blocked or struggling: redirect to `/storyforge:unblock` instead of pushing through.

## Rules

### Universal (both modes)
- **Abstain from invention.** If you cannot point to a source line in the loaded brief (including `canon_brief.pov_relevant_facts`, `canon_brief.changed_facts`, or — via standalone `get_canon_brief()` — `current_facts`), `world/setting.md`, `characters/*.md` (or `people/*.md` for memoir), `plot/timeline.md`, or a previous chapter's `draft.md` for a concrete detail — items carried, character relationships, routes, location features, quoted dialogue, named objects, time anchors — do not write it. Surface the gap to the user and ask, or leave the spot empty. **Why:** every invented detail accumulates as soft canon and contradicts hard canon on the next pass. The cost of a missing detail is one question to the user; the cost of an invented detail is a continuity break that may not surface for chapters and corrupts every reader who passes through the gap before it is caught. **How to apply:** before writing any concrete claim, do a one-second source check. If the source is not immediately retrievable from the loaded data, flag it instead of guessing. The Pre-Scene Logic Audit (Step A1b / Step 2c) is the structural enforcement of this rule — emit it; do not skip it.
- Resolve `book_category` in Step 0 before any prerequisite load. The fiction and memoir prerequisite sets are non-overlapping.
- Author profile is LAW. SHOW don't tell. Every scene needs conflict. Dialog has subtext. Banned words trigger sentence rewrite.
- **Simile Discipline (Step 6c) is non-negotiable.** Every scene survives the two-question test before it enters `draft.md`. Author-voice bias = quality not quantity. See `simile-discipline.md`.
- **Elegant Abstraction Scan (Step 6d) is a non-negotiable interactive hard-gate.** No scene enters `draft.md` until every Section 11 hit is either fixed or explicitly skipped by the user. The model does not fix autonomously — each hit is presented, a replacement proposed, user approves. These shapes look literary but render emotion through abstraction; they are the primary AI-register failure mode at high-stakes moments. See `anti-ai-patterns.md` Section 11.
- Honor every entry in the brief's `rules_to_honor` (book CLAUDE.md ## Rules) — `severity: block` rules will be hard-blocked by the PostToolUse hook. Honor `tone_litmus_questions` (from `plot/tone.md`) when present.
- **Callback threading constraints:** If a callback entry includes `intensity:` and `max_mentions:` metadata, treat these as hard constraints. `intensity: passive | max_mentions: 1` = mention the prop once, in passing, no sensory close-up, no emotional emphasis. After drafting, scan for all mentions of the prop — if the count exceeds `max_mentions`, cut or consolidate before the Step 6c scan. Without metadata, apply `active` behavior (2–3 mentions allowed).
- Honor the brief's `story_anchor` and `recent_chapter_timelines` for every relative time reference. Adjust prose when the math conflicts — the timeline is ground truth, not the draft.
- The Chapter Timeline section in `README.md` is MANDATORY at review status. Future chapters depend on it.
- Full-chapter mode: write in ONE PASS, then offer revision. Commit to the flow — course-correct after the scene is complete, not during.
- Scene-by-scene mode: write ONLY the current scene, then STOP at the WAIT GATE (Step A2). Scene text goes into `draft.md`; chat receives only metadata (scene number, word count, one-line summary). The WAIT GATE enforces this — see Step A2.
- **Read the full `draft.md` for review (GH#27).** When the user signals `{review_handle}:` blocks are ready (keywords: "kommentiert", "gelesen", "Feedback", "lies mal", "schau dir an"), ALWAYS call `Read` on the whole file first. The file-change system-reminder diff truncates for long files; trailing comments get silently dropped. Count the blocks you see and report the count.
- **Max. 2 scenes per session (Mode A).** Correction cycles burn context fast — after 2 approved scenes, proactively tell the user to start a new session before continuing with the next scene. Do not wait for compaction to hit silently; degraded context means degraded prose. The `## Scene Plan` in README.md preserves state across sessions.
- **Stop if context pressure mounts.** A scene written after partial context loss degrades silently. End the session and resume fresh rather than shipping a degraded scene.
- Target word count from the chapter README.

### Fiction
- Continuity is global: check `plot/timeline.md`, `canon_brief` (DB-backed since #297), and `world/setting.md` Travel Matrix in addition to the brief's recent chapter timelines. Honor the Travel Matrix as the ground truth for all distances and travel durations. Honor the canon log as ground truth — use the NEW version of any `CHANGED` fact (`canon_brief.changed_facts` lists all of them).
- Respect genre conventions — they're the contract with the reader.

## User Feedback Handling — CRITICAL

→ **§ User Feedback Handling** in `chapter-writing-shared.md`.
