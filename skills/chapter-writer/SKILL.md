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
9. **World files** — Read relevant world/setting files if the chapter involves world elements.
10. **Series canon** — If part of a series, read `{series}/world/canon.md`.

## Writing Process

### Step 1: Review Chapter Plan
Read the chapter README.md outline:
- What's the chapter's PURPOSE?
- What CHANGES by the end?
- Which characters appear?
- POV character and their emotional state entering this chapter?
- How does this chapter connect to the previous and next?

### Step 2: Opening Hook
Write the first paragraph with extreme care. Reference `openings-and-endings.md`:
- Start with action, voice, or tension — NEVER with weather or waking up
- Ground the reader: who, where, when (subtly)
- Create a micro-question that pulls the reader forward
- Match the author's established voice from the FIRST sentence

### Step 3: Write Scene by Scene
Follow the Scene-Sequel structure from `chapter-construction.md`:

**Scene:**
- Goal: What does the POV character want in this scene?
- Conflict: What opposes them?
- Disaster/Outcome: How does it go wrong (or unexpectedly right)?

**Sequel:**
- Reaction: How does the character respond emotionally?
- Dilemma: What choices do they face?
- Decision: What do they decide to do next?

### Step 4: Apply Author Voice
For EVERY paragraph, check against the author profile:
- **Tone:** Does this match the author's tone descriptors?
- **Sentence rhythm:** Vary length per the author's style. Short. Then a longer, winding sentence that builds and breathes. Then short again.
- **Vocabulary:** Use words from the preferred list. NEVER use words from the banned list.
- **Dialog:** Each character sounds different. Use subtext. Minimal tags ("said" or action beats).
- **Sensory details:** All five senses, not just visual. Smell is the most evocative.
- **Specificity:** "A 1987 Oldsmobile with a cracked windshield" not "an old car."

### Step 5: Anti-AI Checks (DURING writing)
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

### Step 6: Chapter Ending
Reference `chapter-construction.md` on endings:
- Cliffhanger, revelation, decision, question, or emotional beat
- MUST make the reader want to turn the page
- Connect to the next chapter's opening (if planned)

### Step 7: Save and Update
1. Write draft to `{project}/chapters/{chapter}/draft.md`
2. Count words — report to user
3. Update chapter status to "Draft" via MCP `update_field()`
4. If this is the first chapter being drafted, update book status to "Drafting"

### Step 8: Self-Review
Before presenting to user, quick-check:
- Does the opening hook?
- Does the ending compel?
- Is there conflict in every scene?
- Does the POV character's emotional state change?
- Would a reader know which character is speaking without dialog tags?

Suggest: `/storyforge:chapter-reviewer` for detailed review.

## Rules
- The author profile is LAW. Every stylistic choice flows from it.
- SHOW, don't tell. Always. Unless telling serves pacing.
- Every scene needs conflict. No exceptions.
- Dialog must have subtext. Characters don't say what they mean.
- The banned word list is non-negotiable. Zero AI-tells.
- Continuity with previous chapters is mandatory — check names, locations, time of day.
- Write the chapter in ONE PASS, then offer revision. Don't second-guess mid-flow.
- Target word count from the chapter README. Respect genre conventions.
