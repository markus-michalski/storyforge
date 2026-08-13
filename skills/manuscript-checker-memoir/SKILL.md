---
name: manuscript-checker-memoir
description: |
  Scan a complete MEMOIR book manuscript for prose-quality issues that only
  surface when the whole thing is read in one pass: book-rule violations
  from the book's CLAUDE.md, cliché hits, dialogue punctuation anomalies
  (Q-word + period), POV filter-word overuse, per-chapter adverb density,
  cross-chapter repetition (similes, character tells, blocking tics,
  structural patterns, signature phrases), plus five memoir-specific passes:
  anonymization leaks, tidy-lesson endings, reflective platitudes, timeline
  ambiguity, and real-people name-form consistency.
  Use when: (1) `book_category == "memoir"` AND user says "manuscript check
  (memoir)", "prose check", "repetition check", "Wiederholungen prüfen",
  "prose tics", "Buch prüfen", (2) All chapters have cleared
  chapter-reviewer-memoir → chapter-humanizer → chapter-proofreader (the last
  step of the revision phase, not the Drafting→Revision transition), (3)
  Full-manuscript revision pass, (4) User wants a craft-level health check
  before export.
  Fiction books → use `/storyforge:manuscript-checker` instead.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug> [--interactive]"
---

# Manuscript Checker (Memoir)

This skill is the memoir variant of manuscript-checker, split out per Issue
#138 so memoir-only sessions never load content that only applies to
fiction, and fiction-only sessions never load the memoir-specific detection
categories and presentation rules. See `/storyforge:manuscript-checker` for
the fiction variant.

Full-manuscript prose-quality gate. Catches the class of issues that creep in
when chapters are written in isolation and only become visible when the book
is read end to end: repeated phrasing, worn-out clichés, POV filter words,
adverb pile-ups, dialogue punctuation drift, and — most importantly —
violations of rules the author wrote into the book's CLAUDE.md. For memoir,
it additionally catches privacy and craft issues specific to writing about
real people and lived events: anonymization leaks, tidy-lesson endings,
reflective platitudes, timeline ambiguity, and inconsistent name forms.

## Step 0 — Verify memoir mode

Before any other prerequisite load:

1. **Load book data** via MCP `get_book_full(slug)`.
2. Read `book_category`. If it is `fiction` (or missing), stop and tell the
   user:
   > *This book's `book_category` is `fiction`. Use
   > `/storyforge:manuscript-checker` for fiction manuscript checks — the
   > anonymization/tidy-lesson/reflective-platitude/timeline passes this
   > variant runs do not apply to invented material.*
3. Otherwise load `book_categories/memoir/README.md` and
   `book_categories/memoir/craft/memoir-anti-ai-patterns.md` before presenting
   findings — memoir-specific recommendations need that context.

**Why:** Memoir-specific recommendations (anonymization blockers, tidy-lesson patterns, reflective-platitude classification) require this context — without it findings will be misclassified and privacy blockers may be downgraded to craft suggestions.

## When to run

- After **all** chapter drafts exist (or at least most of them).
- At the **end** of the revision phase — after every chapter has cleared
  `chapter-reviewer-memoir` → `chapter-humanizer` → `chapter-proofreader`
  (same ordering `chapter-humanizer` and `chapter-proofreader` document, and
  the same row `next-step`'s routing table uses: "Revision (all chapters
  proofread)" → manuscript-checker). It does not run *before*
  chapter-reviewer-memoir — this checker catches cross-chapter drift in
  prose that has already been through per-chapter craft review, humanizing,
  and proofreading, not a substitute pre-check for any of those passes.
- Does not replace `chapter-reviewer-memoir` (single-chapter craft check) or
  `voice-checker` (AI-tell gate) or `continuity-checker` (timeline/location)
  or `memoir-ethics-checker` (consent/defamation/anonymization scan — a
  different, dedicated gate; this checker's `anonymization_leak` category
  catches a narrower, prose-level symptom of the same underlying risk).
  This one catches a different problem: prose drift across chapters.

