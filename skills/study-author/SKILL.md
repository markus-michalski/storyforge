---
name: study-author
description: |
  Analyze PDFs or text files to extract writing style and update an author profile.
  Use when: (1) User says "Buch studieren", "study this PDF", "Stil analysieren",
  (2) User wants to feed reference material to an author profile,
  (3) Memoir author wants to analyze their own journals, letters, or past writing.
model: claude-opus-4-8
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
3. **Registry-Check** — Derive a `book_slug` from the file name (lowercase, hyphens). Check `~/.storyforge/authors/{slug}/studied-works/` for an existing `analysis-{book_slug}.md`. If found, warn the user: "This text has already been analyzed (`analysis-{book_slug}.md` exists). Re-analyzing may create duplicate Writing Discoveries. Continue anyway?"
4. **Source genres** — Ask: *"What genre(s) is this text? (e.g. dark-fantasy, thriller, lgbtq-romance) — leave blank if unknown or cross-genre."* Store as `source_genres` (comma-separated slug list). Used to tag genre-specific Writing Discoveries so chapter-writer skips them in different-genre books.
   After the user confirms the genres, validate each slug via MCP `get_genre(slug)`. For any slug not found in the registry:
   > "Genre '{slug}' ist nicht in der StoryForge-Registry. Der Genre-Filter greift erst, sobald das Genre angelegt ist. Jetzt `/storyforge:genre-creator {slug}` ausführen, oder trotzdem fortfahren? (Kein Datenverlust — `source_genres` wird gespeichert, Filter aktiviert sich nach genre-creator.)"
   User kann wählen: Pause für `genre-creator` oder fortfahren. Leeres Feld (unbekanntes/cross-genre Buch) überspringt die Validierung.
5. **Read the file** — For EPUB and DOCX, the MCP server's `extract_text_from_file()` handles extraction (the Read tool can't parse these). For text/markdown/PDF files under roughly 200k words, use the Read tool directly. **The beginning/middle/end auto-sampling only happens inside `extract_text_from_file()`** — the Read tool has no sampling behavior of its own. So for a PDF/TXT/MD file that is (or might be) over ~200k words, call `extract_text_from_file()` instead of Read, to get the sampling and the size/word-count guard. Supported: PDF, EPUB, DOCX, TXT, MD. Max 50 MB, max 200k words.

### Phase 1.5: Build Positive Extraction Checklist

Before analyzing the text, compile a genre-specific checklist of positive craft markers to look for.

