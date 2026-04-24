---
name: chapter-writer
description: |
  Write a chapter in the author's voice, guided by craft knowledge and genre conventions.
  THE core creative skill. Use when: (1) User says "Kapitel schreiben", "write chapter",
  (2) Book is in Drafting status with chapters outlined.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<book-slug> <chapter-number>"
---

# Chapter Writer

## Prerequisites — MANDATORY LOADS
Before writing a SINGLE word, load ALL of these:

1. **Author profile** — MCP `get_author()`. This drives EVERYTHING: tone, vocabulary, rhythm, voice.
2. **Author vocabulary** — Read `~/.storyforge/authors/{slug}/vocabulary.md` for preferred/banned words.
3. **Book data** — MCP `get_book_full()` for genres, characters, plot context.
4. **Chapter outline** — Read `{project}/chapters/{chapter}/README.md` for beats and purpose.
5. **Previous chapter** — Read `{project}/chapters/{prev}/draft.md` for continuity, voice consistency.
6. **Genre README(s)** — MCP `get_genre()` for each genre. Respect conventions.
7. **Craft references** — MCP `get_craft_reference()`:
   - `chapter-construction` (hooks, scene-sequel, endings)
   - `dialog-craft` (subtext, beats, voice)
   - `show-dont-tell` (techniques, five senses)
   - `pacing-guide` (scene vs. summary, rhythm)
   - `anti-ai-patterns` (what to avoid at ALL costs)
   - `prose-style` (word choice, rhythm, devices)
   - `simile-discipline` (the two-question test for every comparison — mandatory for the pre-save scan in Step 6c)
8. **Character files** — For each character appearing in this chapter, call MCP `get_character(book_slug, character_slug)`. Use the slugified name (e.g. "Jane Doe" → "jane-doe"). If the tool returns `{"error": ...}`, note it and proceed — don't fall back to direct file reads.
9. **World files** — Read `{project}/world/setting.md` (includes the Travel Matrix). Mandatory if the chapter involves any travel or location references.
10. **Story timeline** — Read `{project}/plot/timeline.md`. Mandatory for ALL chapters. This is the canonical day/date reference.
11. **Canon log** — Read `{project}/plot/canon-log.md`. Mandatory for ALL chapters. This tracks established facts and revision changes. Pay special attention to facts marked `CHANGED` — never reference the old version.
12. **Series canon** — If part of a series, read `{series}/world/canon.md`.
13. **Tonal document** — Read `{project}/plot/tone.md` if it exists. This defines book-specific tonal rules, warning signs, and the litmus test for this chapter's position in the tonal arc. Older books may not have this file — proceed without it, but recommend creating one.
14. **Previous chapter timeline** — Read the `## Chapter Timeline` section from `{project}/chapters/{prev}/README.md`. This tells you what time of day the previous chapter ended, which determines when this chapter starts. Critical for time references like "an hour ago" or "that morning."
15. **Per-book CLAUDE.md** — MCP `get_book_claudemd(book_slug)`. Mandatory. Contains workflow rules, book-scoped rules, and callback register. Honor every entry:
    - **Rules**: Apply to this chapter's prose (e.g. "avoid passive voice").
    - **Workflow**: Follow the stated process (e.g. "scene-by-scene").
    - **Callbacks**: Weave in the listed characters, objects, or plot threads where natural. Do not force them, but look for an organic moment.

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

- **Scene-by-scene (Recommended)** — Write one scene at a time (~900 words). User reviews and corrects each scene before the next one is written. After all scenes are complete, user reads the full chapter for a final pass. This is slower per-chapter but produces higher quality with fewer full rewrites.
- **Full chapter** — Write the entire chapter in one pass. Traditional approach.
- **Batch all chapters** — Write all remaining chapter drafts sequentially. Only for rough first drafts when speed matters more than quality.

If the user has already chosen a mode in this session (e.g. during a previous chapter), remember their choice and skip the question — but still mention which mode is active.