**Note on simile coverage.** The `simile` category in this checker is
*cross-chapter n-gram repetition* — the same simile phrase appearing in
multiple chapters. Per-simile *quality* (is this comparison illogical?
decorative?) is covered by `reference/craft/simile-discipline.md` and
enforced at write-time by `chapter-writer-memoir` (Step 6c) and at
review-time by `chapter-reviewer-memoir`. When walking the `simile` findings
in interactive fix mode (section 5), apply the two-question test from
`simile-discipline.md` to each hit before deciding whether to keep or
rewrite — a repeated simile that also fails the discipline check is a clear
cut; a repeated simile that does real work in each location may be an
intentional motif.

## Detection categories

All memoir books get the base checks below plus five memoir-specific passes.

### Base checks

| Category | What it catches | Severity logic |
|---|---|---|
| `book_rule_violation` | Patterns from book_rules DB (rendered in `<book>/CLAUDE.md ## Rules (from DB)`) | always high |
| `plot_hole` | Causality inversions (Issue #150). Sub-category in phrase prefix (`[causality_inversion]`) — the `chekhov_gun` sub-category (unfired promises) is fiction-only and does not fire for memoir. | high — narrative-logic breaks reader trust |
| `cliche` | Curated banlist of worn-out phrasings | always high |
| `question_as_statement` | Dialogue starting with a Q-word but ending with `.` | high if ≥5 hits |
| `filter_word` | POV-distancing verbs per chapter (>3/1k words) | high if >6/1k |
| `adverb_density` | `-ly` adverbs per chapter (>8/1k words) | high if >14/1k |
| `sentence_repetition` | Identical 8-15-word sentences across chapters | always high |
| `snapshot` | ≥5 consecutive descriptive sentences, no action, no dialog | always medium |
| `callback_dropped` | Callback past deadline or must-not-forget + >10 ch silence | always high |
| `callback_deferred` | Callback not seen in >10 drafted chapters | always medium |
| `simile` / `character_tell` / `blocking_tic` / `sensory` / `structural` / `signature_phrase` | Cross-chapter n-gram repetition | high if ≥4 hits |
| `character_tell` (paraphrased) | Same body-part tell reworded each time, e.g. "shoulders came down" vs. "shoulders had dropped" — a second, additive `character_tell` source alongside the n-gram one above. `phrase` reads `"<body part> (varied phrasing)"`, a synthetic label, not manuscript text | medium ≥5 hits, high ≥10 hits |

### Memoir-specific checks

| Category | What it catches | Severity logic |
|---|---|---|
| `anonymization_leak` | Real name appearing in manuscript despite people/ profile marking the person as anonymized | always high — pre-publication blocker |
| `tidy_lesson_ending` | Chapter's final paragraph closes on a moral/lesson summary instead of a moment | high if ≥3 cues, medium if 2 |
| `reflective_platitude` | Density of retrospective commentary per chapter ("looking back", "in hindsight", "what I learned") | high if ≥3 hits, medium if 2 |
| `timeline_ambiguity` | Density of temporal hand-waving per chapter ("at some point", "eventually", "years later") | high if >6/1k words, medium if >3/1k |
| `real_people_consistency` | Same person's display name appearing in inconsistent capitalization or forms across chapters | always medium |

Sort priority: `book_rule_violation` → `anonymization_leak` (privacy-critical) → `plot_hole` (narrative logic) → `cliche` → all others by severity.

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

**Presentation differences for memoir findings:**
- Surface `anonymization_leak` findings first and mark them as
  **pre-publication blockers** — these are not craft suggestions, they are
  privacy issues that must be resolved before the manuscript leaves the author.
- For `tidy_lesson_ending` findings: quote the last paragraph and ask the
  author whether the lesson language is load-bearing or can be cut.
- For `reflective_platitude` findings: distinguish between narrating-self
  commentary (legitimate in memoir) and filler platitudes (cut).
- For `timeline_ambiguity` findings: suggest the smallest possible anchor
  ("late summer 1987" beats "a few years later") rather than pushing for
  exact dates everywhere.

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
    "anonymization_leak": {"high": 1, "medium": 0},
    "cliche": {"high": 5, "medium": 0},
    "question_as_statement": {"high": 1, "medium": 0},
    "filter_word": {"high": 4, "medium": 6},
    "adverb_density": {"high": 2, "medium": 3},
    "callback_dropped": {"high": 1, "medium": 0},
    "callback_deferred": {"high": 0, "medium": 2},
    "simile": {"high": 6, "medium": 14}
  },
  "report_path": ".../research/manuscript-report.md",
  "findings": [ { phrase, category, severity, count, occurrences: [...] } ],
  "gate": {
    "status": "PASS | WARN | FAIL",
    "reasons": ["..."],
    "findings": [ { code, message, severity, location } ],
    "metadata": { "chapters_scanned": 34, "findings_count": 120, "rule_violations": 3 }
  }
}
```

The `gate` envelope is the canonical verdict (see `reference/gate-contract.md`):

- **FAIL** when any `book_rule_violation` finding exists — the user's own rules
  outrank everything else.
- **WARN** when other findings exist but no rule violations. **Caveat:**
  `anonymization_leak` also maps to WARN, not FAIL — a memoir manuscript
  whose only issues are `anonymization_leak` findings will show `Gate:
  WARN`. Do not let that read as "nothing urgent"; annotate the headline
  itself (see Step 4).
- **PASS** when zero findings.

Surface `gate.status` to the user as the headline before walking through the
top offenders. When chaining into other quality steps (export-engineer,
chapter-reviewer-memoir), the downstream skill can read `gate.status`
directly instead of re-counting findings.

### 3. Read the generated report

**Why:** The report contains all ranked findings with per-occurrence snippets that the MCP response summary omits — without reading it, interactive fix mode in Step 5 will miss lower-ranked items and lack the line context needed to propose accurate rewrites.

Read `report_path` so you have the full Markdown context. The detector
groups findings by category, ranks them, and writes a recommendation per
finding.

### 4. Present a focused summary

**Chat summary target: max ~300 Wörter.** The full report is on disk — chat is the headline, not the whole story.

1. Lead with `gate.status` (PASS / WARN / FAIL) as the literal headline —
   before the chapter/finding counts, not implied by them. Per Step 2's
   caveat, a memoir manuscript with only `anonymization_leak` findings shows
   `Gate: WARN` — annotate the headline itself, e.g. `Gate: WARN — 3
   pre-publication privacy blockers`.
2. State chapters scanned + total findings + high-severity count by category.
3. Show the top 5 highest-severity findings across *all* categories, in the
   **sort priority order defined above**: `book_rule_violation` →
   `anonymization_leak` → `plot_hole` → `cliche` → all others by severity. Label
   `anonymization_leak` entries explicitly as **pre-publication blockers**,
   same framing as Step 1b's presentation differences — not a generic craft
   suggestion.
4. Tell the user the report path so they can open it.
5. Offer the next step (see section 5).

Example:

```
Gate: WARN — 3 pre-publication privacy blockers

