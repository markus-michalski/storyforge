---
name: chapter-writer-memoir
description: |
  Write a memoir chapter in the author's voice, guided by memoir craft:
  scene-vs-summary, emotional truth, consent gates, and memoir anti-AI patterns.
  Use when: (1) `book_category == "memoir"` AND user says "Kapitel schreiben",
  "write chapter", (2) Book is in Drafting status with chapters outlined.
  Fiction books → use `/storyforge:chapter-writer` instead.
model: claude-opus-4-7
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
   - `consent_status_warnings` — if any `refused` tier → halt drafting immediately; route user to `/storyforge:character-creator` (memoir mode) to decide cut / anonymize / re-frame.
   - `review_handle` — store as `{review_handle}`.
2. **Author profile** — MCP `get_author()`. **Why:** Drives tone, vocabulary, rhythm, voice. Without it prose defaults to generic AI register. **The profile's `writing_discoveries` field carries `recurring_tics` to suppress, `style_principles` to lean into, `donts` to avoid. Apply BEFORE drafting any prose.**
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
9. **People log** — Use `canon_brief` from the chapter writing brief (memoir mode reads `plot/people-log.md`). **Why:** Large people-logs truncate context. The inlined brief carries `pov_relevant_facts` (trimmed newest-first to 30k char budget) and `changed_facts`. For the unfiltered list call standalone `get_canon_brief(book_slug, chapter_slug)`. If `extraction_method == "none"` the file does not exist yet — create it on first chapter close (Step 7). Surface `warnings`; do not invent person facts.
10. **Consent status check** — Read `consent_status_warnings` from the brief. **MANDATORY GATE.** If any warning has tier `refused`, halt drafting and route to `/storyforge:character-creator` (memoir mode). For tier `missing` or `pending`, surface and confirm before drafting.

Note: memoir does **not** read `world/setting.md` (real settings live in `research/sources.md`) and does **not** read `plot/canon-log.md` (memoir uses `people-log.md` instead).

## Writing Process

### Step 1: Review Chapter Plan
Read the chapter README.md outline:
- What's the chapter's PURPOSE?
- What CHANGES by the end?
- Which people appear?
- POV character and their emotional state entering this chapter?
- How does this chapter connect to the previous and next?

### Step 2: Choose Writing Mode
Ask the user how they want to write this chapter (use AskUserQuestion):

- **Scene-by-scene (Recommended)** — Write one scene at a time (~900 Wörter als Soft-Target, je nach Szenen-Bedarf — manche brauchen 600, andere 1200). User reviews and corrects each scene before the next one is written. After all scenes are complete, user reads the full chapter for a final pass.
- **Full chapter** — Write the entire chapter in one pass. Target: 2500-4000 Wörter je nach Outline, als Richtwert — die Outline-Word-Count im README ist der primäre Anker.
- **Batch all chapters** — Write all remaining chapter drafts sequentially. Only for rough first drafts when speed matters more than quality.

If the user has already chosen a mode in this session, remember their choice and skip the question — but still mention which mode is active.

### Step 2b: Mark Chapter as In-Progress
Call MCP `start_chapter_draft(book_slug, chapter_slug)` before any prose. **Why:** Flips status `Outline → Draft` so dashboards and `get_book_progress` reflect active work immediately. Idempotent — only forward, safe to call redundantly.

---

### Pre-Logic Audit (MANDATORY, both modes)

**Emit a bulleted audit block to chat before any prose enters `draft.md`.** No exceptions, no inlining into the prose response. For each category, answer in one sentence citing the source; if the source is silent, say so — that is the gap to surface, not paper over.

1. **Inventory (POV character).** What does the POV char physically carry? **Source:** brief's `pov_character_inventory`. If `extraction_method: "none"` or `warnings` non-empty → ask before any item-touching action; do not invent.

2. **Geography.** Which locations, routes, and settings does this scene touch; which is the POV char familiar with? **Source:** `research/sources.md` + chapter setting prose, plus `plot/timeline.md` and `recent_chapter_timelines`. Verify against research notes — memoir uses real places, not a structured matrix.

