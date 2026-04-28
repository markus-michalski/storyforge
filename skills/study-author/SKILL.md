---
name: study-author
description: |
  Analyze PDFs or text files to extract writing style and update an author profile.
  Use when: (1) User says "Buch studieren", "study this PDF", "Stil analysieren",
  (2) User wants to feed reference material to an author profile,
  (3) Memoir author wants to analyze their own journals, letters, or past writing.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<file-path> [author-slug]"
---

# Study Author — Style Extraction

## Purpose
Extract concrete writing patterns from texts and encode them into an author profile. This is what makes the author profile REAL — not just abstract descriptors but measurable patterns derived from actual prose.

**Two modes:**
- **Fiction mode** — Analyze a published author's work to extract craft patterns to emulate.
- **Memoir mode** — Analyze the memoirist's own personal writing (journals, letters, old blog posts, emails) to excavate their *authentic* voice from before they started worrying about craft.

## Step 0 — Detect Mode

Ask: *"Is this a published book/text by another author (fiction mode), or is this your own personal writing — journal, letters, diary (memoir mode)?"*

Alternatively, detect from context: if the book linked to the author slug has `book_category: memoir` AND the user provides their own writing, default to memoir mode.

---

## Fiction Mode

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

- **If No:** Stop here. Direct the user to `/storyforge:create-author` first. Style-extraction is meant to *refine* an existing profile, not to bootstrap one — bootstrapping from a single studied work risks copying that author's signature too closely.
- **If Yes:** Proceed to Phase 3.

### Phase 3: Write Analysis
Save analysis as `~/.storyforge/authors/{slug}/studied-works/analysis-{title}.md`

```markdown
---
title: "Original Book Title"
author_of_source: "Original Author Name"
analyzed: "2026-04-03"
word_count: 85000
mode: fiction
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

---

## Memoir Mode

The goal is opposite to fiction mode: instead of learning *someone else's* craft patterns, we excavate *the author's own unguarded voice* — the one they had before they started thinking about writing.

### Phase 1: Input
1. **Get file path** — User provides path to journals, letters, diary entries, old blog posts, emails, or any personal writing (PDF, TXT, MD)
2. **Get author** — Which author profile to update? Show list via MCP `list_authors()`
3. **Read the file** — Same file handling as fiction mode. If the journal is handwritten and photographed, ask the user to transcribe a representative excerpt (~2000–5000 words) first.

**No Phase 2.5 gate in memoir mode.** Studying your own personal writing IS a valid way to build or enrich a memoir author profile — it's not copying someone else's voice.

### Phase 2: Analysis (Memoir-Specific)

Analyze for these patterns — focused on authentic personal voice, not craft performance:

**Natural Voice Fingerprints:**
- How do sentences start? (Subject-verb? Fragment? Question? Aside?)
- What's the default tense for self-narration?
- How does the author refer to themselves? (I / we / one / unnamed)
- Recurring sentence starters, verbal tics, filler phrases
- How do they end entries — trailing off, punctuation, abrupt stop?

**Emotional Register:**
- Vocabulary for feelings — specific words they reach for (not generic happy/sad)
- How directly do they name emotions vs. describing action/body?
- Do they reflect or narrate? (Commentary-heavy vs. scene-heavy)
- Hedging patterns: "I think", "maybe", "I'm not sure but" — or confident assertion?

**Time Handling:**
- Do they skip time or dwell? (Weeks in a sentence or hours in a page?)
- How do they mark time: dates, seasons, relative anchors, none?
- Do they write in the moment or in retrospect?

**People Writing:**
- How do they introduce people — named, described, or thrown in with assumed context?
- How do they render speech — quoted, paraphrased, or summary?
- What adjectives do they reach for when describing someone they love / fear / resent?

**Personal Preoccupations:**
- Recurring themes, worries, joys — the things they return to unprompted
- Vocabulary clusters that signal their deepest concerns
- What do they *not* say but circle around? (absence patterns)

### Phase 3: Write Analysis
Save as `~/.storyforge/authors/{slug}/studied-works/analysis-{title}.md`

```markdown
---
title: "{Source description — e.g., 'Personal journals 2018-2022'}"
author_of_source: "{Author's own name}"
analyzed: "{date}"
word_count: {approximate}
mode: memoir
---

# Voice Excavation: {Source Description}

## Natural Voice Fingerprints
[Sentence starters, tense, self-reference, verbal tics]

## Emotional Register
[How feelings are expressed — specific words, direct vs. indirect]

## Time Handling
[How the author moves through time in personal writing]

## People Writing
[How they introduce, describe, quote the people in their life]

## Personal Preoccupations
[Recurring themes and vocabulary clusters]

## Unguarded Phrases to Preserve
[Specific turns of phrase that are uniquely theirs — the ones that would get "corrected" by an editor]

## What to Carry into the Memoir
[Synthesis: the 3-5 voice traits most worth protecting in polished prose]
```

### Phase 4: Update Profile
Update the author's `profile.md` and `vocabulary.md` based on findings:
- Add unguarded personal phrases to "Signature Phrases"
- Add personal vocabulary to "Preferred Words"
- Note the natural tense and self-reference style
- Flag hedging or avoidance patterns as memoir-specific risks to watch
- Add preoccupation themes — these are the memoir's authentic emotional spine

### Phase 5: Report
Show the user what was found and what changed. Specifically: which phrases are uniquely theirs and should survive editing, and which patterns (hedging, reflective platitudes) the memoir-anti-ai checker will flag.

---

## Rules (Both Modes)
- Extract PATTERNS only — verbatim text from studied works belongs nowhere in the profile. Verbatim copy is plagiarism risk and AI-tell.
- Multiple studied works refine the profile further — merge, don't overwrite. Each studied work is evidence; the profile is the synthesis.
- Flag any conflicts between studied works — surface to the user before merging.
- **Memoir mode:** privacy first. Journals contain sensitive material about third parties. The analysis extracts voice patterns — it does not summarize events, record names of people mentioned, or store any personal facts from the journals in the analysis file.