1. **Load author profile** — MCP `get_author(slug)`. Read `primary_genres` and `tone` descriptors.
2. **Load genre Positive Markers** — For each genre in `primary_genres`, MCP `get_genre(name)`. Read the `## study-author: Positive Markers` section.
3. **Compose checklist** — Combine:
   - Genre-derived positive markers (from each genre's `## study-author: Positive Markers` section)
   - Tone-derived markers from the author profile (e.g. `tone: sarcastic` → explicitly look for sarcasm deployment patterns; `tone: dark-humor` → look for gallows humor techniques)
4. **Present checklist to user** — Show what will be tracked positively, allow the user to add or remove items before proceeding.

> Example output: "For lgbtq-supernatural-romance I'll specifically track: banter exchange frequency and triggers, sarcasm deployment points, vulnerability reveal pattern, mate/bond tension escalation, pack/found-family dynamic scenes. Additionally from your author's tone profile (sarcastic, playful, warm): humor-as-armor patterns, warmth signals after sarcasm drops."

**Wait for user to confirm or modify the checklist before proceeding to Phase 2. Do not begin text analysis until the user explicitly approves the checklist.** A general earlier "go ahead"/"sounds good" about running the study does NOT count as approving this specific checklist — the checklist doesn't exist yet at that point in the conversation. Present it, then end your turn and wait for the user's next message; don't present-and-proceed in the same response.

This checklist drives Phase 2. **Every item must be answered in the Phase 3 Positive Style Markers section — "not found" is a valid answer, but a checklist item may never simply be absent from the written file.** This applies even under Phase 5's terseness target: negative results get compressed to one line each, not dropped.

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

**Wait for explicit Yes/No answer before proceeding. Do not write any files until confirmed.**

### Phase 3: Write Analysis
Save analysis as `~/.storyforge/authors/{slug}/studied-works/analysis-{book_slug}.md` — reuse the exact `book_slug` derived in Phase 1 step 3, NOT the raw `title` string. The registry-check in step 3 looks for `analysis-{book_slug}.md`; saving under a different filename (e.g. a literal, unslugged title) silently breaks that duplicate-detection.

```markdown
---
title: "Original Book Title"
author_of_source: "Original Author Name"
analyzed: "2026-04-03"
word_count: 85000
mode: fiction
source_genres: "dark-fantasy, lgbtq"
---

# Style Analysis: {Title}

## Quantitative Metrics (~150 words; tables preferred)
[Tables with numbers]

## Positive Style Markers (~80 words per checklist item)
[One section per checklist item from Phase 1.5. For each: what was found, frequency/ratio if measurable, concrete examples from the text. "Not found" is a valid answer — record it so the absence is documented, not silently skipped.]

## Distinctive Patterns (~200 words total)
[Qualitative observations beyond the checklist]

## Signature Techniques (~150 words total)
[What makes this writing unique]

## Words & Phrases to Adopt (~100 words; bullet list)
[Specific vocabulary to incorporate]

## Anti-Patterns Observed (~100 words; bullet list)
[What this author avoids]
```

### Phase 4: Update Profile
Update the author's profile using MCP tools to ensure cache invalidation:

- **Tone / sentence_style / other frontmatter fields** — MCP `update_author(slug, field, value)` per field
- **Quantitative prose targets from Phase 2's Sentence/Dialog Metrics** — MCP `update_author(slug, field, value)` for each metric computed this pass, as a range centered on the observed value (± a few points to allow natural variance, e.g. an observed 42% dialog ratio → `"37–47%"`): `dialog_ratio_target`, `fragment_ratio_target`, `single_line_paragraph_ratio_target`, `avg_sentence_length_target` (words, not %). Overwrite on each study-author run — the target reflects the most recently studied work, consistent with the profile being a living document.
  **Why:** `author-check` reads these four exact field names (its Phase 1b) to override its generic defaults with author-specific targets (Phase 3 "Note on targets"). Without this write, the computed metrics live only in the analysis file and `author-check` silently falls back to generic defaults every time, regardless of what was actually measured here.
- **Positive style markers found** — **MANDATORY for every checklist item where a pattern was found.** MCP `write_author_discovery(author_slug, section="style_principles", text=<marker>, book_slug=<analyzed-work-slug>, genres=<source_genres from Phase 1 — empty string if unknown/universal>)` per item. Format: `**[Marker name]** — [concrete observation from this text, with frequency or ratio if measurable].` A positive finding that only lives in `studied-works/analysis-{title}.md` is invisible to chapter-writer. Every found positive marker must become a `style_principles` Writing Discovery. "Not found" items are skipped.
  **Why:** Writing Discoveries are the only data chapter-writer reads at runtime. A positive marker that lives only in the analysis file has zero effect on prose generation — it is permanently invisible to chapter-writer.
- **Signature Techniques discovered** (beyond the checklist) — MCP `write_author_discovery(author_slug, section="style_principles", text=<technique>, book_slug=<analyzed-work-slug>, genres=<source_genres from Phase 1>)`
  **Why:** Signature techniques not written as Discoveries never reach chapter-writer — analysis files are archives, not active guidance.
- **Anti-patterns to avoid** — MCP `write_author_banned_phrase(author_slug, phrase, reason=<why-avoid>)` per phrase
  **Why:** Banned phrases only block AI-tells in prose when registered in the author profile — analysis file entries are never checked at write time.
- **Preferred Words** — MCP `write_author_discovery(author_slug, section="style_principles", text=<entry>, book_slug=<analyzed-work-slug>, genres=<source_genres>)` per word/phrase. Format: `**{word}** — {usage context or frequency observation}.`
  **Why:** Vocabulary preferences in the analysis file are inert; only profile-level entries influence chapter-writer's word choices.
- **Deliberate Imperfections** — MCP `write_author_discovery(author_slug, section="recurring_tics", text=<entry>, book_slug=<analyzed-work-slug>, genres=<source_genres>)` per pattern. Format: `**{pattern}** — intentional; {why it works for this author}.`
  **Why:** Recurring tics must be in the author profile so chapter-writer can reproduce them rather than smoothing them away as errors.

### Phase 5: Report
Show a concise summary (~200 words total): top 3 findings, count of banned phrases added, count of Writing Discoveries written.

---

## Memoir Mode

The goal is opposite to fiction mode: instead of learning *someone else's* craft patterns, we excavate *the author's own unguarded voice* — the one they had before they started thinking about writing.

**Memoir mode has NO Phase 2.5 gate — this is a deliberate divergence from Fiction Mode below, not an oversight.** Fiction Mode's Phase 2.5 blocks studying a text until a `create-author` profile already exists, because bootstrapping a fiction profile from someone else's book risks copying their signature too closely. That risk doesn't exist here: studying your own personal writing IS a valid way to *build* a memoir profile from nothing, not just refine one. Do not port Fiction Mode's "has a profile already been created?" question into this workflow, even out of habit — proceed straight from Phase 1 into Phase 2 regardless of whether `create-author` has been run yet for this author.

### Phase 1: Input
1. **Get file path** — User provides path to journals, letters, diary entries, old blog posts, emails, or any personal writing (PDF, TXT, MD)
2. **Get author** — Which author profile to update? Show list via MCP `list_authors()`
3. **Derive `book_slug`** — From the file name (lowercase, hyphens), same rule as fiction mode. Used for the analysis filename in Phase 3.
4. **Read the file** — Same file handling as fiction mode. If the journal is handwritten and photographed, ask the user to transcribe a representative excerpt (~2000–5000 words) first.

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
Save as `~/.storyforge/authors/{slug}/studied-works/analysis-{book_slug}.md` — the `book_slug` derived in Phase 1 step 3.

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
Update the author's profile using MCP tools to ensure cache invalidation:

- **Tense / self-reference style / other frontmatter fields** — MCP `update_author(slug, field, value)` per field
- **Unguarded phrases to preserve** — MCP `write_author_discovery(author_slug, section="style_principles", text=<phrase>, book_slug=<analyzed-work-slug>)`
- **Hedging / avoidance patterns to flag** — MCP `write_author_banned_phrase(author_slug, phrase, reason="memoir-anti-ai: avoidance pattern")` per phrase
- **Preferred Words** — MCP `write_author_discovery(author_slug, section="style_principles", text=<entry>, book_slug=<analyzed-work-slug>)` per word. Format: `**{word}** — {usage context, how often, what it signals}.`
- **Signature Phrases** — MCP `write_author_discovery(author_slug, section="style_principles", text=<entry>, book_slug=<analyzed-work-slug>)` per phrase. Format: `**{phrase}** — {context in which it appears, why it's characteristic}.`
- **Preoccupation themes** — MCP `write_author_discovery(author_slug, section="style_principles", text=<entry>, book_slug=<analyzed-work-slug>)` per theme. Format: `**{theme}** — {how it surfaces in this author's writing, vocabulary cluster if applicable}.`

### Phase 5: Report
Show a concise summary (~200 words total): top 3 voice findings, count of Writing Discoveries written, count of banned phrases added. Specifically: which phrases are uniquely theirs and should survive editing, and which patterns (hedging, reflective platitudes) the memoir-anti-ai checker will flag.

---

## Rules (Both Modes)
- Extract PATTERNS only — verbatim text from studied works belongs nowhere in the profile. Verbatim copy is plagiarism risk and AI-tell.
- Multiple studied works refine the profile further — merge, don't overwrite. Each studied work is evidence; the profile is the synthesis.
- Flag any conflicts between studied works — surface to the user before merging.
- **Positive markers are mandatory Writing Discoveries (fiction mode):** Every positive style marker found via the Phase 1.5 checklist MUST be written as a `style_principles` Writing Discovery via `write_author_discovery`. The analysis file is an archive; Writing Discoveries are the living profile that chapter-writer acts on. A positive pattern that stays only in the analysis file has zero effect on how the author writes.
- **Memoir mode:** privacy first. Journals contain sensitive material about third parties. The analysis extracts voice patterns — it does not summarize events, record names of people mentioned, or store any personal facts from the journals in the analysis file.