### Step 2b: Mark Chapter as In-Progress
Before writing a single word of prose, call MCP `start_chapter_draft(book_slug, chapter_slug)`. This flips the chapter's on-disk status from `Outline → Draft` (only forward — chapters already at `Draft`, `Review`, `Polished`, or `Final` are left alone).

Why this matters:
- `get_book_progress` and the #21 book-tier derivation reflect active work immediately, not only after Step 7 closes the chapter. Without this, dashboards and next-step recommendations lie during active writing.
- For legacy chapters that still keep metadata in `README.md` frontmatter, the tool migrates it into `chapter.yaml` on first touch (canonical source per #16) and strips the frontmatter from README. No data loss.

The tool is safe to call redundantly (idempotent) — subsequent calls on a Draft chapter are a no-op.

---

### Mode A: Scene-by-Scene Writing (Recommended)

#### Step A1: Scene Plan
Before writing, break the chapter outline into individual scenes based on the Scene Beats in the chapter README.md. Present the plan to the user:

```
Scene 1: [Brief description] (~XXX words)
Scene 2: [Brief description] (~XXX words)
Scene 3: [Brief description] (~XXX words)
...
```

Target ~900 words per scene (can vary — some scenes need 600, others 1200). The total should approximate the chapter's target word count.

#### Step A2: Write One Scene
For the current scene, apply ALL craft rules (Steps 3-6 from Mode B below). Write ONLY this scene — do not continue into the next scene.

**Before appending, run the Step 6c Simile Discipline Scan on the scene text.** No scene goes into `draft.md` before the scan.

After writing the scene:
1. **Append the scene text directly to `{project}/chapters/{chapter}/draft.md`.** Do NOT paste the scene into chat. The user reviews in their editor and annotates with inline `` ```textile Markus: ... ``` `` comment blocks — that workflow only works if the prose is in the file. If `draft.md` does not exist yet, create it with a chapter heading (`# Chapter N: Title`) above the first scene. Separate scenes with a blank line; do not add scene headings unless the chapter outline specifies them.
2. In chat, report only: scene number, final word count, and a one-line summary of what the scene covers. Do NOT repeat the scene prose in chat.
3. **WAIT for user feedback.** Corrections come back as inline `Markus:` blocks inside `draft.md` — read them from the updated file and apply per the User Feedback Handling rules.

#### Step A3: User Review Loop
The user reads the scene in their editor and may add `` ```textile Markus: ... ``` `` comment blocks inline in `draft.md`.

**CRITICAL — Read-First Rule (GH#27):**
When the user signals that feedback is ready (any of: "kommentiert", "habe kommentiert", "gelesen", "Feedback da", "lies mal", "schau dir an", or any mention of `Markus:` in chat), you MUST call the `Read` tool on the full `draft.md` file BEFORE processing anything. **Never rely on the file-change `system-reminder` diff** — Claude Code truncates diffs for long files (observed cutoffs at 40, 140, 200, 267+ lines), which causes comments near the end of the file to be silently invisible.

Workflow:
1. User signals review is ready.
2. Call `Read` on `{project}/chapters/{chapter}/draft.md` — full file, no offset/limit unless the file exceeds 2000 lines.
3. Scan the fully-loaded content for ALL `` ```textile Markus: ``` `` blocks. Count them aloud to the user: "Ich sehe N Kommentare."
4. Process each block per User Feedback Handling (verify, check context, assess impact, push back if wrong).
5. If the count you report does not match what the user expected, re-read the file before proceeding — never guess.

Once the user approves the scene (explicitly or by asking to continue):
1. Remove any applied `Markus:` comment blocks from `draft.md` — the scene prose stays, the review annotations go.
2. Move to the next scene (Step A2).

#### Step A4: Chapter Completion
After ALL scenes are approved and appended to draft.md:
1. Notify the user: "Alle Szenen stehen. Bitte lies das komplette Kapitel und sag mir ob noch etwas geändert werden soll."
2. **WAIT for the user's final read.**
3. If corrections needed: apply them (with the usual verification).
4. When the user is satisfied: proceed to Step 7 (Save and Update).
5. Chapter status depends on user's verdict:
   - User says it's good → status "Review" or "Final" (ask which)
   - User wants another pass → stay in "Draft"

---

### Mode B: Full Chapter Writing

#### Step 3: Opening Hook
Write the first paragraph with extreme care. Reference `openings-and-endings.md`:
- Start with action, voice, or tension — NEVER with weather or waking up
- Ground the reader: who, where, when (subtly)
- Create a micro-question that pulls the reader forward
- Match the author's established voice from the FIRST sentence

**If this is Chapter 1:** Before writing, review the 13-Point First Chapter Checklist from `openings-and-endings.md`. Plan how this chapter will satisfy all 13 points — especially the load-bearing ones (4, 5, 9, 10, 13). After writing, run `/storyforge:chapter-reviewer` which will automatically apply the first-chapter check.

#### Step 4: Write Scene by Scene
Follow the Scene-Sequel structure from `chapter-construction.md`:

**Scene:**
- Goal: What does the POV character want in this scene?
- Conflict: What opposes them?
- Disaster/Outcome: How does it go wrong (or unexpectedly right)?

**Sequel:**
- Reaction: How does the character respond emotionally?
- Dilemma: What choices do they face?
- Decision: What do they decide to do next?

#### Step 5: Apply Author Voice
For EVERY paragraph, check against the author profile:
- **Tone:** Does this match the author's tone descriptors?
- **Sentence rhythm:** Vary length per the author's style. Short. Then a longer, winding sentence that builds and breathes. Then short again.
- **Vocabulary:** Use words from the preferred list. NEVER use words from the banned list.
- **Dialog:** Each character sounds different. Use subtext. Minimal tags ("said" or action beats).
- **Sensory details:** All five senses, not just visual. Smell is the most evocative.
- **Specificity:** "A 1987 Oldsmobile with a cracked windshield" not "an old car."

#### Step 6: Anti-AI Checks (DURING writing)
Reference `anti-ai-patterns.md` continuously:
- [ ] Sentence length varies wildly (2 words to 30+)
- [ ] No "delve", "tapestry", "nuanced", "vibrant", or other AI-tells
- [ ] Paragraphs are asymmetric (not all same length)
- [ ] No lists of three (AI loves triads)
- [ ] Dialog sounds like real people, not speeches
- [ ] Emotions shown through action/body, not named
- [ ] Specific details, not generic descriptions
- [ ] Imperfections exist — favorite transitions, recurring metaphors, the author's "tics"
- [ ] Not every scene wraps up neatly with an emotional bow

#### Step 6b: Chapter Ending
Reference `chapter-construction.md` on endings:
- Cliffhanger, revelation, decision, question, or emotional beat
- MUST make the reader want to turn the page
- Connect to the next chapter's opening (if planned)

---

### Step 6c: Simile Discipline Scan (MANDATORY, both modes, pre-save)

**This scan runs BEFORE any prose is appended to `draft.md` or saved.** In scene-by-scene mode (Mode A), run it per scene before Step A2's append. In full-chapter mode (Mode B), run it on the complete chapter text before Step 7.

Reference: `simile-discipline.md`. The scan enforces its two-question test.

**How to run the scan:**

1. **Grep the scene/chapter text for simile markers.** Walk the prose and flag every instance of:
   - `like [noun]` / `like [clause]`
   - `as [adj] as [noun]`
   - `as if [clause]` / `as though [clause]`
   - `the way [subject] [verb]`
   - `moved like`, `felt like`, `sounded like`, `looked like`, `seemed like`
   - `resembled`, `reminded [him/her] of`
   - `gave the impression of`, `had the air of`
   - `the kind of [noun] that [clause]` — this construction is a frequent failure mode and must be inspected even without an explicit simile marker.

2. **For each hit, answer both questions honestly:**
   - **Literal resemblance?** Does the vehicle actually, concretely resemble the tenor? Can the reader picture the comparison?
   - **Real work?** Does the simile clarify sensation, reveal character frame-of-reference, land a tonal beat, or compress description? Or is it decoration?

3. **Apply the author-voice bias.**
   - Check the author profile and vocabulary for simile-style notes.
   - If the author's voice is documented as simile-heavy with grounded, character-specific comparisons (e.g. Ethan Cole's everyday-life similes), apply the test with that register as context. Many similes can pass.
   - If the profile is silent or documents a sparse style, apply the test strictly. Default to cut-when-in-doubt.

4. **Scan for stack density.** Any paragraph containing two or more simile markers is flagged. Either each one is doing distinct, necessary work, or all but the strongest are cut.

5. **Scan for dead similes.** Reject the familiar ones on sight: *pale as a ghost*, *quiet as a mouse*, *quick as lightning*, *cold as ice*, *sharp as a knife*, *like a deer in headlights*, *like a kid in a candy store*. Replace or cut.

6. **Revise failed similes** in order of preference:
   - Cut entirely, replace with a concrete beat.
   - Swap the vehicle for one that actually resembles the tenor.
   - Keep only if, after rework, it genuinely does work.

7. **Honor book-CLAUDE.md simile bans** — the per-book CLAUDE.md is already in context from Prerequisite 15. Cross-check any rule banning specific comparison patterns (e.g. "no comparisons involving things the floor shouldn't do") and cut matching similes even if the discipline check would otherwise keep them. Book rules override author-voice leniency.

**Do not report the scan results in chat unless findings were significant.** For clean scenes, silence is fine. If you cut or revised similes, optionally note "Simile-Scan: N cut, M revised" in the scene metadata line alongside word count — this is a brief audit trail, not a review dump.

**Do not skip the scan to save time.** The pattern recurs chapter after chapter in real projects precisely because it's easy to leave decorative similes in place. The scan is the enforcement point that the general rules in `prose-style.md` and `anti-ai-patterns.md` don't have.

---

### Step 7: Save and Update (both modes)
1. Write draft to `{project}/chapters/{chapter}/draft.md` (in scene-by-scene mode, the full draft is already assembled)
2. Count words — report to user
3. Update chapter status via MCP `update_field()` on `chapter.yaml`:
   - User says it's good → `"Review"` or `"Final"` (ask which)
   - User wants another pass → leave at `"Draft"` (no call needed)
   - Note: the `Outline → Draft` flip already happened in Step 2b; this step only handles later transitions.
4. Book-level status — no explicit update needed. The #21 indexer derives the effective book status from chapter aggregates on every read, so the book's tier advances automatically (`Drafting` once any chapter is past Outline, `Revision` once all chapters are at Revision-rank, `Proofread` once all are Final). If the user wants the README frontmatter to reflect this on disk, they can run `update_field()` on the book README explicitly.
5. **Update timeline** — Add all days/events from this chapter to `{project}/plot/timeline.md`. One row per story-day. This is MANDATORY.
6. **Update Travel Matrix** — If new routes were introduced in this chapter, add them to the Travel Matrix in `{project}/world/setting.md`.
7. **Update Canon Log** — Add any new facts established in this chapter to `{project}/plot/canon-log.md`. If this is a **revision** of an existing chapter, mark changed facts as `CHANGED` with the old version in Notes, and add all downstream chapters to the Revision Impact Tracker.
8. **Update Chapter Timeline** — Fill in the `## Chapter Timeline` section in this chapter's `README.md`. Log every time-anchored event with approximate times (`~HH:MM`). Track elapsed durations. This is MANDATORY — future chapters depend on this for temporal consistency.

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
- The author profile is LAW. Every stylistic choice flows from it.
- SHOW, don't tell. Always. Unless telling serves pacing.
- Every scene needs conflict. No exceptions.
- Dialog must have subtext. Characters don't say what they mean.
- The banned word list is non-negotiable. Zero AI-tells.
- **Simile Discipline (Step 6c) is non-negotiable.** Every scene and every full chapter must survive the two-question test before it enters `draft.md`. Decorative, illogical, stacked, or dead similes do not ship. The author-voice bias means the check targets *quality*, not *quantity* — a simile-heavy author voice is fine as long as each simile does real work. Refer to `simile-discipline.md` for the full heuristic.
- Continuity is GLOBAL, not just local: always check `plot/timeline.md` and `world/setting.md` Travel Matrix, not just the previous chapter.
- Never invent a travel time or distance that isn't in the Travel Matrix. Add it first, then write.
- Never write a day-of-week or date that contradicts `plot/timeline.md`. Update timeline first if needed.
- Never contradict a fact in the Canon Log. If a fact is marked `CHANGED`, use the NEW version only.
- When revising a chapter: update the Canon Log FIRST, then write. This ensures downstream impact is tracked.
- If `plot/tone.md` exists, check the Tonal Arc table for this chapter's position. Write in the dominant mode specified. If you catch yourself drifting into a warning-sign pattern, stop and course-correct.
- Never write a relative time reference ("an hour ago", "ten minutes later") without checking it against the Chapter Timeline. If the math doesn't work, adjust the prose, not the timeline.
- The Chapter Timeline in README.md is MANDATORY for every chapter. No exceptions. Future chapters depend on it.
- In full-chapter mode: Write in ONE PASS, then offer revision. Don't second-guess mid-flow.
- In scene-by-scene mode: Write ONLY the current scene. STOP and WAIT for user feedback. NEVER proceed to the next scene without explicit approval. Each scene applies ALL craft rules (author voice, anti-AI, sensory details) — short scenes are not an excuse for lower quality.
- In scene-by-scene mode: Scene text goes **into `draft.md`**, not into chat. The user's inline-review workflow (`` ```textile Markus: ... ``` `` blocks inside the draft) breaks if prose sits in chat. Report only metadata in chat: scene number, word count, one-line summary.
- **Never trust the file-change system-reminder diff for user review (GH#27).** When the user signals that `Markus:` blocks are ready (keywords: "kommentiert", "gelesen", "Feedback", "lies mal", "schau dir an", or any `Markus:` mention), ALWAYS call the `Read` tool on the full `draft.md` file first. The system-reminder truncates diffs for long files, which has caused comments at the end of the file to be silently dropped. After reading, explicitly count the `Markus:` blocks you see and report the count to the user — if it mismatches their expectation, re-read before proceeding.
- **One Claude Code session per chapter.** Do not span a chapter across sessions. The chapter-writer's cold-start prerequisite load (author profile, tone doc, canon log, previous chapter, book CLAUDE.md) is designed for a fresh session; scene-by-scene review cycles burn context fast. If auto-compaction fires mid-chapter it can silently drop earlier review decisions. All persistent state is on disk — finish the chapter, close the session, open a new one for the next chapter.
- **Never power through mid-chapter compaction pressure.** If context pressure starts to mount during a scene-by-scene chapter, STOP and tell the user. A scene written after partial context loss degrades silently — previous review decisions, tonal cues, and canon facts may have been compressed away. Better to end the session and resume fresh than to ship a degraded scene.
- Target word count from the chapter README. Respect genre conventions.

## User Feedback Handling — CRITICAL

**NEVER blindly accept user corrections.** The user may:
- Misunderstand a passage (especially nuanced English prose)
- Miss context from an earlier chapter that explains the current text
- Be wrong about a fact (e.g., thinking a character said X when they said Y)
- Suggest a change that would create new inconsistencies

**Before implementing ANY user-requested change:**
1. **Verify the claim** — Re-read the relevant passage. Does it actually say what the user thinks it says?
2. **Check context** — Is there an earlier chapter that explains or justifies the passage?
3. **Assess impact** — Would this change contradict other established facts?
4. **Give honest feedback** — If the user is wrong or the change would cause problems, say so clearly. Quote the relevant text. Explain why the current version may actually be correct.
5. **Propose alternatives** — If the user's concern is valid but their suggested fix isn't ideal, propose a better solution.

Only after this validation should a correction be accepted and applied.
The user explicitly values being challenged over being blindly agreed with.