Manuscript scan complete: 34 chapters, 120 findings.
High-severity: 3 anonymization leaks, 5 clichés, 1 question-as-statement
cluster, 4 heavy-filter-word chapters, 2 heavy-adverb chapters, 6 repetitions.

Top offenders:
1. ANONYMIZATION LEAK: "Sarah" named directly in ch 03, 11, 14 despite anonymized profile
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

Process findings in **category priority order**:

1. `book_rule_violation` (user explicitly wants these fixed)
2. `anonymization_leak` (privacy blocker — fix before any other category)
3. `cliche` (always worth fixing)
4. `question_as_statement` (distinct fix pattern — see below)
5. `filter_word`, `adverb_density` (per-chapter craft fixes)
6. `tidy_lesson_ending`, `reflective_platitude`, `timeline_ambiguity`
7. Repetition categories (`simile`, `character_tell`, etc.)
8. `real_people_consistency` (last — name-form cleanup, no prose rewrite needed)

**`anonymization_leak`, `tidy_lesson_ending`, `reflective_platitude`, and `timeline_ambiguity`
do NOT use the generic snippet+recommendation format below on their own — apply Step 1b's
"Presentation differences for memoir findings" treatment for each one specifically**
(pre-publication-blocker framing for `anonymization_leak`; quote the final paragraph and ask
load-bearing-or-cut for `tidy_lesson_ending`; distinguish narrating-self commentary from filler for
`reflective_platitude`; propose the smallest anchor rather than an exact date for
`timeline_ambiguity`) before falling back to the generic steps below for anything the
category-specific treatment doesn't cover (e.g. still asking keep/accept/skip/quit).
`real_people_consistency` has no dedicated presentation treatment — use the generic
snippet+recommendation format for it, same as any base-check category.

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