3. **Character biography & relationships.** For every person on the page: relationship to POV, what POV knows, what is canon-forbidden? **Source:** `people/{slug}.md`, brief's `canon_brief.pov_relevant_facts` + `canon_brief.changed_facts`. For non-POV characters call standalone `get_canon_brief()` → `current_facts`. If `canon_brief.warnings` non-empty → surface and ask.

4. **Banned phrases + author tics.** Scan the *planned* beats against brief's `banned_phrases` and author profile's `writing_discoveries.recurring_tics` / `donts`. Replan offending beats before any prose.

5. **Sensory plausibility.** Can the POV perceive what the planned beat requires? **Source:** brief's `pov_character_state` — `clothing`, `injuries`, `altered_states`, `environmental_limiters`. If any category has `extraction_methods[cat] == "none"` AND the planned beat depends on it → surface and ask.

If any category surfaces a gap, surface it explicitly and ask the user — never paper over it.

---

### Mode A: Scene-by-Scene Writing (Recommended)

#### Step A1: Scene Plan
Break the chapter outline into scenes based on the Scene Beats in `README.md`. Present the plan: `Scene N: [description] (~XXX words)`. Target ~900 words/scene (vary 600-1200 as needed); total should approximate the chapter's target.

#### Step A1b: Pre-Scene Logic Audit
Run the **Pre-Logic Audit** (above) **per scene**. Emit the bulleted block to chat before appending to `draft.md`, then proceed to Step A2.

#### Step A2: Write One Scene
Apply ALL craft rules (Steps 3-6 from Mode B). Write ONLY this scene.

**Pre-append:** run the Step 6c Simile Discipline Scan. No scene enters `draft.md` before the scan.

After writing:
1. **Append directly to `{project}/chapters/{chapter}/draft.md`** — never paste prose into chat. If `draft.md` doesn't exist, create it with `# Chapter N: Title` above the first scene. Separate scenes with a blank line.
2. Report in chat ONLY: scene number, word count, one-line summary.
3. **WAIT for user feedback** as `{review_handle}:` blocks inside `draft.md`.

