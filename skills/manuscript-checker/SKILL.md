---
name: manuscript-checker
description: |
  Scan a complete FICTION book manuscript for prose-quality issues that only
  surface when the whole thing is read in one pass: book-rule violations
  from the book's CLAUDE.md, plot holes, cliché hits, dialogue punctuation
  anomalies (Q-word + period), POV filter-word overuse, per-chapter adverb
  density, and cross-chapter repetition (similes, character tells, blocking
  tics, structural patterns, signature phrases).
  Use when: (1) `book_category == "fiction"` (or missing) AND user says
  "manuscript check", "prose check", "repetition check", "Wiederholungen
  prüfen", "prose tics", "Buch prüfen", (2) All chapters have cleared
  chapter-reviewer → chapter-humanizer → chapter-proofreader (the last step
  of the revision phase, not the Drafting→Revision transition), (3)
  Full-manuscript revision pass, (4) User wants a craft-level health check
  before export.
  Memoir books → use `/storyforge:manuscript-checker-memoir` instead.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug> [--interactive]"
---

# Manuscript Checker (Fiction)

This skill is the fiction variant of manuscript-checker, split out per Issue
#138 so fiction-only sessions never load the memoir-specific detection
categories and presentation rules, and memoir-only sessions never load
content that only applies to fiction. See `/storyforge:manuscript-checker-memoir`
for the memoir variant.

Full-manuscript prose-quality gate. Catches the class of issues that creep in
when chapters are written in isolation and only become visible when the book
is read end to end: repeated phrasing, worn-out clichés, POV filter words,
adverb pile-ups, dialogue punctuation drift, plot holes, and — most
importantly — violations of rules the author wrote into the book's CLAUDE.md.

## Step 0 — Verify fiction mode

Before any other prerequisite load:

1. **Load book data** via MCP `get_book_full(slug)`.
2. Read `book_category`. Treat missing as `fiction`. If it is `memoir`, stop
   and tell the user:
   > *This book's `book_category` is `memoir`. Use
   > `/storyforge:manuscript-checker-memoir` for memoir manuscript checks —
   > it adds the anonymization/tidy-lesson/reflective-platitude/timeline
   > passes this variant doesn't run.*
3. Otherwise proceed with the workflow below.

## When to run

- After **all** chapter drafts exist (or at least most of them).
- At the **end** of the revision phase — after every chapter has cleared
  `chapter-reviewer` → `chapter-humanizer` → `chapter-proofreader` (same
  ordering `chapter-humanizer` and `chapter-proofreader` document, and the
  same row `next-step`'s routing table uses: "Revision (all chapters
  proofread)" → manuscript-checker). It does not run *before*
  chapter-reviewer — this checker catches cross-chapter drift in prose that
  has already been through per-chapter craft review, humanizing, and
  proofreading, not a substitute pre-check for any of those passes.
- Does not replace `chapter-reviewer` (single-chapter craft check) or
  `voice-checker` (AI-tell gate) or `continuity-checker` (timeline/location).
  This one catches a different problem: prose drift across chapters.

**Note on simile coverage.** The `simile` category in this checker is
*cross-chapter n-gram repetition* — the same simile phrase appearing in
multiple chapters. Per-simile *quality* is covered separately by
`reference/craft/simile-discipline.md`, enforced at write-time by
`chapter-writer` (Step 6c) and at review-time by `chapter-reviewer`. See
`reference/craft/repetition-category-rules.md` for how the two combine
during Step 5's interactive fix mode.

## Detection categories

