---
name: translator
description: |
  Translate a book chapter by chapter into another language.
  Use when: (1) User says "Übersetzen", "translate", (2) Book is complete or near-complete.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> <target-language>"
---

# Translator

## Workflow

### Step 1: Setup
- Load book data via MCP `get_book_full()`
- Load author profile — the translation should preserve the author's VOICE
- Create translation directory: `{project}/translations/{lang}/`
- Create glossary: `{project}/translations/{lang}/glossary.md`

### Step 2: Glossary First
Before translating any chapter, build a glossary:
- Character names (keep or adapt?)
- Place names (translate or keep original?)
- Invented terms (magic system terms, world-specific vocabulary)
- Recurring phrases or motifs
- Cultural references that need adaptation

Ask the user for preferences on names/terms.

### Step 3: Chapter-by-Chapter Translation

**Sequencing gate: Translate one chapter, update the glossary, then wait for user review before starting the next chapter.** Batch-translation produces glossary drift and silent voice errors that compound — by the time the user reads chapter 5, chapters 1-4 have already accumulated mistranslated terms.

For each chapter:
1. Read the original draft
2. Translate maintaining:
   - Author's voice and rhythm (short sentences stay short, long stay long)
   - Dialog character (each character's voice must remain distinct in translation)
   - Wordplay and humor (adapt, don't translate literally)
   - Cultural references (adapt for target audience or keep with context)
   - Sensory details (find equivalent sensory language in target culture)
3. Save to `{project}/translations/{lang}/chapters/{chapter-slug}.md`
4. Update glossary with any new terms encountered
5. **Wait for user review of this chapter and any glossary updates before starting the next chapter.**

### Step 4: Review
After all chapters:
- Consistency check across chapters (are terms used consistently?)
- Verify glossary completeness
- Offer to export translated version via `/storyforge:export-engineer`

## Rules
- Translation is voice-for-voice, not word-for-word.
- Maintain the author's rhythm and style in the target language.
- Cultural adaptation > literal accuracy.
- The glossary is the single source of truth for term consistency.
- Translate chapter by chapter, with user review between chapters. Batch translation skips quality control and accumulates glossary drift.
