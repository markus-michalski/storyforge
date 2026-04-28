---
name: create-author
description: |
  Create a new author profile with writing style, voice, and preferences.
  Use when: (1) User says "Autor anlegen", "create author", "Autorenprofil",
  (2) Before starting a first book project.
model: claude-opus-4-7
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

---

## Fiction Path

### Phase 1: Identity
Ask the user:
1. **Pen name** — What should this author be called?
2. **Primary genres** — Show available genres via MCP `list_genres()`. Select 1-3.
3. **Writing influences** — Which published authors inspire this persona? (e.g., "Stephen King meets Carmen Maria Machado")

### Phase 2: Voice Definition
Guide the user through voice choices (use AskUserQuestion):

1. **Narrative voice:** first-person, third-limited, third-omniscient, second-person
2. **Tense:** past or present
3. **Tone:** Select 2-4 from: sarcastic, dark-humor, atmospheric, lyrical, terse, warm, cold, irreverent, earnest, melancholic, playful, intense, detached, intimate
4. **Sentence style:** short-punchy, long-flowing, varied, minimalist
5. **Vocabulary level:** simple, moderate, advanced, archaic
6. **Dialog style:** naturalistic, stylized, minimal, heavy
7. **Pacing:** slow-burn, tension-driven, breakneck, literary
8. **Writing process (author_writing_mode):**
   - **Outliner** — Plans everything before writing (beats, chapter outlines, full plot map)
   - **Plantser (Hybrid)** — Knows the key story beats, discovers the rest scene by scene
   - **Discovery Writer (Pantser)** — Finds the story as they write; no outline before drafting

### Phase 3: Deeper Character
Ask open-ended questions:
- "What themes keep pulling this author back?" (e.g., isolation, identity, power)
- "What does this author NEVER do?" (e.g., happy endings, love triangles, info-dumps)
- "What's this author's signature move?" (e.g., unreliable narrators, gut-punch endings, dry wit in dark moments)

### Phase 5: Study (Fiction Optional)
Ask: "Do you have PDFs or text files from authors whose style you want to channel? → `/storyforge:study-author`"

---

## Memoir Path

Memoir profiles differ from fiction profiles in what matters: the author IS the material. Voice authenticity is even more non-negotiable — and the profile needs fields that fiction doesn't: relationship to material, subject position, and off-limits decisions.

### Phase 1: Identity (Memoir)
Ask the user:
1. **Name / pen name** — What should this author be called? (May use real name)
2. **Memoir scope tags** — What kind of memoir? (e.g., memoir-of-illness, memoir-of-family, memoir-of-place, memoir-of-addiction, memoir-of-work — these are not genres but thematic anchors)
3. **Writing influences** — Which memoirists or essayists inspire this voice? (e.g., Mary Karr, Tara Westover, Carmen Maria Machado, Ta-Nehisi Coates, Kiese Laymon, Roxane Gay, Paul Kalanithi)

### Phase 2: Voice Definition (Memoir)
Same universal voice questions as fiction, plus memoir-specific additions:

1. **Narrative voice:** first-person (default for memoir), or second-person (rare, experimental)
2. **Tense:** past (most common), present (immersive), or mixed (past for events, present for reflection)
3. **Tone:** Select 2-4 from: confessional, unflinching, elegiac, wry, tender, sardonic, reckoning, defiant, searching, intimate, measured, fierce
4. **Sentence style:** short-punchy, long-flowing, varied, minimalist
5. **Vocabulary level:** simple, moderate, advanced
6. **Pacing:** slow-burn, reflective, urgent, episodic
7. **Writing process (author_writing_mode):**
   - **Structured** — Outlines the narrative arc before drafting scenes
   - **Accumulative** — Writes scenes as they come, shapes structure in revision
   - **Discovery** — Finds the story by writing toward it; structure emerges

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

### Phase 3: Deeper Character (Memoir)
Ask open-ended questions tailored to memoir:
- "What do you want readers to understand that only YOU could tell them?" (The unique access — what only this author could have witnessed or lived)
- "What are you afraid to write?" (The avoidance points — often the most important material)
- "What is your 'why now'?" (Why is this the right moment to write this memoir? What changed?)
- "What will you protect?" (What relationships or people are you not willing to damage — and how does that shape the story you can tell?)

---

## Shared Phase 4: Create Profile

1. Use MCP `create_author()` with collected data
2. Call MCP `update_author(slug, "author_writing_mode", value)` to persist writing mode
3. For memoir authors, also call `update_author(slug, "subject_position", value)` and `update_author(slug, "off_limits", value)`
4. Load the generated `profile.md` and `vocabulary.md`
5. Review the banned words list (AI tells) — ask if user wants to add/remove any
6. For memoir: pre-populate memoir-specific AI tells from `book_categories/memoir/craft/memoir-anti-ai-patterns.md` (reflective platitudes, "looking back I realize", tidy lesson endings)
7. Show the complete profile to the user

## Shared Phase 5: Study (Optional)
- **Fiction:** "Do you have PDFs from authors whose style you want to channel? → `/storyforge:study-author`"
- **Memoir:** "Do you have personal journals, letters, or old writing to analyze for your authentic voice? → `/storyforge:study-author` (memoir mode)"

## Rules
- **MANDATORY:** Every profile must have the "avoid" list pre-populated with AI-tell words from `anti-ai-patterns.md`. For memoir, additionally pre-populate with memoir-specific AI tells.
- Tone descriptors should be SPECIFIC, not generic ("searching with dry wit" beats "introspective").
- Influences should be REAL authors the user has actually read.
- The profile is a living document — it evolves as the author writes.
- **Memoir:** off-limits decisions made here carry forward — they are not decoration. The ethics-checker and chapter-writer enforce them.
