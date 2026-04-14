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
8. **Character files** — Read all characters appearing in this chapter.
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

After writing the scene:
1. Present it to the user
2. Report word count for this scene
3. **WAIT for user feedback.** Do NOT proceed to the next scene until the user approves or corrects.

#### Step A3: User Review Loop
The user reads and may correct the scene. Handle corrections per the User Feedback Handling rules (verify, check context, assess impact, push back if wrong).

Once the user approves the scene (explicitly or by asking to continue):
1. Append the approved scene to `{project}/chapters/{chapter}/draft.md`
2. Move to the next scene (Step A2)

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

### Step 7: Save and Update (both modes)
1. Write draft to `{project}/chapters/{chapter}/draft.md` (in scene-by-scene mode, the full draft is already assembled)
2. Count words — report to user
3. Update chapter status to "Draft" (or "Review"/"Final" if user specified) via MCP `update_field()`
4. If this is the first chapter being drafted, update book status to "Drafting"
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
- **Litmus test** — If `plot/tone.md` exists, answer EVERY question from the Litmus Test section. If more than 1 answer is "no", flag it to the user and suggest specific revisions before proceeding.
- **Time consistency** — Verify that every time reference in the chapter (explicit or relative) is consistent with the Chapter Timeline you created in Step 7.

Suggest: `/storyforge:chapter-reviewer` for detailed review.

## Rules
- The author profile is LAW. Every stylistic choice flows from it.
- SHOW, don't tell. Always. Unless telling serves pacing.
- Every scene needs conflict. No exceptions.
- Dialog must have subtext. Characters don't say what they mean.
- The banned word list is non-negotiable. Zero AI-tells.
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