Flat-delivery questions ("Who did this.") are a legitimate stylistic choice
(McCarthy-style) used sparingly. At scale they read as monotonous or buggy.
**Do not blanket-convert.** For each hit offer two options:

- **(A) Convert to a real question mark.** The default — most dialogue wants
  this.
- **(B) Keep the period, pair it with a narrative beat.** For moments where
  the flatness is load-bearing:

  > "Who?"
  > It was a demand, not a question.

Ask the user per hit, or bulk-apply (A) after a sample. A good heuristic: if
the surrounding paragraph already establishes the character's flat delivery,
(B) may be redundant and (A) is cleaner.

### 6. Record revision summary if the user fixed anything

If edits were applied, call `add_canon_fact(book_slug, chapter_num=<highest chapter number covered by this scan>, subject="manuscript-pass", fact="<summary>", domain="revision")` where `<summary>` lists: N book-rule violations fixed, N clichés replaced, N question-as-statement hits converted, N filter-word passes tightened, N repetitions pruned. `chapter_num` is the chapter's integer number (not its slug) — use the actual highest chapter number that has a draft, **not** `chapters_scanned` itself: `chapters_scanned` is a count (`len(drafts)`), and only equals the highest drafted chapter number when the drafted chapters happen to form a contiguous `1..N` block. A book drafted as chapters 01-05 and 12-40, for example, has `chapters_scanned=34` but a highest chapter number of 40 — `chapters_scanned` would silently anchor the fact to the wrong chapter there. When the drafted range isn't obviously contiguous, confirm the real highest number via `get_book_full(book_slug)`'s chapter list rather than assuming it from the count. Also don't narrow this to only the chapters the user happened to apply fixes to in this walkthrough — the note isn't tied to one specific chapter, so it anchors to the manuscript's scanned extent, not to the fix subset. The `canon_brief` projector reads from DB exclusively (Issue #297) — `plot/canon-log.md` is no longer read.

## Rules

- Always wait for user confirmation before applying fixes. The detector finds candidates; the human picks the keepers.
- **Book-rule violations are the user's own rules.** Treat them as authoritative. If the user's prose violates a rule they wrote, that's the most important fix — more important than any generic craft finding. If the user asks in the moment to downgrade, skip, or file it as a low-priority note, push back once first: remind them it's a rule *they* wrote for *this book*, so waiving it deserves at least one explicit confirmation rather than a same-breath override. The final call is still theirs — pushback opens a discussion, it never decides the outcome unilaterally (see the "verify user corrections" rule).
- A repeated phrase isn't always a bug. Some are deliberate motifs
  ("for a hundred and fifty years" might be a thematic refrain). When in
  doubt, ask.
- For high-severity repetition in categories `simile`, `character_tell`,
  and `blocking_tic`: default to "pick one to keep". For `structural` and
  `signature_phrase`: be more cautious — these may be intentional voice
  markers.
- **`character_tell` findings whose `phrase` ends in `(varied phrasing)`** are the
  paraphrased-tic detector, not the n-gram one — the phrase is a synthetic label
  ("shoulder (varied phrasing)"), not text that appears anywhere in the manuscript. "Pick
  one to keep" doesn't apply: there's no single literal phrase to keep or cut. Instead, walk
  the listed occurrences with the user and vary the physical signal across them — a
  different body part, a different kind of beat, or fewer repeats of the same character's
  tell. A book's `## Allowed Repetitions` in CLAUDE.md (matched on the body-part word) is the
  right escape hatch for a deliberate motif. E.g. for `"shoulder (varied phrasing)"` with
  occurrences "her shoulders came down" (ch 02), "her shoulders had dropped" (ch 08), "the
  tension left her shoulders" (ch 15): the recommendation should propose varying the physical
  signal itself for at least one occurrence (a different body part, or a beat that isn't a
  body-part release at all) — not "keep ch 08's phrasing, cut the other two."
- For `simile` findings specifically: apply the two-question test from
  `reference/craft/simile-discipline.md` to each occurrence. If a repeated
  simile also fails the discipline check (illogical, decorative, dead, or
  stacked), cut all instances — don't just keep the "best" one. If every
  instance does real work, the finding may be a deliberate motif worth
  keeping — ask the user. **Mixed outcome** (some occurrences pass the
  two-question test, some fail — e.g. one instance does real work, others
  are lazy reuse with no connection to their scene): the test is applied
  per occurrence, so the outcome is too — cut only the failing occurrences,
  keep the one(s) that pass. Don't extend the "cut all instances" exception
  to an occurrence that individually does real work, and don't fall back to
  the ordinary "pick one to keep" repetition default for the ones that fail
  the discipline check.
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

For `book_rule_violation` findings, the scanner extracts patterns from every
rule stored in the book's **book_rules database** — *not* from hand-editing
`CLAUDE.md` text. Rules get there via `append_book_rule(book_slug, text)` (used
by `/storyforge:register-callback` for a `Regel:`-prefixed message) or
`/storyforge:rules-audit`'s `update_book_rule`/promote-rule flows. CLAUDE.md's
own `## Rules` section is a **read-only rendered view** of that same DB (`##
Rules (from DB)`) — editing that section of the file directly does nothing;
the render is regenerated from the DB, not parsed back into it. Preview exactly
what the scanner will extract from the current rules via `list_book_rules(book_slug)`
before running a scan, if you want to sanity-check a rule without waiting for a
full manuscript scan.

The extraction logic itself, applied to each rule's stored text:

- **Backtick-wrapped regex** — if the content contains regex metacharacters
  (`|`, `(`, `)`, `[`, `]`, `\`, `^`, `$`, `?`, `+`, `*`, `{`, `}`), it's
  compiled as a case-insensitive regex. Example:
  `` `the (specific|particular) [a-z]+ (that|of)` ``
- **Backtick-wrapped literal** — otherwise treated as a literal case-insensitive
  substring. Example: `` ` thing ` ``
- **Double-quoted phrases** (≥6 chars) — extracted *only* when the rule text
  contains a ban cue (`banned`, `avoid`, `never`, `don't use`, ...).
  This prevents positive rewrite examples from being interpreted as bans.
- Italics (`*foo*`) are **ignored** — they're for narrative examples.
- Rules without any extractable pattern produce no findings. Rephrase the
  rule text with backticks or a ban-cue-qualified quoted phrase — via
  `/storyforge:rules-audit`'s `update_book_rule(book_slug, rule_match=...,
  new_text=...)`, not by editing CLAUDE.md directly — to make it
  machine-readable. `lint_book_rules(book_slug)` flags exactly which
  existing rules the scanner will silently ignore or misinterpret.

*(Live-verified 2026-07-25 against a real sandbox book: `append_book_rule`
inserted into the DB while the on-disk CLAUDE.md's `<!-- RULES:START/END -->`
markers stayed empty; `scan_manuscript` still correctly flagged the violation
from the DB-stored rule. Prior wording described the pre-Phase-4 CLAUDE.md-text
extraction model, which `append_book_rule`/the scanner no longer use.)*

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
