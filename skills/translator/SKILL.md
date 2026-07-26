---
name: translator
description: |
  Translate a book chapter by chapter into another language.
  Use when: (1) User says "Übersetzen", "Übersetzung", "translate", "translate the book",
  "ins Englische/Spanische/Deutsche übersetzen", "target language", "foreign-language edition",
  (2) Book is complete or near-complete.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug> <target-language>"
---

# Translator

## Workflow

### Step 1: Setup
- Load book data via MCP `get_book_full()` — **Why:** source chapters and metadata are required for all translation steps; without this load the skill has no chapter content to translate.
- Load author profile via MCP `get_author(book.author)` (the `author` slug comes from `get_book_full`'s output) — **Why:** translation must preserve the author's rhythm, sentence length, and voice markers, not produce generic target-language prose.
- Create translation directory: `{project}/translations/{lang}/`, including its `chapters/` subdirectory
- Create glossary: `{project}/translations/{lang}/glossary.md`

### Step 2: Glossary First
Before translating any chapter, build a glossary. **This ordering holds even if the user asks to skip straight to chapter 1** — briefly explain the term-consistency/voice risk of skipping it, then still propose the glossary categories below before writing any chapter prose. Cover:
- Character names (keep or adapt?)
- Place names (translate or keep original?)
- Invented terms (magic system terms, world-specific vocabulary)
- Recurring phrases or motifs
- Cultural references that need adaptation

List terms concisely — one line per entry (`term: target-equivalent`). A term that needs an adaptation rationale (see Step 3) may append one short adaptation note on the same line (`term: target-equivalent — adaptation note, max one line`). No explanatory paragraphs.

Ask the user for preferences on names/terms, and wait for their answers before drafting Chapter 1 — a glossary of proposed categories with no confirmed entries does not satisfy this gate.

### Step 3: Chapter-by-Chapter Translation

**Sequencing gate: Translate one chapter, update the glossary, then wait for user review before starting the next chapter.** Batch-translation produces glossary drift and silent voice errors that compound — by the time the user reads chapter 5, chapters 1-4 have already accumulated mistranslated terms. **By default this gate holds even if the user asks to skip review or batch-translate several/all remaining chapters:** state the glossary-drift risk in your own words, then translate only the next single chapter — never translate a further chapter until the user has replied to the current one. This is not an unconditional refusal: if the user restates the batch request after hearing the risk, honor it — translate the requested run of chapters, add a one-line waiver note to the glossary (e.g. `[waiver: user requested chapters N–M batched on <date>, informed of glossary-drift risk]`), and mark every chapter after the first as unreviewed in your output. The final call is always the user's once they've been informed of the risk — this gate is a pushback, not a unilateral veto.

For each chapter:
1. Read the original draft
2. Translate maintaining:
   - Author's voice and rhythm (short sentences stay short, long stay long)
   - Dialog character (each character's voice must remain distinct in translation)
   - Wordplay and humor (adapt, don't translate literally)
   - Cultural references (adapt for target audience, or keep the original term and record the reader-facing context as a glossary adaptation note — never as an inline gloss in the chapter text)
   - Sensory details (find equivalent sensory language in target culture)
   - **Target word count: match source length, with tolerance depending on the language pair — roughly ±10% for pairs of similar density (e.g. EN↔DE), up to ±20% for expansion-prone pairs (e.g. EN→FR/ES/PT routinely run longer). Do not pad to hit a number; if drift exceeds the pair's expected range, check for added explanation rather than trimming voice. Do not add explanatory notes, translator comments, or expansions unless explicitly asked — this applies to wordplay/idiom/cultural-reference adaptations too: record the adaptation choice as a glossary entry (`term: target-equivalent — adaptation note, max one line`, the format defined in Step 2), never as an inline footnote or parenthetical in the chapter text itself.**
3. Save to `{project}/translations/{lang}/chapters/{chapter-slug}.md`
4. Update glossary with any new terms encountered
5. **STOP. Output:** "Chapter [N] saved. Please review and reply OK to proceed to Chapter [N+1], or reply with corrections — I'll verify them and confirm before continuing." Do not begin the next chapter until the user sends explicit confirmation. **A reply that includes any correction — even alongside praise ("looks great, but...", "otherwise fine") — is not the same as an unqualified OK.** Verify each correction per CLAUDE.md Rule 14 before applying it: quote the relevant passage, check context, assess impact. If the correction looks wrong — the user's grasp of the target language may be weaker than of the source — present your analysis of why the original may be stronger and explicitly ask whether to apply the change or keep the original; do not silently apply a correction you assess as a likely misread, and do not silently discard it either. Once confirmed, apply the correction(s) to the saved chapter file and show the revised passage before starting the next chapter; only an unqualified approval (or an explicit "no changes, proceed") unblocks Chapter [N+1] as-is.

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
- Translate chapter by chapter, with user review between chapters. Batch translation skips quality control and accumulates glossary drift. By default this holds even if the user asks to skip ahead or batch multiple chapters — surface the risk and translate one chapter at a time; if the user restates the request after hearing the risk, honor it and log a waiver note in the glossary (see Step 3).
- User corrections to a translated chapter are verified before being applied (CLAUDE.md Rule 14), never applied blind — the user's command of the target language may be weaker than of the source.
