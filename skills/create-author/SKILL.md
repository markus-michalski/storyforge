---
name: create-author
description: |
  Create a new author profile with writing style, voice, and preferences.
  Use when: (1) User says "Autor anlegen", "create author", "Autorenprofil",
  (2) Before starting a first book project.
model: claude-opus-4-8
user-invocable: true
argument-hint: "<author-name>"
---

# Create Author Profile

## Purpose
Author profiles are StoryForge's defense against generic AI output. Every stylistic choice — sentence rhythm, vocabulary, tone, dialog style — flows from the profile. A well-defined author writes DIFFERENTLY than a generic AI.

## Workflow

### Phase 0: Detect Primary Category

Ask: *"Will this author primarily write fiction, memoir, or both?"*

- **Fiction** → proceed through Phase 1–5 as-is (fiction path)
- **Memoir** → Phase 1–3 branch into memoir-specific questions (memoir path)
- **Both** → run fiction path first; then add memoir-specific fields at the end of Phase 3

**Wait for user answer before proceeding to Phase 1.**

---

## Fiction Path

### Phase 1: Identity
Ask the user:
1. **Pen name** — What should this author be called?
2. **Primary genres** — Show available genres via MCP `list_genres()`. Select 1-3. If the user names a
   genre before seeing the list, or names one not returned by `list_genres()`, say so explicitly and
   ask them to pick from the real list — never write an unlisted genre string into the profile
   unaddressed. If they name more than 3, ask them to narrow it down rather than passing all of them
   to `create_author()`.
3. **Writing influences** — Which published authors inspire this persona? (e.g., "Stephen King meets Carmen Maria Machado"). If a named influence doesn't read as a real, published author — an invented-sounding name, or something offered as clearly fictional — ask the user to confirm it's real rather than persisting it as stated; see Rules below.
4. **Native language** — What is the author's mother tongue? (ISO 639-1 code, e.g. `de`, `fr`, `es`, `ja`) — used for explanations in language-aware skills like the proofreader
5. **Preferred writing language** — Which language does this author primarily write in? Used as fallback when a book has no `book_language` set. (default: `en`)

**Wait for user to answer all Phase 1 questions before moving to Phase 2.** This includes native
language and preferred writing language — don't treat them as optional metadata just because they
come last in the list; if the user's message answers only some of the 5, explicitly ask for the
specific ones still missing before moving on.

### Phase 2: Voice Definition
Guide the user through voice choices (use AskUserQuestion):

1. **Narrative voice:** first-person, third-limited, third-omniscient, second-person
2. **Tense:** past or present
3. **Tone:** Select 2-4 from: sarcastic, dark-humor, atmospheric, lyrical, terse, warm, cold, irreverent, earnest, melancholic, playful, intense, detached, intimate. If the user's answer isn't one of these
   (e.g. a generic word like "introspective"), don't write it through as-is — either map it to the
   closest listed option and confirm, or ask them to pick from the actual list; this also covers the
   Rules section's ban on generic tone descriptors.
4. **Sentence style:** short-punchy, long-flowing, varied, minimalist
5. **Vocabulary level:** simple, moderate, advanced, archaic
6. **Dialog style:** naturalistic, stylized, minimal, heavy
7. **Pacing:** slow-burn, tension-driven, breakneck, literary
8. **Writing process (author_writing_mode):**
   - **Outliner** — Plans everything before writing (beats, chapter outlines, full plot map)
   - **Plantser (Hybrid)** — Knows the key story beats, discovers the rest scene by scene
   - **Discovery Writer (Pantser)** — Finds the story as they write; no outline before drafting

**Do not ask Phase 3 questions until Phase 2 answers are confirmed.**

### Phase 3: Deeper Character
Ask open-ended questions:
- "What themes keep pulling this author back?" (e.g., isolation, identity, power)
- "What does this author NEVER do?" (e.g., happy endings, love triangles, info-dumps)
- "What's this author's signature move?" (e.g., unreliable narrators, gut-punch endings, dry wit in dark moments)

If the user volunteers an answer to one of these before it's asked (e.g. while still answering Phase
2), still explicitly ask the remaining Phase 3 question(s) — a volunteered answer to one question is
not permission to skip confirming the others.

**Wait for user confirmation before executing Phase 4 MCP calls.** This is a distinct step from the
user answering the last Phase 3 question — ask something like "Ready for me to create the profile?"
and wait for an explicit yes before calling `create_author()`; don't treat the arrival of the third
Phase 3 answer itself as that confirmation.