| Category | What it catches | Severity logic |
|---|---|---|
| `book_rule_violation` | Patterns from book_rules DB (rendered in `<book>/CLAUDE.md ## Rules (from DB)`) | always high |
| `plot_hole` | Causality inversions + dropped/unfired Chekhov's-gun promises (Issue #150). Sub-category in phrase prefix (`[causality_inversion]` / `[chekhov_gun]`). | high — story-logic breaks reader trust |
| `cliche` | Curated banlist of worn-out phrasings | always high |
| `question_as_statement` | Dialogue starting with a Q-word but ending with `.` | high if ≥5 hits |
| `filter_word` | POV-distancing verbs per chapter (>3/1k words) | high if >6/1k |
| `adverb_density` | `-ly` adverbs per chapter (>8/1k words) | high if >14/1k |
| `sentence_repetition` | Identical 8-15-word sentences across chapters | always high |
| `snapshot` | ≥5 consecutive descriptive sentences, no action, no dialog | always medium |
| `callback_dropped` | Callback past deadline or must-not-forget + >10 ch silence | always high |
| `callback_deferred` | Callback not seen in >10 drafted chapters | always medium |
| `book_rules_unreadable` / `callbacks_unreadable` | Meta-finding (Issue #579/#584): the book_rules/callback DB couldn't be read (e.g. a series book not yet linked via `add_book_to_series()`) — this category was never actually checked, not verified clean. `occurrences` is empty; `source_rule` carries the underlying error with the fix command. Not a prose finding — see Step 5's handling note below. | always high |
| `simile` / `character_tell` / `blocking_tic` / `sensory` / `structural` / `signature_phrase` | Cross-chapter n-gram repetition | high if ≥4 hits |
| `character_tell` (paraphrased) | Same body-part tell reworded each time, e.g. "shoulders came down" vs. "shoulders had dropped" — a second, additive `character_tell` source alongside the n-gram one above. `phrase` reads `"<body part> (varied phrasing)"`, a synthetic label, not manuscript text | medium ≥5 hits, high ≥10 hits |

Sort priority: `book_rule_violation` → `plot_hole` (story logic) → `cliche` → all others by severity.

## Workflow

### 1. Resolve target book

If the user provided a slug, use it. Otherwise call MCP `get_session()` and
use the active book. If still ambiguous, call `list_books()` and ask which
one.

### 1b. Load author profile

Call MCP `get_author(book.author)` using the `author` slug from
`get_book_full`'s response (already loaded in Step 0) — the interactive fix
mode in Step 5 needs the profile's `writing_discoveries.style_principles`
and `writing_discoveries.recurring_tics` fields to honor author-designated
stylistic choices (e.g. "flat declarative questions are part of the voice")
before proposing rewrites (see Rules below). Not to be confused with the
`signature_phrase` detection category above, which is unrelated cross-chapter
n-gram repetition. If `author` is empty or `get_author` returns an `error`
key (legacy books with no `author` field), skip this and proceed without
profile context — don't block the scan on it.

### 2. Run the scan

**If the user is asking specifically about Callback Register status** (not a
full manuscript check), skip this step and use `verify_callbacks(book_slug)`
instead — see "Callback Register findings" below for the full
satisfied/deferred/potentially_dropped breakdown it returns. Only run the
full scan below for a general manuscript-health request.

Call MCP tool `scan_manuscript(book_slug)` with default thresholds.
Optional parameters:

- `min_occurrences` (default 2) — raise to 3 for very long books to focus
  on the worst offenders (affects the n-gram repetition layer only).
- `max_findings_per_category` (default 40) — cap to keep the report focused.
- `write_report` (default true) — also writes
  `<book>/research/manuscript-report.md`.

The tool returns:

```json
{
  "book_slug": "...",
  "chapters_scanned": 34,
  "findings_count": 120,
  "summary": {
    "book_rule_violation": {"high": 3, "medium": 0},
    "cliche": {"high": 5, "medium": 0},
    "question_as_statement": {"high": 1, "medium": 0},
    "filter_word": {"high": 4, "medium": 6},
    "adverb_density": {"high": 2, "medium": 3},
    "callback_dropped": {"high": 1, "medium": 0},
    "callback_deferred": {"high": 0, "medium": 2},
    "simile": {"high": 6, "medium": 14}
  },
  "report_path": ".../research/manuscript-report.md",
  "findings": [ { phrase, category, severity, count, occurrences: [...], has_quality_exception } ],
  "gate": {
    "status": "PASS | WARN | FAIL",
    "reasons": ["..."],
    "findings": [ { code, message, severity, location } ],
    "metadata": {
      "chapters_scanned": 34, "findings_count": 120,
      "rule_violations": 3, "hard_rule_violations": 2
    }
  }
}
```

`has_quality_exception` (category `book_rule_violation` only, default `false`) marks a finding whose
source rule documents its own "sometimes fine" carve-out (e.g. "only when the comparison does real
character work" — Issue #608) — a regex match can't tell whether *this* occurrence satisfies it, so
treat it as needing human judgment, not a reflex fix. `gate.metadata.rule_violations` counts every
`book_rule_violation` finding (hard or quality-exception); `hard_rule_violations` counts only the
ones that actually drove `gate.status` — read the second field when explaining why status is WARN
despite rule violations being present.

The `gate` envelope is the canonical verdict (see `reference/gate-contract.md`):

- **FAIL** when any `book_rule_violation` finding exists whose source rule does
  NOT document its own quality exception — the user's own rules outrank
  everything else.
- **WARN** when other findings exist, including `book_rule_violation` findings
  whose rule documents a quality exception (e.g. "only when the comparison
  does real character work" — Issue #608; a regex match can't judge whether a
  specific occurrence satisfies that exception, so it's advisory, not a hard
  block).
- **PASS** when zero findings.

Surface `gate.status` to the user as the headline before walking through the
top offenders. When chaining into other quality steps (export-engineer,
chapter-reviewer), the downstream skill can read `gate.status` directly
instead of re-counting findings.

### 3. Read the generated report

**Why:** The report contains all ranked findings with per-occurrence snippets that the MCP response summary omits — without reading it, interactive fix mode in Step 5 will miss lower-ranked items and lack the line context needed to propose accurate rewrites.

Read `report_path` so you have the full Markdown context. The detector
groups findings by category, ranks them, and writes a recommendation per
finding.

### 4. Present a focused summary

**Chat summary target: max ~300 Wörter.** The full report is on disk — chat is the headline, not the whole story.

1. Lead with `gate.status` (PASS / WARN / FAIL) as the literal headline —
   before the chapter/finding counts, not implied by them.
2. State chapters scanned + total findings + high-severity count by category.
3. Show the top 5 highest-severity findings across *all* categories, in the
   **sort priority order defined above**: `book_rule_violation` →
   `plot_hole` → `cliche` → all others by severity.
4. Tell the user the report path so they can open it.
5. Offer the next step (see section 5).

Example:

```
Gate: FAIL

Manuscript scan complete: 34 chapters, 120 findings.
High-severity: 3 book-rule violations, 5 clichés, 1 question-as-statement
cluster, 4 heavy-filter-word chapters, 2 heavy-adverb chapters, 6 repetitions.

Top offenders:
1. RULE: "Avoid vague-noun thing" — 7× (ch 03, 11, 14, 19, 22)
2. CLICHÉ: "blood ran cold" — 3× (ch 02, 17, 29)
3. DIALOGUE PUNCTUATION: 18 Q-word lines ending with "." (most in ch 05-09)
4. FILTER WORDS ch 08: felt×12, noticed×7, seemed×4 (23.0/1k words)
5. REPETITION: "for the first time" — 18× (structural)

Full report: research/manuscript-report.md

Want me to walk you through the high-severity findings interactively, or do
you want to revise on your own?
```

### 5. Optional: interactive fix mode

If the user says yes (or passes `--interactive`):

**Process ONE finding at a time. Wait for user response (keep / accept / skip / quit) before showing the next finding.**

**After presenting all findings for a category, STOP and wait for the user to respond before moving to the next category — unless that response is `quit`.** The user's keep/accept/skip answer to the *last finding in a category* resolves that finding only — it is NOT implicit consent to start the next category. Ask explicitly (e.g. "Ready to move on to `question_as_statement`?") and wait for that separate answer before showing the first finding of the next category. **`quit` is the one exception:** it ends the entire walkthrough immediately, whether given mid-category or on a category's last finding — never follow a `quit` with a "ready to move on?" prompt.

**`book_rules_unreadable` / `callbacks_unreadable` findings are not part of this walkthrough.** They carry no `occurrences` and no prose to rewrite — surface `source_rule` (the fix command) to the user once when summarizing the scan, then skip them entirely in interactive fix mode rather than presenting them as a category to step through.

Process findings in **category priority order**:

1. `book_rule_violation` (user explicitly wants these fixed)
2. `cliche` (always worth fixing)
3. `question_as_statement` (distinct fix pattern — see below)
4. `filter_word`, `adverb_density` (per-chapter craft fixes)
5. Repetition categories (`simile`, `character_tell`, etc.)

For each high-severity finding:

**Per finding: snippet + recommendation in ≤3 sentences. Do not expand unless the user asks.**

1. Show the phrase, category, and ALL occurrences with chapter + line + snippet.
2. Recommend which one to keep (if any) — explain reasoning anchored in the
   scene's POV/senses/mood.
3. Propose concrete rewrites for the others. Do NOT generate generic
   alternatives — read the surrounding prose first.
4. Ask the user: keep all / accept rewrites / skip / quit.
5. If the user accepts, apply edits via the Edit tool to the affected
   chapter `draft.md` files.

### Special handling for `question_as_statement`

See `reference/craft/question-as-statement-handling.md` for the two-option
(convert to `?` vs. keep the period as a load-bearing beat) treatment —
loaded when interactive fix mode (Step 5) reaches this category.

### 6. Record revision summary if the user fixed anything

If edits were applied, call `add_canon_fact(book_slug, chapter_num=<highest chapter number covered by this scan>, subject="manuscript-pass", fact="<summary>", domain="revision")` where `<summary>` lists: N book-rule violations fixed, N clichés replaced, N question-as-statement hits converted, N filter-word passes tightened, N repetitions pruned. `chapter_num` is the chapter's integer number (not its slug) — use the actual highest chapter number that has a draft, **not** `chapters_scanned` itself: `chapters_scanned` is a count (`len(drafts)`), and only equals the highest drafted chapter number when the drafted chapters happen to form a contiguous `1..N` block. A book drafted as chapters 01-05 and 12-40, for example, has `chapters_scanned=34` but a highest chapter number of 40 — `chapters_scanned` would silently anchor the fact to the wrong chapter there. When the drafted range isn't obviously contiguous, confirm the real highest number from `get_book_full(book_slug)`'s `chapters_data` — take the max `number` among entries with `has_draft: true`, since that list also contains outlined-but-undrafted chapters. Also don't narrow this to only the chapters the user happened to apply fixes to in this walkthrough — the note isn't tied to one specific chapter, so it anchors to the manuscript's scanned extent, not to the fix subset. The `canon_brief` projector reads from DB exclusively (Issue #297) — `plot/canon-log.md` is no longer read.

## Rules

- Always wait for user confirmation before applying fixes. The detector finds candidates; the human picks the keepers.
- **Book-rule violations are the user's own rules.** Treat them as authoritative. If the user's prose violates a rule they wrote, that's the most important fix — more important than any generic craft finding. If the user asks in the moment to downgrade, skip, or file it as a low-priority note, push back once first: remind them it's a rule *they* wrote for *this book*, so waiving it deserves at least one explicit confirmation rather than a same-breath override. The final call is still theirs — pushback opens a discussion, it never decides the outcome unilaterally (see the "verify user corrections" rule).
- A repeated phrase isn't always a bug. Some are deliberate motifs
  ("for a hundred and fifty years" might be a thematic refrain). When in
  doubt, ask.
- For repetition categories (`simile`, `character_tell`, `blocking_tic`, `sensory`,
  `structural`, `signature_phrase`), including the `character_tell`
  paraphrased-tic detector (`phrase` ending in `(varied phrasing)`) and the
  `simile` two-question-test mixed-outcome handling: see
  `reference/craft/repetition-category-rules.md`, loaded when interactive
  fix mode (Step 5) actually reaches one of these categories.
- **Clichés are high severity even at a count of 1.** A cliché doesn't
  become less clichéd by being rare.
- **Filter words are not always bad.** Internal realisations, dream logic,
  and explicit meta-narration all legitimately use them. Only push back on
  density, not on isolated uses.
- **Adverbs are not always bad.** The signal is density, not individual
  words. Use the top-N display to find the tics, not a blanket banlist.
- The user explicitly wants to be challenged (see global CLAUDE.md). If you
  think the detector is wrong about a finding, push back.
- Honor the author profile. If `writing_discoveries.style_principles` or
  `writing_discoveries.recurring_tics` (from Step 1b's `get_author` call)
  names a stylistic choice (e.g. "flat declarative questions are part of the
  voice"), exclude it from rewrite recommendations.

## Book-rule pattern extraction

See `reference/craft/book-rule-pattern-extraction.md` for how the scanner
extracts patterns from `book_rule_violation` findings' source rules
(backtick-regex, backtick-literal, ban-cue-qualified quoted phrases), and
how to sanity-check a rule via `list_book_rules(book_slug)` before scanning.

## Callback Register findings

`callback_dropped` and `callback_deferred` findings come from cross-referencing
the book's registered callbacks (same `book_rules` DB as rules above, populated
via `append_book_callback`/`register-callback`) against all chapter drafts. The
standalone MCP tool `verify_callbacks(book_slug)` runs the same
logic but returns the full three-bucket breakdown (satisfied / deferred /
potentially_dropped) without going through the scan pipeline.

Use `verify_callbacks` when the user asks specifically about callbacks; use
`scan_manuscript` for the full manuscript health check which includes callbacks
as one of its detection categories.

## Error handling

- Book not found → tell the user the expected path and stop.
- Zero chapters with `draft.md` → tell the user the checker only runs on
  drafted chapters and stop.
- Zero findings → that's a great result. Tell the user the prose is clean.
