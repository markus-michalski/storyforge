---
name: voice-checker
description: |
  Check if written text sounds AI-generated. Compare against author profile for authenticity.
  Use when: (1) User says "voice check", "klingt das nach AI?",
  (2) After drafting, as a final authenticity gate.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<book-slug> [chapter-slug]"
---

# Voice Checker — Anti-AI Authenticity Gate

## Prerequisites
- Load `anti-ai-patterns` reference via MCP `get_craft_reference()`
- Load `prose-style` and `dos-and-donts` references
- Load author profile via MCP `get_author()`
- Load author vocabulary from `~/.storyforge/authors/{slug}/vocabulary.md`
- Read the text to check (chapter draft or entire book)

## Analysis — 7 Dimensions

### 1. Vocabulary Scan
Scan for ALL words from the AI-tell list in `anti-ai-patterns.md`:
- Flag every occurrence with line number and context
- Check for over-use of abstract nouns (journey, landscape, tapestry, realm)
- Check for hedging language ("it's worth noting", "it should be mentioned")

### 2. Sentence Length Distribution
Measure sentence lengths across the text:
- Calculate mean, median, standard deviation
- **Human writing:** High variance (std dev > 8 words). Mix of 3-word fragments and 35-word complex sentences.
- **AI writing:** Low variance (std dev < 5 words). Suspiciously uniform.
- Flag sections where 5+ consecutive sentences are within 3 words of each other in length.

### 3. Paragraph Structure
- Are all paragraphs roughly the same length? (AI tell)
- Is there variety in paragraph openings? (AI tends to follow patterns)
- Are there single-sentence paragraphs for impact? (Human technique)
- Any "topic sentence → elaboration → conclusion" patterns repeating? (AI structure)

### 4. Dialog Authenticity
- Do all characters sound the same? (Biggest AI tell in fiction)
- Are there interruptions (em-dashes), fragments, trailing off (ellipses)?
- Is dialog perfectly grammatical? (Real speech isn't)
- Is there subtext, or is everything on-the-nose?
- Are dialog tags varied? (AI overuses creative tags; humans use "said")

### 5. Emotional Expression
- Are emotions NAMED ("She felt sad") or SHOWN (action, body language)?
- Does every emotional moment get a neat resolution? (AI tendency)
- Are there contradictory emotions? (Humans feel multiple things at once)
- Is there emotional restraint where appropriate? (Not every moment is dramatic)

### 6. Specificity Score
Rate the text's specificity:
- Generic: "a beautiful sunset" → AI
- Specific: "the sky turned the color of a bruised plum, bleeding into the lake" → Human
- Count generic descriptions vs. specific ones
- Flag "the [adjective] [noun]" patterns that add nothing

### 7. Author Profile Match
Compare against the defined author profile:
- Does the tone match? (sarcastic author shouldn't sound earnest)
- Is the sentence style consistent with profile?
- Are preferred words actually used?
- Are avoided patterns actually avoided?
- Does the pacing match the profile's setting?

## Output Format

```markdown
## Voice Check Report

### Overall Authenticity Score: [X]/100

### Dimension Scores
| Dimension | Score | Assessment |
|-----------|-------|------------|
| Vocabulary | X/100 | [Clean / Minor flags / Major flags] |
| Sentence Variance | X/100 | [Human-like / Borderline / AI-like] |
| Paragraph Structure | X/100 | [Varied / Somewhat uniform / Uniform] |
| Dialog Authenticity | X/100 | [Distinct voices / Similar / Identical] |
| Emotional Expression | X/100 | [Shown / Mixed / Told] |
| Specificity | X/100 | [Concrete / Mixed / Generic] |
| Author Match | X/100 | [Strong / Partial / Weak] |

### Flagged Words
[List with line numbers]

### Most AI-Like Passages
[Quote 3-5 passages that read most "AI" with explanations]

### Most Human-Like Passages
[Quote 3-5 passages that feel most authentic]

### Recommendations
[Specific rewrites for the worst offenders]

### Verdict
[AUTHENTIC / NEEDS WORK / REWRITE RECOMMENDED]
```

## Rules
- This is the FINAL quality gate before a chapter is marked "Polished"
- A score below 70 means revision is needed
- Below 50 means significant rewriting
- The vocabulary scan is non-negotiable — zero AI-tell words in final text
- Be specific with line numbers and quotes — don't just say "it sounds AI"