#### Step A3: User Review Loop
When the user signals feedback ready ("kommentiert", "gelesen", "Feedback", "lies mal", "schau dir an", or any `{review_handle}:` mention), MUST call `Read` on the full `draft.md` first (GH#27 — file-change diffs truncate for long files). Count the `{review_handle}:` blocks aloud: "Ich sehe N Kommentare." Process each per User Feedback Handling. When the user approves: remove applied review blocks, move to next scene.

#### Step A4: Chapter Completion
All scenes approved → tell user: "Alle Szenen stehen. Bitte lies das komplette Kapitel." Wait for final read. Apply any remaining corrections. Then proceed to Step 7 with status `Review` or `Final` per user verdict.

---

### Mode B: Full Chapter Writing

#### Step 2c: Pre-Chapter Logic Audit
Run the **Pre-Logic Audit** (above) **once per chapter**, covering the chapter as a whole. Emit the bulleted block before any prose enters `draft.md`.

#### Step 3: Opening Hook
Open with action/voice/tension (not weather or waking-up). Ground the reader subtly. Create a micro-question. Match the author's voice from the FIRST sentence. See `openings-and-endings.md`.

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

### Step 7: Save and Update (both modes)
1. Draft is at `{project}/chapters/{chapter}/draft.md`. Count words — report to user.
2. **Extract promises** — Before flipping status to `Review` or `Final`, walk the completed draft and identify setup-elements (unresolved threads, callbacks, foreshadowed events — taxonomy in `reference/craft/plot-logic.md`). Cap at 8 per chapter. Persist via MCP `register_chapter_promises(book_slug, chapter_slug, promises)`.
3. Chapter status: MCP `update_field()` on `chapter.yaml` → `Review` / `Final` (per user) or leave `Draft`.
4. **Update `plot/timeline.md`** — one real-date row per story-day. MANDATORY.
5. **Update `plot/people-log.md`** — what each named person did, said, believed, or revealed in this chapter. The memoir's consistency log — inconsistency across chapters is a factual error, not just a craft failure. Create the file on first chapter close if it does not exist. Use `## Chapter NN — Title` section headers and `### Person: topic` subsections so the `canon_brief` projector can parse them deterministically. Mark changed/corrected facts `CHANGED` with old version in Notes.
6. **No route-matrix update** — memoir documents real settings via research. Note new place names in `research/sources.md` instead.
7. **Update Chapter Timeline** in this chapter's `README.md` — every time-anchored event with real clock times (`~HH:MM`). MANDATORY (future chapters depend on it).
8. **Update POV character snapshot** — Skip when staying at `Draft`. For `Review` / `Final` closes only.

   **How:** Run the brief's extractors mentally against the completed draft. Present a proposal:
   ```
   POV snapshot for {pov_character} after {chapter_slug}:
   - current_inventory: [...]
   - current_clothing:  [...]
   - current_injuries:  [...]
   - altered_states:    [...]
   - environmental_limiters: []
   ```
   Ask: *"Passt das so? Korrekturen?"* Wait for confirmation. Persist via MCP `update_character_snapshot(book_slug, pov_slug, snapshot_json, book_category="memoir")` where `pov_slug` is from `people/{slug}.md`.

### Step 8: Self-Review (both modes)
- Does the opening hook?
- Does the ending land (even if unresolved)?
- Is there *stakes* in every scene — the lived equivalent of conflict?
- Does the POV character's emotional state change or deepen?
- Would a reader know which person is speaking without dialog tags?
- **Simile discipline** — Confirm the Step 6c scan ran. No decorative comparisons survived.
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
- Honor every entry in the brief's `rules_to_honor` (book CLAUDE.md ## Rules). Honor `tone_litmus_questions` (from `plot/tone.md`) when present.
- Never write a relative time reference without checking against the brief's `story_anchor` and `recent_chapter_timelines`. Adjust prose — not the timeline.
- The Chapter Timeline section in `README.md` is MANDATORY at review status.
- Full-chapter mode: write in ONE PASS, then offer revision.
- Scene-by-scene mode: write ONLY the current scene, STOP and WAIT for explicit user approval. Scene text goes into `draft.md`, never chat.
- **Read the full `draft.md` for review (GH#27).** When the user signals `{review_handle}:` blocks are ready, ALWAYS call `Read` on the whole file first. Count the blocks you see and report the count.
- **One Claude Code session per chapter.** Finish the chapter, close, open a new session.
- **Stop if context pressure mounts.** End and resume fresh rather than shipping a degraded scene.
- **Consent gate is non-negotiable.** Before drafting any scene, read `consent_status_warnings`. Tier `refused` halts drafting — route to `/storyforge:character-creator` (memoir mode). Tier `missing` requires explicit user decision. Tier `pending` requires user confirmation.
- **Real names are sacred.** Frontmatter `real_name` stays in the people file; never render it into prose. Use the `name` field (which may be a pseudonym).
- **Scene-vs-summary discipline.** The first decision per page is dramatize or reflect. Default to mix; never default to one alone. See `book_categories/memoir/craft/scene-vs-summary.md`.
- **Emotional truth, not just factual truth.** Reconstructed dialogue carries the substance of remembered conversation, not a fabricated transcript. Felt-sense first; rendered events second; verifiable facts third.
- **No invented details.** If you don't know what someone wore, said, smelled like — leave it out. The instinct to "fill in" is the fiction reflex; in memoir it produces fabrication.
- **No tidy lessons.** "Looking back I realize…", "what I learned was…", reflective platitudes — these are the memoir AI-tells. See `memoir-anti-ai-patterns.md`.
- **People-log over canon-log.** Memoir's continuity log is `plot/people-log.md`. Inconsistency across chapters is factual error.
- **No route matrix.** Real places go in `research/sources.md`, not `world/setting.md`.
- **Genres are themes, not contracts.** A "horror memoir" is a memoir of horrifying experience, not a haunted-house plot.
- Target word count from the chapter README.

## User Feedback Handling — CRITICAL

The user explicitly values being challenged over being blindly agreed with. Before implementing ANY user-requested change:

1. **Verify the claim** — Re-read the passage. Does it say what the user thinks it says?
2. **Check context** — Is there an earlier chapter that justifies the current version?
3. **Assess impact** — Would this change contradict the people-log or break continuity?
4. **Give honest feedback** — If the user is wrong, say so. Quote the text. Explain.
5. **Propose alternatives** — If the concern is valid but the suggested fix isn't, offer a better one.

Only after validation should the correction be applied.
