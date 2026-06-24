---
name: chapter-writer
description: |
  Write a chapter in the author's voice, guided by craft knowledge and genre conventions.
  THE core creative skill. Use when: (1) User says "Kapitel schreiben", "write chapter",
  (2) Book is in Drafting status with chapters outlined.
model: claude-opus-4-7
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
2. **Author profile** — MCP `get_author()`. **Why:** Drives tone, vocabulary, rhythm, voice. Memoirist's voice is the same load. Without it prose defaults to generic AI register. **The profile's `writing_discoveries` field (Issue #151) carries cross-book findings — `recurring_tics` to actively suppress, `style_principles` to lean into, `donts` to avoid. Apply these BEFORE drafting any prose; they are author identity, not optional.**
   **Style Suppressions:** After loading `style_principles`, check the book CLAUDE.md for a `## Style Suppressions` section (the raw CLAUDE.md text is available via the chapter writing brief or `get_book_claudemd`). Any `style_principles` entry whose heading matches a suppression entry is **skipped for this book** — do not activate it in Audit 4.5, do not apply it to prose. The author profile entry is preserved for other books. If no `## Style Suppressions` section exists, all principles apply normally.
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
8. **Canon log** — Use `canon_brief` from the chapter writing brief (Issue #161, #165, #170). **Why:** `plot/canon-log.md` grows large over a novel-length project and causes context-window truncation when read in full. The inlined `canon_brief` provides `pov_relevant_facts` (POV-filtered, your primary writing signal — trimmed newest-first to a 30k char budget) + `changed_facts` (ALL `CHANGED` entries regardless of age) — the facts most likely to affect the chapter being written. `warnings` non-empty = file missing, legacy format, or missing `pov_character` frontmatter; surface to user and do not invent. **For the unfiltered fact list within the scope window** (e.g. when `pov_relevant_facts` is empty or you need broader context), call standalone MCP `get_canon_brief(book_slug, chapter_slug, scope_chapters=N)`. The standalone tool returns the same projection plus `current_facts` — needed for review/continuity work, not for routine drafting. **When `pov_relevant_facts_truncated == true`** the inlined POV facts are the newest slice only; older POV facts still exist in the scope window — call standalone `get_canon_brief()` if continuity checks need them. To go beyond the scope window, pass a larger `N` or read the raw file.
9. **Series canon** — If part of a series, read `{series}/world/canon.md`. **Why:** Series-level facts and constraints carry across books.
9b. **World Rules** — Read `{project}/world-rules.md` if it exists. **Why:** Documents canonically fragile facts the model would otherwise fill with plausible-sounding inventions: species biology, room inventories, character-specific timeline details, distances, healing rates. Any fact documented here overrides model defaults and the "Abstain from invention" rule treats it as a valid source. Missing file → skip silently; do NOT invent rules for uncovered categories.
10. **Previous chapter draft** — Read `{project}/chapters/{prev_chapter_slug}/draft.md`. **Why:** Canon-log gives you facts; the previous draft gives you voice-in-relationship. The prose reveals how these specific characters talk to each other — their sentence rhythm, physical shorthand, what gets left unsaid, who deflects and who pushes. Without this, reconstructed dialog defaults to briefing mode: characters explaining things both parties already know. Skip only if this is Chapter 1 (no predecessor) or if the prior draft does not exist yet.

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

**Emit a bulleted audit block to chat before any prose enters `draft.md`.** No exceptions, no inlining into the prose response. For each category, answer in one sentence citing the source; if the source is silent, say so — that is the gap to surface, not paper over.

1. **Inventory (POV character).** What does the POV char physically carry? **Source:** brief's `pov_character_inventory`. If `extraction_method: "none"` or `warnings` non-empty → ask before any item-touching action; do not invent.
   > *Example: "Theo (Ch26 ~12:55): compass, silver knife, phone, power bar, mission jacket. No pamphlet."*

2. **Geography.** Which rooms, routes, and waypoints does this scene touch; which is the POV char familiar with? **Source:** `world/setting.md` Travel Matrix (fiction) or `research/sources.md` (memoir), plus `plot/timeline.md` and `recent_chapter_timelines`. Model the route before any movement verb.
   > *Example: "Mine = basement chamber + adit chamber via working tunnel; external route via Bloodrunner corridor. POV in basement → internal tunnel is the only sensible path."*

3. **Character biography & relationships.** For every character on the page: relationship to POV, what POV knows, what is canon-forbidden? **Source:** `characters/{slug}.md` (fiction) or `people/{slug}.md` (memoir), brief's `canon_brief.pov_relevant_facts` + `canon_brief.changed_facts`. For non-POV characters call standalone `get_canon_brief()` → `current_facts`. If `canon_brief.warnings` non-empty → surface and ask. **Also check from Prerequisite 10 (previous chapter prose):** How do these specific characters talk to each other in practice? Unfinished sentences? Physical shorthand before words? Who deflects, who presses? This texture — not the canon relationship summary — is what makes "two people who've been through N chapters together" sound different from "two people explaining things to each other."
   > *Example: "Caelan is Sera's father, NOT Theo's. Any 'reminds him of his father' framing is canon-break — cut."*
   > *Texture example: "Ch 31 prose shows Kael asks flat one-word questions when he already knows the answer — he's checking Theo's state, not fishing for info. Theo answers short when he's steady, long when he's scared. They don't explain — they confirm."*

4. **Banned phrases + author tics.** Scan the *planned* beats against brief's `banned_phrases` and author profile's `writing_discoveries.recurring_tics` / `donts`. Replan offending beats before any prose.
   > *Example: "Planned 'Theo does mental math' → tic `math` → replan as 'Theo cross-checks timing against radio chatter'."*

4.5 **style_principles activation.** From the author profile's `writing_discoveries.style_principles`, **excluding any entries suppressed in the book's `## Style Suppressions` section**, name 3 principles that this scene's beats can express. For each: (a) the principle, (b) which beat is the trigger, (c) the concrete action or line that delivers it. If you cannot name a specific beat for a principle, do not count it — an intention without a beat is a hope, not a plan. List the 3 active principles before drafting begins.
   > *Example: "① Banter-exchange trigger (3-beat Q-deflect-call): beat = Theo announces the Lucien plan → Kael asks flat, Theo deflects with sarcasm, Kael names what Theo's doing. ② Sarcasm-deployment (setup/hit/physical): beat = tension peak after the feed scene → one-liner + body cue. ③ Humor-as-armor: beat = vulnerability reveal → Theo jokes instead of answering directly."*

5. **Sensory plausibility.** Can the POV perceive what the planned beat requires? **Source:** brief's `pov_character_state` — `clothing`, `injuries`, `altered_states`, `environmental_limiters`. If any category has `extraction_methods[cat] == "none"` AND the planned beat depends on it → surface and ask.
   > *Example: "`clothing` → tactical boots; 'steps colder than expected' → boots block direct sensation → rewrite as 'he gripped the railing — cold enough that even through gloves he felt it'."*

6. **Scene arc (scene-level; Step 1 asks the chapter-level equivalent).** In one sentence: what does the POV character feel at the start of this scene, what shifts mid-scene, and where do they land emotionally? **Source:** scene PURPOSE from the `## Scene Plan` in the chapter README. If you can only answer by listing beats in order, re-read PURPOSE before writing.

If any category surfaces a gap, surface it explicitly and ask the user — never paper over it.

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
Run the **Pre-Logic Audit** (above) **per scene**. Emit the bulleted block to chat before appending to `draft.md`, then proceed to Step A2.

#### Step A2: Write One Scene

**Anti-Checklist Warning:** The Pre-Scene Audit operates per-beat — that is the planning phase. Prose does NOT follow that sequence. Read all beats from the chapter README's Scene Beats section, hold them as a constellation, then write the scene as one organic whole. Do NOT write beat 1, then beat 2, then beat 3 — that produces sequential paragraphs each rendering one beat in isolation, not prose. After writing, check whether each beat found its place naturally. If a beat did not surface, note it in the chat metadata line so the user can decide whether to add it or release it from the plan.

Apply ALL craft rules (Steps 3-6 from Mode B). Write ONLY this scene.

**Pre-write tactical check:** if the scene involves combat OR group movement (`walk`, `hike`, `drive`, `attack`, `mission`, `enter the building`, `approach`, multi-character formation), the brief's `tactical_constraints` may already be populated. If not — or if the scene's specific outline differs — call MCP `verify_tactical_setup(book_slug, scene_outline_text, characters_present)` and resolve every warn-severity warning before drafting.

**Pre-append:** run the Step 6c Simile Discipline Scan (model fixes autonomously), then the Step 6d Elegant Abstraction Scan (interactive hard-gate — user resolves every hit before appending). No scene enters `draft.md` until both scans are complete and all EA hits resolved or explicitly skipped.

After writing:
1. **Append directly to `{project}/chapters/{chapter}/draft.md`** — never paste prose into chat. If `draft.md` doesn't exist, create it with `# Chapter N: Title` above the first scene. Separate scenes with a blank line.
2. Report in chat ONLY: scene number, word count, one-line summary.
3. **WAIT for user feedback** as `{review_handle}:` blocks inside `draft.md`.

#### Step A3: User Review Loop

→ **§ User Review Loop** in `chapter-writing-shared.md`.

#### Step A4: Chapter Completion

→ **§ Chapter Completion** in `chapter-writing-shared.md`.

---

### Mode B: Full Chapter Writing

#### Step 2c: Pre-Chapter Logic Audit
Run the **Pre-Logic Audit** (above) **once per chapter**, covering the chapter as a whole. Emit the bulleted block before any prose enters `draft.md`.

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

Runs IMMEDIATELY AFTER the Simile Discipline Scan (Step 6c). **No prose enters `draft.md` until this scan is fully resolved.** Reference: `anti-ai-patterns.md` Section 11 for the full shape catalog and examples.

**Shape catalog:** `anti-ai-patterns.md` Section 11 has the full catalog, markers, and examples (11.1–11.10). Quick-scan markers: *One/Two/Three words.* narrator commentary (11.1); *the words/line landed* (11.2); *the room received / silence held* (11.3); *most expensive sentence / paid in silence* (11.4); *did not quite become* — flag 2+ per scene (11.5); body-part + deciding/refusing/knowing (11.6); *trust his/her/my face/hands* trust-split variants (11.6); backward-negation refusal clauses (11.7); same logical constraint in two consecutive sentences (11.8).

**Scan protocol:**

1. Scan all prose in the current scene for the above markers.
2. If **zero hits**: emit `EA-Scan: clean ✓` and proceed to append.
3. If **5 or more hits**: stop and flag it. These shapes cluster — a scene with 5+ hits needs a rewrite, not spot-welding. Tell the user: "This scene has N EA-hits. Patching this many shapes risks losing coherence — recommend rewriting from scratch. Proceed with per-hit fixes or rewrite?" Wait for the user's choice before continuing.
4. If **1–4 hits**: do NOT append yet. **EA-Scan display blocks are the documented exception to the prose-in-chat rule** — they appear in chat as diagnostic blocks, not as prose. Present each hit to the user, one at a time:

```
EA-Scan — hit N/M — Shape 11.X [Name]
--------------------------------------
Original: "[flagged sentence, verbatim]"
Fix:      "[proposed replacement — physical, specific, named body]"

apply / skip / try again
```

   If this is the **second or later 11.5 hit** in the scene, add `[11.5 recurrence — pushback required before skip]` and offer a concrete alternative before accepting a skip.

5. Wait for user response per hit:
   - `apply` — write the fix into the scene text, proceed to next hit
   - `skip` — keep original, proceed to next hit (shape remains; user accepts it deliberately)
   - `try again` or free text — user proposes an alternative or requests a different angle; iterate. After **3 try-again iterations** on the same hit, ask: "Provide the replacement text directly, or type `skip`."

6. After ALL hits are resolved (applied or explicitly skipped), append the corrected scene to `draft.md`. In the chat metadata line (scene number / word count / summary) add: `EA-Scan: N fixed, M skipped`.

**Fix direction (same for all shapes):** Route the emotional weight through a named body in the room. Whose eyes did not move. Whose hand stilled. Whose breath came faster. Specificity is the antidote.

**Why Step 6d is interactive but Step 6c is not:** Simile failures are clear-cut (dead simile, stacked simile, illogical vehicle); the model can fix them reliably. Section 11 shapes are statistically respectable — they appear in published fiction and often sit at peak emotional moments, so whether a given instance is an AI-tell or a deliberate effect requires authorial judgment. The fix must stay in voice. Hence: interactive.

Do not silently bypass the scan — these shapes are invisible to the vocabulary-scan in Step 6 and are the most common source of AI-register complaints from readers.

---

### Step 7: Save and Update (both modes)
1. Draft is at `{project}/chapters/{chapter}/draft.md`. Count words — report to user.
2. **Extract promises (Issue #150)** — Before flipping status to `Review` or `Final`, walk the completed draft and identify setup-elements (locked drawers, character claims, cryptic warnings, unresolved clues — full taxonomy in `reference/craft/plot-logic.md`). For each: short concrete description (8–14 words), target chapter slug if the chapter outline names it else `unfired`, status `active`. Cap at 8 per chapter. Persist via MCP `register_chapter_promises(book_slug, chapter_slug, promises)`. If the chapter places no promises, pass an empty list — this writes a placeholder so the index knows the chapter was processed. Skip this step when staying at `Draft` (mid-chapter saves don't lock in promises).
3. Chapter status: MCP `update_field()` on `chapter.yaml` → `Review` / `Final` (per user) or leave `Draft`. Book-level status auto-derives via the #21 indexer.
4. **Update `plot/timeline.md`** — one row per story-day. MANDATORY.
5. **Update Travel Matrix** in `world/setting.md` if new routes appeared.
6. **Update `plot/canon-log.md`** — new facts. Use `## Chapter NN — Title` section headers and `### Subject: topic` subsections so the `canon_brief` projector can parse them deterministically (Issue #161). If revising, write a `- **CHANGED**: old → new (revision_impact: 06-slug, 11-slug)` bullet inside the chapter where the change was made. The trailing `revision_impact` list names every downstream chapter the change propagates into; the projector reads it automatically.
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
After the chapter is saved and the user signals satisfaction, end the session on momentum.

**Closing reminder to the user:**
> "Tipp für die nächste Session: Stopp jetzt, solange der Schwung da ist. Fang das nächste Kapitel NICHT an — hör mittendrin auf, wenn du weißt wie es weitergeht. So hast du beim nächsten Mal sofort einen Einstiegspunkt und kommst schneller in den Flow."

This is not optional advice — it's a craft technique (Jerry Jenkins, Stephen King). Writers who stop mid-momentum have a warm entry into the next session. Writers who stop at a "logical ending point" face a blank page next time.

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
- Never write a relative time reference without checking against the brief's `story_anchor` and `recent_chapter_timelines`. If the math doesn't work, adjust the prose — not the timeline.
- The Chapter Timeline section in `README.md` is MANDATORY at review status. Future chapters depend on it.
- Full-chapter mode: write in ONE PASS, then offer revision. Don't second-guess mid-flow.
- Scene-by-scene mode: write ONLY the current scene, then STOP and WAIT for explicit user approval (silence does not count). Scene text goes into `draft.md`, never chat — chat gets only metadata (scene number, word count, one-line summary). The user's inline-review workflow (`` ```textile {review_handle}: ... ``` `` blocks) breaks if prose sits in chat.
- **Read the full `draft.md` for review (GH#27).** When the user signals `{review_handle}:` blocks are ready (keywords: "kommentiert", "gelesen", "Feedback", "lies mal", "schau dir an"), ALWAYS call `Read` on the whole file first. The file-change system-reminder diff truncates for long files; trailing comments get silently dropped. Count the blocks you see and report the count.
- **Max. 2 scenes per session (Mode A).** Correction cycles burn context fast — after 2 approved scenes, proactively tell the user to start a new session before continuing with the next scene. Do not wait for compaction to hit silently; degraded context means degraded prose. The `## Scene Plan` in README.md preserves state across sessions.
- **Stop if context pressure mounts.** A scene written after partial context loss degrades silently. End the session and resume fresh rather than shipping a degraded scene.
- Target word count from the chapter README.

### Fiction
- Continuity is global: check `plot/timeline.md`, `canon_brief` (from brief — covers `plot/canon-log.md`), and `world/setting.md` Travel Matrix in addition to the brief's recent chapter timelines. Never invent travel times. Never contradict canon. Use the NEW version of any `CHANGED` fact — `canon_brief.changed_facts` lists all of them.
- Respect genre conventions — they're the contract with the reader.

## User Feedback Handling — CRITICAL

→ **§ User Feedback Handling** in `chapter-writing-shared.md`.
