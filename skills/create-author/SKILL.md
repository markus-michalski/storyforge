---
name: create-author
description: |
  Create a new author profile with writing style, voice, and preferences.
  Use when: (1) User says "Autor anlegen", "create author", "Autorenprofil",
  (2) Before starting a first book project.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<author-name>"
---

# Create Author Profile

## Purpose
Author profiles are StoryForge's defense against generic AI output. Every stylistic choice — sentence rhythm, vocabulary, tone, dialog style — flows from the profile. A well-defined author writes DIFFERENTLY than a generic AI.

## Workflow

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

### Phase 3: Deeper Character
Ask open-ended questions:
- "What themes keep pulling this author back?" (e.g., isolation, identity, power)
- "What does this author NEVER do?" (e.g., happy endings, love triangles, info-dumps)
- "What's this author's signature move?" (e.g., unreliable narrators, gut-punch endings, dry wit in dark moments)

### Phase 4: Create Profile
1. Use MCP `create_author()` with collected data
2. Load the generated `profile.md` and `vocabulary.md`
3. Review the banned words list (AI tells) — ask if user wants to add/remove any
4. Show the complete profile to the user

### Phase 5: Study (Optional)
Ask: "Do you have PDFs or text files from authors whose style you want to channel? → `/storyforge:study-author`"

## Rules
- EVERY profile must have the "avoid" list pre-populated with AI-tell words from anti-ai-patterns.md
- Tone descriptors should be SPECIFIC, not generic
- Influences should be REAL authors the user has actually read
- The profile is a living document — it evolves as the author writes