**"Both" category only:** append the memoir-specific fields (subject position, relationship to
material, off-limits — see Memoir Phase 2 below) here, after these fiction Phase 3 questions and
before the confirmation-and-Phase-4 step above. Do not rely on remembering this from Phase 0 alone —
this is the actual point in the conversation where it must happen.

### Phase 5: Study (Fiction Optional)
Ask: "Do you have PDFs or text files from authors whose style you want to channel? → `/storyforge:study-author`"

---

## Memoir Path

Memoir profiles differ from fiction profiles in what matters: the author IS the material. Voice authenticity is even more non-negotiable — and the profile needs fields that fiction doesn't: relationship to material, subject position, and off-limits decisions.

### Phase 1: Identity (Memoir)
Ask the user:
1. **Name / pen name** — What should this author be called? (May use real name)
2. **Memoir scope tags** — What kind of memoir? (e.g., memoir-of-illness, memoir-of-family, memoir-of-place, memoir-of-addiction, memoir-of-work — these are not genres but thematic anchors)
3. **Writing influences** — Which memoirists or essayists inspire this voice? (e.g., Mary Karr, Tara Westover, Carmen Maria Machado, Ta-Nehisi Coates, Kiese Laymon, Roxane Gay, Paul Kalanithi). If a named influence doesn't read as a real, published author, ask the user to confirm it's real rather than persisting it as stated; see Rules below.
4. **Native language** — What is the author's mother tongue? (ISO 639-1 code, e.g. `de`, `fr`, `es`, `ja`) — used for explanations in language-aware skills like the proofreader
5. **Preferred writing language** — Which language does this author primarily write in? Used as fallback when a book has no `book_language` set. (default: `en`)

**Wait for user to answer all Phase 1 questions before moving to Phase 2.**

### Phase 2: Voice Definition (Memoir)
Same universal voice questions as fiction, plus memoir-specific additions:

1. **Narrative voice:** first-person (default for memoir), or second-person (rare, experimental)
2. **Tense:** past (most common), present (immersive), or mixed (past for events, present for reflection)
3. **Tone:** Select 2-4 from: confessional, unflinching, elegiac, wry, tender, sardonic, reckoning, defiant, searching, intimate, measured, fierce. If the user's answer isn't one of these (e.g. a
   generic word like "introspective"), don't write it through as-is — either map it to the closest
   listed option and confirm, or ask them to pick from the actual list; this also covers the Rules
   section's ban on generic tone descriptors.
4. **Sentence style:** short-punchy, long-flowing, varied, minimalist
5. **Vocabulary level:** simple, moderate, advanced
6. **Pacing:** slow-burn, reflective, urgent, episodic
7. **Writing process (author_writing_mode):**
   - **Structured** — Outlines the narrative arc before drafting scenes
   - **Accumulative** — Writes scenes as they come, shapes structure in revision
   - **Discovery** — Finds the story by writing toward it; structure emerges

   Memoir uses this three-term vocabulary, not fiction's (Outliner/Plantser/Discovery Writer). If the
   user answers with a fiction term here (e.g. "outliner"), map it to the closest memoir equivalent
   ("Structured") and confirm — never persist the literal fiction-path word into a memoir author's
   `author_writing_mode`.

**Memoir-specific fields (ask separately):**

8. **Subject position** — Whose story is primarily at the center?
   - **Writing-self** — Primarily about the author's own experience and inner life (e.g., *Wild*, *Hunger*)
   - **Writing-other** — The author as witness; another person or community is the center (e.g., *The Glass Castle*, *Between the World and Me*)
   - **Shared story** — Author and another person equally central

9. **Relationship to material** — How close are you to these events, emotionally and temporally?
   - *Recent (< 5 years):* Still processing; emotional distance may be limited
   - *Mid-range (5–20 years):* Some perspective, emotional residue still present
   - *Distant (20+ years):* Full retrospective vantage; risk is sentimentalization
   Ask: "This shapes how much retrospective commentary vs. in-scene immediacy the memoir will need."

10. **Off-limits** — What is absolutely NOT going to appear in this memoir?
    - Family members who have refused or would refuse consent?
    - Events too raw to write about yet?
    - Information that would harm living people if published?
    Save these in the profile as `off_limits` — the chapter-writer and ethics-checker will honor them.
    Even if the user states off-limits items unprompted elsewhere in the conversation, read them back
    explicitly for confirmation before treating them as final — per the Rules section, these are not
    decoration and downstream skills enforce them as written.

