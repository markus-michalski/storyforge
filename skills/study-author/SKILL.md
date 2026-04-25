---
name: study-author
description: |
  Analyze PDFs or text files to extract writing style and update an author profile.
  Use when: (1) User says "Buch studieren", "study this PDF", "Stil analysieren",
  (2) User wants to feed reference material to an author profile.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<file-path> [author-slug]"
---

# Study Author — Style Extraction

## Purpose
Extract concrete writing patterns from existing books/texts and encode them into an author profile. This is what makes the author profile REAL — not just abstract descriptors but measurable patterns derived from actual prose.

## Workflow

### Phase 1: Input
1. **Get file path** — User provides path to PDF, EPUB, DOCX, TXT, or MD file (max 50 MB)
2. **Get author** — Which author profile to update? Show list via MCP `list_authors()`
3. **Read the file** — Use the Read tool for text/markdown/PDF files. For EPUB and DOCX, the MCP server's `extract_text_from_file()` handles extraction. Supported: PDF, EPUB, DOCX, TXT, MD. Max 50 MB, max 200k words (larger files are auto-sampled from beginning, middle, and end).

### Phase 2: Analysis
Analyze the text for these concrete patterns:

**Sentence Metrics:**
- Average sentence length (words)
- Sentence length variance (high = human, low = AI)
- Shortest/longest sentences
- Ratio of fragments to complete sentences

**Vocabulary:**
- Unique word ratio (type-token ratio)
- Most frequent content words (nouns, verbs, adjectives)
- Vocabulary complexity (Flesch-Kincaid level)
- Distinctive word choices (unusual or characteristic words)
- Repeated phrases or verbal tics

**Dialog:**
- Dialog-to-narration ratio (% of text in quotes)
- Average dialog line length
- Tag usage ("said" frequency vs. action beats vs. tagless)
- Interruptions/fragments in dialog

**Structure:**
- Average paragraph length
- Scene transition patterns
- Chapter opening patterns (action, dialog, description, reflection)
- Chapter ending patterns

**Style Markers:**
- Metaphor frequency and type (concrete vs. abstract)
- Sensory detail distribution (visual, auditory, tactile, olfactory, gustatory)
- Active vs. passive voice ratio
- Adverb frequency
- Filter word frequency ("she saw", "he felt")

### Phase 2.5: Pre-Phase-3 Gate

Before writing analysis to disk, ask: **"Has this author profile already had an initial profile generated via `/storyforge:create-author`? (Yes/No)"**

- **If No:** Stop here. Direct the user to `/storyforge:create-author` first. Style-extraction is meant to *refine* an existing profile, not to bootstrap one — bootstrapping from a single studied work risks copying that author's signature too closely. Wait for explicit confirmation that the base profile exists before continuing.
- **If Yes:** Proceed to Phase 3.

### Phase 3: Write Analysis
Save analysis as `~/.storyforge/authors/{slug}/studied-works/analysis-{title}.md`

Format:
```markdown
---
title: "Original Book Title"
author_of_source: "Original Author Name"
analyzed: "2026-04-03"
word_count: 85000
---

# Style Analysis: {Title}

## Quantitative Metrics
[Tables with numbers]

## Distinctive Patterns
[Qualitative observations]

## Signature Techniques
[What makes this writing unique]

## Words & Phrases to Adopt
[Specific vocabulary to incorporate]

## Anti-Patterns Observed
[What this author avoids]
```

### Phase 4: Update Profile
Update the author's `profile.md` and `vocabulary.md` based on findings:
- Add characteristic words to "Preferred Words"
- Refine tone descriptors based on evidence
- Update sentence_style based on measured variance
- Add discovered "Signature Techniques"
- Update "Deliberate Imperfections" section

### Phase 5: Report
Show the user a summary of what was learned and what changed in the profile.

## Rules
- Extract PATTERNS only — verbatim text from studied works belongs nowhere in the profile. Verbatim copy is plagiarism risk and AI-tell.
- Multiple studied works refine the profile further — merge, don't overwrite. Each studied work is evidence; the profile is the synthesis.
- Flag any conflicts between studied works (e.g., one book uses first person, another uses third) — surface to the user before merging.
