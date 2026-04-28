---
name: voice-checker
description: |
  Check if written text sounds AI-generated. Compare against author profile for authenticity.
  Use when: (1) User says "voice check", "klingt das nach AI?",
  (2) After drafting, as a final authenticity gate.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> [chapter-slug]"
---

# Voice Checker — Anti-AI Authenticity Gate

## Prerequisites — MANDATORY LOADS

- **`anti-ai-patterns` reference** via MCP `get_craft_reference()`. **Why:** The flag-list — provides the catalog of AI-tells (vocabulary, structures, emotional patterns) the scan grades against. Without it, "AI-like" is a vibe, not a metric.
- **`prose-style` reference** via MCP. **Why:** Defines what good sentence-level craft looks like — the positive counterpart to the anti-pattern list, used for scoring specificity and rhythm.
- **`dos-and-donts` reference** via MCP. **Why:** The craft-rule baseline — many "AI-tells" are also general bad-craft tells; this reference distinguishes "AI-bad" from "fiction-bad."
- **Author profile** via MCP `get_author()`. **Why:** "AI-like" is relative to the author's documented voice — a sparse-prose author and a maximalist author cannot be graded by the same baseline.
- **Author vocabulary** from `~/.storyforge/authors/{slug}/vocabulary.md`. **Why:** Preferred/banned word list — the per-author enforcement layer that overrides the generic AI-tell list when in conflict.
- Read the text to check (chapter draft or entire book).

**Memoir mode — additional mandatory load:**

Call MCP `get_book_full(book_slug)` and read `book_category`. If it equals
`memoir`, additionally load:

- **`memoir-anti-ai-patterns.md`** via MCP `get_book_category_dir("memoir")` +
  `/craft/memoir-anti-ai-patterns.md`. **Why:** Memoir has five failure modes
  that fiction prompts don't catch: reflective platitudes, retrospective hinges,
  tidy lesson endings, hedging-as-humility, and therapeutic-vocabulary
  anachronisms. The universal anti-ai-patterns doc does not cover these.

If `book_category` is `fiction` or missing, skip the memoir load and proceed
with the standard 7-dimension analysis only.

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

### 8. Memoir-Specific AI-Tells _(memoir mode only — skip for fiction)_

Run this dimension only when `book_category: memoir`. Grade against
`memoir-anti-ai-patterns.md`. Six patterns to flag:

**8a. Reflective platitude** — a narrator pause that delivers universal-life
wisdom in elegant cadence. True the way fortune cookies are true; applies to
everyone, therefore to no one. Signal phrases: "we all face moments like these",
"grief is not a destination but a companion", "life has a way of…". **Fix:**
replace with a specific, slightly wrong thing only this narrator would say.

**8b. "Looking back" hinges** — the retrospective announcement construction:
"Looking back, I now realize…", "In hindsight, I see that…", "Only later did
I come to know…", "What I did not yet know was…". The announcement is the
problem — it tells the reader what is about to happen instead of just doing it.
**Fix:** cut the hinge; move directly into the realization.

**8c. Tidy lesson / earned wisdom** — the chapter ends with a clean takeaway.
The narrator has Learned Something. Real change is partial, contradicted by
next week's behavior; a lesson that announces itself as final almost certainly
wasn't. **Fix:** end on the moment, not the meaning. Cut the last paragraph if
it delivers the lesson; trust the reader.

**8d. Hedging as humility** — every claim softened by qualifiers until the
prose is upholstered in cotton: *perhaps*, *I think*, *maybe*, *some part of
me*, *in a sense*, *to a certain extent*, *in some way*. This is performative
uncertainty — the writer's fear of commitment, not the narrator's genuine doubt.
**Fix:** remove every qualifier on the first pass; restore only those marking
genuine uncertainty.

**8e. Therapeutic reframe** — anachronistic therapy vocabulary imposed on a
past self who didn't have it: *nervous system*, *dysregulated*, *attachment
style*, *somatic*, *trauma response*, *parts work*, *nervous system regulation*.
**Fix:** render the past-self's experience in the past-self's vocabulary; mark
the contemporary frame explicitly as retrospective if it matters at all.

**8f. Explanation-after-image** — every concrete image immediately followed by
its interpretation: "He set down the mug carefully — *the small ceremony of a
man trying to control what he could*." The explanation eats the image's work.
**Fix:** strip the explanation; trust the image. If it can't stand alone, make
it stronger.

Scoring for Dimension 8:
- 0 patterns found → 100/100
- 1 pattern found → 80/100 (note it; no hard stop)
- 2–3 patterns → 60/100 (revision recommended)
- 4+ patterns → 40/100 or below (rewrite recommended; flag as a systemic problem)

Report memoir tells **in their own labeled section** separate from the
universal-AI-tell findings, so the author sees which issues are memoir-specific
and which would also affect fiction.

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
| Memoir AI-Tells | X/100 | [memoir mode only — omit for fiction] |

### Flagged Words
[List with line numbers — max ~150 words, group by category if many]

### Memoir AI-Tells _(memoir mode only — omit section for fiction)_
[One subsection per pattern found (8a–8f). Quote the offending phrase,
name the pattern, give a one-sentence fix direction. Omit subsections
for patterns not found. If none found, write: "No memoir-specific
AI-tells detected."]

### Most AI-Like Passages
[Quote 3-5 passages that read most "AI" with explanations — max ~150 words per passage incl. explanation]

### Most Human-Like Passages
[Quote 3-5 passages that feel most authentic — max ~100 words per passage]

### Recommendations
[Specific rewrites for the worst offenders — max 5 entries, before/after pairs.
For memoir: prioritise memoir-specific tells (8a–8f) over universal tells
if both are present — memoir-specific issues are more reader-visible.]

### Verdict
[AUTHENTIC / NEEDS WORK / REWRITE RECOMMENDED]

VERDICT: PASS | WARN | FAIL
```

Verdict mapping (per the gate contract — see `reference/gate-contract.md`):

- **PASS** ↔ AUTHENTIC, score ≥ 70, no AI-tell vocabulary hits.
- **WARN** ↔ NEEDS WORK, score 50–69, or AI-tell hits with a clear path to a single-pass rewrite.
- **FAIL** ↔ REWRITE RECOMMENDED, score < 50, or systemic AI-tell patterns that require restructuring.

## Rules
- Run this as the gate before marking a chapter "Polished" — voice-check is the last thing between draft and shipped prose.
- A score below 70 means revision is needed.
- Below 50 means significant rewriting.
- Run the vocabulary scan as a hard gate before proceeding. If AI-tell words are found, STOP and request a rewrite of the affected sentences before re-scoring.
- Be specific with line numbers and quotes — generic "it sounds AI" is not actionable; quote the offending text.
- **Memoir mode:** always run Dimension 8 and report its findings in a separate section. Do NOT fold memoir-specific tells into the universal dimensions — the author needs to see the distinction between "this is bad prose" and "this is bad memoir prose". A passage can score well on universal dimensions and still be riddled with memoir-specific AI patterns.
- **Memoir mode:** hedging qualifiers (*perhaps*, *in some way*) score differently from fiction mode — in memoir they are performative safety behaviour, not stylistic choice. Flag all density above 2 per 500 words as a pattern, not as individual occurrences.