**Do not ask Phase 3 questions until Phase 2 answers are confirmed.**

### Phase 3: Deeper Character (Memoir)
Ask open-ended questions tailored to memoir:
- "What do you want readers to understand that only YOU could tell them?" (The unique access — what only this author could have witnessed or lived)
- "What are you afraid to write?" (The avoidance points — often the most important material)
- "What is your 'why now'?" (Why is this the right moment to write this memoir? What changed?)
- "What will you protect?" (What relationships or people are you not willing to damage — and how does that shape the story you can tell?)

**Wait for user confirmation before executing Phase 4 MCP calls.**

---

## Shared Phase 4: Create Profile

**Critical — `create_author()` only accepts `name`, `genres`, `tone`, `voice`, `tense`.** Every other
field it writes (`sentence_style`, `vocabulary_level`, `dialog_style`, `pacing`, `themes`,
`influences`) is a hardcoded template default (`"varied"` / `"moderate"` / `"naturalistic"` /
`"tension-driven"` / `[]` / `[]`), regardless of what the user actually answered in Phase 2/3/1. If
the user's answer differs from the default, it is silently lost unless patched with `update_author()`
afterward — always compare each collected value against the tool's defaults and patch every field
that differs, not just the three named in steps 2-3 below.

1. Use MCP `create_author()` with collected data (name, genres, tone, voice, tense only)
2. Call MCP `update_author(slug, "author_writing_mode", value)` to persist writing mode
3. Call MCP `update_author(slug, "native_language", value)` and `update_author(slug, "preferred_writing_language", value)`
4. Call MCP `update_author()` once per remaining Phase 2/3 answer that differs from `create_author()`'s
   defaults: `sentence_style`, `vocabulary_level`, `dialog_style`, `pacing` (Phase 2), and `themes`,
   `influences` (Phase 1/3, collected as prose — join into a list). These are real `_ALLOWED_AUTHOR_FIELDS`
   and are NOT persisted by `create_author()` itself — skipping this step means the user's actual
   answers get silently replaced by generic defaults.
5. For memoir authors, also call `update_author(slug, "subject_position", value)`,
   `update_author(slug, "relationship_to_material", value)`, and `update_author(slug, "off_limits", value)`
   — all three memoir-specific fields collected in Phase 2, not just the two most obviously named.
6. Load the generated `profile.md` and `vocabulary.md`
7. Review the banned words list (AI tells) — ask if user wants to add/remove any (brief: list entries only, no prose commentary)
8. For memoir: call MCP `write_author_banned_phrase(author_slug, phrase, reason)` once per memoir-specific
   AI tell from `book_categories/memoir/craft/memoir-anti-ai-patterns.md` (at minimum: "reflective
   platitude", "looking back I realize", "tidy lesson ending") — this must be a real write, not just a
   claim in the summary; show these separately from the base fiction/universal banned-words list so
   the user can see what was added.
9. Show the complete profile as a compact YAML-style summary (~150 words). Do not add prose commentary
   — no greeting, no closing sentence, output ends with the summary block itself.

## Shared Phase 5: Study (Optional)
- **Fiction:** "Do you have PDFs from authors whose style you want to channel? → `/storyforge:study-author`"
- **Memoir:** "Do you have personal journals, letters, or old writing to analyze for your authentic voice? → `/storyforge:study-author` (memoir mode)"

## Rules
- **MANDATORY — Why:** Anti-AI vocabulary is the primary defense against generic output. Always pre-populate the avoid list from `anti-ai-patterns.md` before showing the profile. For memoir, additionally load `memoir-anti-ai-patterns.md`.
- Tone descriptors should be SPECIFIC, not generic ("searching with dry wit" beats "introspective").
- Influences should be REAL authors the user has actually read — if a name doesn't read as a real,
  published author (invented-sounding, or presented as a character rather than a person), check with
  the user in Phase 1 before treating it as confirmed. This is not just an aspiration — act on it at
  the point the name is collected, not only as an afterthought.
- The profile is a living document — it evolves as the author writes.
- **Memoir:** off-limits decisions made here carry forward — they are not decoration. The ethics-checker and chapter-writer enforce them.
