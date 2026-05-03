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

Read `book_category` from the chapter writing brief (Step 1). The brief carries it explicitly so the skill never has to re-fetch the book just to check. Treat missing as `fiction` (legacy default).

If `book_category == "memoir"`, surface a one-line note: *"Working in memoir mode — loading memoir craft (scene-vs-summary, emotional-truth, anti-AI patterns), checking consent_status before drafting any scene with named living people."*

The fiction and memoir prerequisite sets are non-overlapping. Branch every load below on `book_category`.

## Prerequisites — MANDATORY LOADS

Before writing a single word:

1. **Chapter writing brief** — MCP `get_chapter_writing_brief(book_slug, chapter_slug)`. **Why:** One structured payload that bundles 13 separate context sources — `book_category`, story_anchor, recent_chapter_timelines, recent_chapter_endings, characters_present (fiction: role + knowledge + tactical profiles; memoir: relationship + person_category + consent_status + anonymization), `consent_status_warnings` (memoir only), rules_to_honor (book CLAUDE.md ## Rules with severity), callbacks_in_register, banned_phrases (book + author + global), recent_simile_count_per_chapter, tone_litmus_questions, tactical_constraints, review_handle, plus the chapter metadata. Honor every populated field while writing. Empty fields and entries in `errors` mean "not available for this chapter" — degrade gracefully, do not invent. Store the returned `review_handle` as `{review_handle}`.
2. **Author profile** — MCP `get_author()`. **Why:** Drives tone, vocabulary, rhythm, voice. Memoirist's voice is the same load. Without it prose defaults to generic AI register. **The profile's `writing_discoveries` field (Issue #151) carries cross-book findings — `recurring_tics` to actively suppress, `style_principles` to lean into, `donts` to avoid. Apply these BEFORE drafting any prose; they are author identity, not optional.**
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
8. **Canon log** — Read `{project}/plot/canon-log.md`. **Why:** Established facts, including `CHANGED` revisions. Contradicting canon breaks reader trust.
9. **Series canon** — If part of a series, read `{series}/world/canon.md`. **Why:** Series-level facts and constraints carry across books.

### Memoir mode (`book_category == "memoir"`)

4. **Genre README(s)** — MCP `get_genre()` for each genre, framed as **thematic tags** (memoir-of-illness, memoir-of-place). **Why:** Memoir uses genre as theme, not as plot-convention contract. Skip the plot-genre conventions (HEA, ticking-clock, etc.) — they do not apply.
5. **Craft references — universal** — MCP `get_craft_reference()`:
   - `chapter-construction` — **Why:** Hooks and chapter endings still apply; memoir scenes still need shape.
   - `dialog-craft` — **Why:** Reconstructed dialogue in memoir is still dialogue and must not all sound the same. Subtext + beats apply identically.
   - `show-dont-tell` — **Why:** Memoir's failure mode is reflective summary; show-don't-tell is the antidote.
   - `pacing-guide` — **Why:** The scene/summary ratio is the central memoir-craft decision per page.
   - `anti-ai-patterns` — **Why:** The fiction anti-AI catalog still applies for prose-level tells (delve, tapestry, smooth-but-flat rhythm).
   - `prose-style` — **Why:** Sentence-level craft is identical across categories.
   - `simile-discipline` — **Why:** The two-question test still gates Step 6c pre-save scan.
6. **Memoir craft** from `book_categories/memoir/craft/` (resolve via MCP `get_book_category_dir("memoir")`):
   - `scene-vs-summary.md` — **Why:** The first decision per page — dramatize or reflect — drives every memoir scene's shape. The fiction craft's "scene = goal/conflict/disaster" still applies; this layer adds *when not to render a scene at all*.
   - `emotional-truth.md` — **Why:** The standard memoir is held to. Factual / emotional / narrative truth, in that order of priority. Failure mode: facts without felt sense.
   - `memoir-anti-ai-patterns.md` — **Why:** Memoir-specific tells the universal anti-AI doc misses — "looking back I realize", reflective platitudes, tidy lessons learned, hedged intimacy.
   - `real-people-ethics.md` — **Why:** Consent gate enforcement before any scene with a named living person; framing for anonymized portrayals; defamation-trigger awareness.
7. **Memoir structure type** — Read `plot/structure.md` frontmatter (`structure_type:` — set by `plot-architect` memoir mode #58). **Why:** The chapter's scene/summary ratio and POV vantage vary by structure type (chronological / thematic / braided / vignette). For braided memoir, the chapter spine in `plot/outline.md` flags which thread (A or B) this chapter belongs to.
8. **Story timeline** — Read `{project}/plot/timeline.md`. **Why:** Memoir uses real chronology, but the timeline file still anchors story-time so cross-chapter references stay consistent.
9. **People log** — Read `{project}/plot/people-log.md` if it exists (analogue to fiction's `canon-log.md`). **Why:** Real-person consistency — what each person *did*, *said*, *believed* in earlier chapters. Memoir's truth standard requires consistency across chapters; canon-log contradictions in memoir are not just craft failures, they are factual errors. If the file does not exist yet, create it on first chapter close (Step 7).
10. **Consent status check** — Read `consent_status_warnings` from the brief. **MANDATORY GATE.** If any warning has tier `refused`, halt drafting and route the user back to `/storyforge:character-creator` (memoir mode) to decide cut / anonymize / re-frame. For tier `missing` or `pending`, surface the warning to the user and confirm before drafting.

Note: memoir does **not** read `world/setting.md` (no Travel Matrix — real settings live in `research/sources.md` and the chapter's own setting prose) and does **not** read `plot/canon-log.md` (memoir uses `people-log.md` for real-person consistency tracking instead).

## Writing Process

### Step 1: Review Chapter Plan
Read the chapter README.md outline:
- What's the chapter's PURPOSE?
- What CHANGES by the end?
- Which characters appear?
- POV character and their emotional state entering this chapter?
- How does this chapter connect to the previous and next?

### Step 2: Choose Writing Mode
Ask the user how they want to write this chapter (use AskUserQuestion):

- **Scene-by-scene (Recommended)** — Write one scene at a time (~900 Wörter als Soft-Target, je nach Szenen-Bedarf — manche brauchen 600, andere 1200). User reviews and corrects each scene before the next one is written. After all scenes are complete, user reads the full chapter for a final pass. This is slower per-chapter but produces higher quality with fewer full rewrites.
- **Full chapter** — Write the entire chapter in one pass. Target: 2500-4000 Wörter je nach Genre/Outline, als Richtwert — die Outline-Word-Count im README ist der primäre Anker. Traditional approach.
- **Batch all chapters** — Write all remaining chapter drafts sequentially. Only for rough first drafts when speed matters more than quality.

If the user has already chosen a mode in this session (e.g. during a previous chapter), remember their choice and skip the question — but still mention which mode is active.

### Step 2b: Mark Chapter as In-Progress
Call MCP `start_chapter_draft(book_slug, chapter_slug)` before any prose. **Why:** Flips status `Outline → Draft` so dashboards and `get_book_progress` reflect active work immediately, not only when Step 7 closes the chapter. Idempotent — only forward, safe to call redundantly. Also migrates legacy README frontmatter into `chapter.yaml` on first touch (canonical source per #16) without data loss.

---

### Mode A: Scene-by-Scene Writing (Recommended)

#### Step A1: Scene Plan
Break the chapter outline into scenes based on the Scene Beats in `README.md`. Present the plan: `Scene N: [description] (~XXX words)`. Target ~900 words/scene (vary 600-1200 as needed); total should approximate the chapter's target.

#### Step A2: Write One Scene
Apply ALL craft rules (Steps 3-6 from Mode B). Write ONLY this scene.

**Pre-write tactical check:** if the scene involves combat OR group movement (`walk`, `hike`, `drive`, `attack`, `mission`, `enter the building`, `approach`, multi-character formation), the brief's `tactical_constraints` may already be populated. If not — or if the scene's specific outline differs — call MCP `verify_tactical_setup(book_slug, scene_outline_text, characters_present)` and resolve every warn-severity warning before drafting.

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

Scan markers: `like [noun/clause]`, `as [adj] as`, `as if/as though`, `the way [subj] [verb]`, `moved/felt/sounded/looked/seemed like`, `resembled`, `reminded ___ of`, `gave the impression of`, `had the air of`, and the failure pattern `the kind of [noun] that [clause]`.

For each hit: answer literal-resemblance and real-work honestly. Apply author-voice bias from the profile (simile-heavy authors get more leeway than sparse ones). Flag any paragraph with two or more simile markers — either each does distinct work or all but the strongest are cut. Reject dead similes on sight (*pale as a ghost*, *quick as lightning*, etc.). Revise: cut and replace with a beat first, swap the vehicle second, keep only if rework genuinely earned it.

The brief's `recent_simile_count_per_chapter` shows what the last 3 chapters used — if a paragraph would push above ~3-4, cut harder. Book CLAUDE.md ## Rules in the brief's `rules_to_honor` override author-voice leniency.

For clean scenes, silence is fine. When cuts happen, optionally note "Simile-Scan: N cut, M revised" alongside the scene metadata line. Do not skip — decorative similes are the recurring failure mode `prose-style.md` and `anti-ai-patterns.md` cannot catch alone.

---

### Step 7: Save and Update (both modes)
1. Draft is at `{project}/chapters/{chapter}/draft.md`. Count words — report to user.
2. **Extract promises (Issue #150)** — Before flipping status to `Review` or `Final`, walk the completed draft and identify setup-elements (locked drawers, character claims, cryptic warnings, unresolved clues — full taxonomy in `reference/craft/plot-logic.md`). For each: short concrete description (8–14 words), target chapter slug if the chapter outline names it else `unfired`, status `active`. Cap at 8 per chapter. Persist via MCP `register_chapter_promises(book_slug, chapter_slug, promises)`. If the chapter places no promises, pass an empty list — this writes a placeholder so the index knows the chapter was processed. Skip this step when staying at `Draft` (mid-chapter saves don't lock in promises).
3. Chapter status: MCP `update_field()` on `chapter.yaml` → `Review` / `Final` (per user) or leave `Draft`. Book-level status auto-derives via the #21 indexer.
4. **Update `plot/timeline.md`** — one row per story-day (memoir: real-date row). MANDATORY.

**Fiction (`book_category: fiction`):**

5. **Update Travel Matrix** in `world/setting.md` if new routes appeared.
6. **Update `plot/canon-log.md`** — new facts. If revising, mark changed facts `CHANGED` with old version in Notes, and add downstream chapters to the Revision Impact Tracker.

**Memoir (`book_category: memoir`):**

5. **Update `plot/people-log.md`** — what each named person did, said, believed, or revealed in this chapter. The memoir analogue of canon-log; consistency across chapters is a truth standard, not just a craft standard. Create the file on first chapter close if it does not exist. Mark changed/corrected facts `CHANGED` with old version in Notes.
6. **No Travel Matrix update** — memoir documents real settings via research, not a structured matrix. Note any new place names worth tracking in `research/sources.md` instead.

**Both modes — universal step:**

7. **Update Chapter Timeline** in this chapter's `README.md` — every time-anchored event with `~HH:MM`. MANDATORY (future chapters depend on it). Memoir uses real clock times.

### Step 8: Self-Review (both modes)
Before presenting to user (in full-chapter mode) or after all scenes assembled (in scene-by-scene mode), quick-check:
- Does the opening hook?
- Does the ending compel?
- Is there conflict in every scene?
- Does the POV character's emotional state change?
- Would a reader know which character is speaking without dialog tags?
- **Simile discipline** — Confirm the Step 6c scan ran on every scene/section. No decorative or illogical comparisons survived. No stacked similes. No dead similes. `the kind of X that Y` constructions inspected.
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
- Resolve `book_category` in Step 0 before any prerequisite load. The fiction and memoir prerequisite sets are non-overlapping.
- Author profile is LAW. SHOW don't tell. Every scene needs conflict (memoir: every scene needs *stakes* — the lived equivalent). Dialog has subtext. Banned words trigger sentence rewrite.
- **Simile Discipline (Step 6c) is non-negotiable.** Every scene survives the two-question test before it enters `draft.md`. Author-voice bias = quality not quantity. See `simile-discipline.md`.
- Honor every entry in the brief's `rules_to_honor` (book CLAUDE.md ## Rules) — `severity: block` rules will be hard-blocked by the PostToolUse hook. Honor `tone_litmus_questions` (from `plot/tone.md`) when present.
- Never write a relative time reference without checking against the brief's `story_anchor` and `recent_chapter_timelines`. If the math doesn't work, adjust the prose — not the timeline.
- The Chapter Timeline section in `README.md` is MANDATORY at review status. Future chapters depend on it.
- Full-chapter mode: write in ONE PASS, then offer revision. Don't second-guess mid-flow.
- Scene-by-scene mode: write ONLY the current scene, then STOP and WAIT for explicit user approval (silence does not count). Scene text goes into `draft.md`, never chat — chat gets only metadata (scene number, word count, one-line summary). The user's inline-review workflow (`` ```textile {review_handle}: ... ``` `` blocks) breaks if prose sits in chat.
- **Read the full `draft.md` for review (GH#27).** When the user signals `{review_handle}:` blocks are ready (keywords: "kommentiert", "gelesen", "Feedback", "lies mal", "schau dir an"), ALWAYS call `Read` on the whole file first. The file-change system-reminder diff truncates for long files; trailing comments get silently dropped. Count the blocks you see and report the count.
- **One Claude Code session per chapter.** Cold-start brief is designed for a fresh session; scene-by-scene cycles burn context fast. If auto-compaction fires mid-chapter, earlier review decisions can be silently dropped. Finish the chapter, close, open a new session.
- **Stop if context pressure mounts.** A scene written after partial context loss degrades silently. End the session and resume fresh rather than shipping a degraded scene.
- Target word count from the chapter README.

### Fiction
- Continuity is global: check `plot/timeline.md`, `plot/canon-log.md`, and `world/setting.md` Travel Matrix in addition to the brief's recent chapter timelines. Never invent travel times. Never contradict canon. Use NEW versions of `CHANGED` facts.
- Respect genre conventions — they're the contract with the reader.

### Memoir
- **Consent gate is non-negotiable.** Before drafting any scene, read the brief's `consent_status_warnings`. Tier `refused` halts drafting — route to `/storyforge:character-creator` (memoir mode) for the cut/anonymize/re-frame decision. Tier `missing` requires the user's explicit decision before drafting. Tier `pending` requires user confirmation that drafting is okay (the consent request still needs to happen pre-publication).
- **Real names are sacred.** Frontmatter `real_name` stays in the people file; never render it into prose. Use the `name` field (which may be a pseudonym).
- **Scene-vs-summary discipline.** The first decision per page is dramatize or reflect. Default to mix; never default to one alone. See `book_categories/memoir/craft/scene-vs-summary.md`.
- **Emotional truth, not just factual truth.** Reconstructed dialogue carries the substance of remembered conversation, not a fabricated transcript. Memoir's truth standard is felt-sense first; rendered events second; verifiable facts third — but never violate any of the three.
- **No invented details.** If you don't know what someone wore, said, smelled like — leave it out, don't invent. The instinct to "fill in" with plausible detail is the fiction reflex; in memoir it produces fabrication.
- **No tidy lessons.** "Looking back I realize…", "what I learned was…", reflective platitudes — these are the memoir AI-tells. See `memoir-anti-ai-patterns.md`.
- **People-log over canon-log.** Memoir's continuity log is `plot/people-log.md` — what each named person did, said, believed, revealed across chapters. Inconsistency across chapters is not just craft failure, it is factual error.
- **No Travel Matrix.** Memoir does not pre-tabulate travel times — real life provides them. Specific real places get noted in `research/sources.md`, not in `world/setting.md`.
- **Genres are themes, not contracts.** A "horror memoir" is a memoir of horrifying experience, not a haunted-house plot. Don't impose plot-genre conventions on lived material.

## User Feedback Handling — CRITICAL

The user explicitly values being challenged over being blindly agreed with. Before implementing ANY user-requested change:

1. **Verify the claim** — Re-read the passage. Does it say what the user thinks it says?
2. **Check context** — Is there an earlier chapter that justifies the current version?
3. **Assess impact** — Would this change contradict canon or break continuity?
4. **Give honest feedback** — If the user is wrong, say so. Quote the text. Explain.
5. **Propose alternatives** — If the concern is valid but the suggested fix isn't, offer a better one.

Only after validation should the correction be applied.
