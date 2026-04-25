---
name: manuscript-checker
description: |
  Scan a complete book manuscript for prose-quality issues that only surface
  when the whole thing is read in one pass: book-rule violations from the
  book's CLAUDE.md, cliché hits, dialogue punctuation anomalies (Q-word +
  period), POV filter-word overuse, per-chapter adverb density, and
  cross-chapter repetition (similes, character tells, blocking tics,
  structural patterns, signature phrases).
  Use when: (1) User says "manuscript check", "prose check", "repetition
  check", "Wiederholungen prüfen", "prose tics", "Buch prüfen",
  (2) Book status transitions from Drafting to Revision, (3) Full-manuscript
  revision pass, (4) User wants a craft-level health check before export.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> [--interactive]"
---

# Manuscript Checker

Full-manuscript prose-quality gate. Catches the class of issues that creep in
when chapters are written in isolation and only become visible when the book
is read end to end: repeated phrasing, worn-out clichés, POV filter words,
adverb pile-ups, dialogue punctuation drift, and — most importantly —
violations of rules the author wrote into the book's CLAUDE.md.

## When to run

- After **all** chapter drafts exist (or at least most of them).
- During the **revision phase**, before chapter-reviewer and voice-checker.
- Does not replace `chapter-reviewer` (single-chapter craft check) or
  `voice-checker` (AI-tell gate) or `continuity-checker` (timeline/location).
  This one catches a different problem: prose drift across chapters.

**Note on simile coverage.** The `simile` category in this checker is
*cross-chapter n-gram repetition* — the same simile phrase appearing in
multiple chapters. Per-simile *quality* (is this comparison illogical?
decorative?) is covered by `reference/craft/simile-discipline.md` and
enforced at write-time by `chapter-writer` (Step 6c) and at review-time by
`chapter-reviewer`. When walking the `simile` findings in interactive fix
mode (section 5), apply the two-question test from `simile-discipline.md`
to each hit before deciding whether to keep or rewrite — a repeated simile
that also fails the discipline check is a clear cut; a repeated simile that
does real work in each location may be an intentional motif.

## Detection categories

| Category | What it catches | Severity logic |
|---|---|---|
| `book_rule_violation` | Patterns extracted from `<book>/CLAUDE.md` rules | always high |
| `cliche` | Curated banlist of worn-out fiction phrasings | always high |
| `question_as_statement` | Dialogue starting with a Q-word but ending with `.` | high if ≥5 hits |
| `filter_word` | POV-distancing verbs per chapter (>3/1k words) | high if >6/1k |
| `adverb_density` | `-ly` adverbs per chapter (>8/1k words) | high if >14/1k |
| `simile` / `character_tell` / `blocking_tic` / `sensory` / `structural` / `signature_phrase` | Cross-chapter n-gram repetition | high if ≥4 hits |

The first two always sort to the top of the report — book rules because the
user explicitly wrote them, clichés because they're unambiguously stale.

## Workflow

### 1. Resolve target book

If the user provided a slug, use it. Otherwise call MCP `get_session()` and
use the active book. If still ambiguous, call `list_books()` and ask which
one.

### 2. Run the scan

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
    "simile": {"high": 6, "medium": 14}
  },
  "report_path": ".../research/manuscript-report.md",
  "findings": [ { phrase, category, severity, count, occurrences: [...] } ]
}
```

### 3. Read the generated report

Read `report_path` so you have the full Markdown context. The detector
groups findings by category, ranks them, and writes a recommendation per
finding.

### 4. Present a focused summary

**Chat summary target: max ~300 Wörter.** The full report is on disk — chat is the headline, not the whole story.

1. State chapters scanned + total findings + high-severity count by category.
2. Show the top 5 highest-severity findings across *all* categories (book rules first, then clichés, then the rest).
3. Tell the user the report path so they can open it.
4. Offer the next step (see section 5).

Example:

```
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

Process findings in **category priority order**:

1. `book_rule_violation` (user explicitly wants these fixed)
2. `cliche` (always worth fixing)
3. `question_as_statement` (distinct fix pattern — see below)
4. `filter_word`, `adverb_density` (per-chapter craft fixes)
5. Repetition categories (`simile`, `character_tell`, etc.)

For each high-severity finding:

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

### 6. Update the canon log if the user fixed anything

If edits were applied, append a brief note to `<book>/plot/canon-log.md`:

```markdown
## Revision: Manuscript pass — YYYY-MM-DD

- N book-rule violations fixed
- N clichés replaced
- N question-as-statement hits converted to "?"
- N filter-word passes tightened in chapters X, Y, Z
- N repetitions pruned (categories: ...)
```

Keeps the canon log honest about what was changed during revision.

## Rules

- Always wait for user confirmation before applying fixes. The detector finds candidates; the human picks the keepers.
- **Book-rule violations are the user's own rules.** Treat them as authoritative. If the user's prose violates a rule they wrote, that's the most important fix — more important than any generic craft finding.
- A repeated phrase isn't always a bug. Some are deliberate motifs
  ("for a hundred and fifty years" might be a thematic refrain). When in
  doubt, ask.
- For high-severity repetition in categories `simile`, `character_tell`,
  and `blocking_tic`: default to "pick one to keep". For `structural` and
  `signature_phrase`: be more cautious — these may be intentional voice
  markers.
- For `simile` findings specifically: apply the two-question test from
  `reference/craft/simile-discipline.md` to each occurrence. If a repeated
  simile also fails the discipline check (illogical, decorative, dead, or
  stacked), cut all instances — don't just keep the "best" one. If every
  instance does real work, the finding may be a deliberate motif worth
  keeping — ask the user.
- **Clichés are high severity even at a count of 1.** A cliché doesn't
  become less clichéd by being rare.
- **Filter words are not always bad.** Internal realisations, dream logic,
  and explicit meta-narration all legitimately use them. Only push back on
  density, not on isolated uses.
- **Adverbs are not always bad.** The signal is density, not individual
  words. Use the top-N display to find the tics, not a blanket banlist.
- The user explicitly wants to be challenged (see global CLAUDE.md). If you
  think the detector is wrong about a finding, push back.
- Honor the author profile. If a profile defines a signature phrase or
  stylistic choice (e.g. "flat declarative questions are part of the voice"),
  exclude it from rewrite recommendations.

## Book-rule pattern extraction

For `book_rule_violation` findings, the scanner extracts patterns from each
bullet under `## Rules` in the book's CLAUDE.md:

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
- Rules without any extractable pattern produce no findings. Rephrase with
  backticks or quotes to make them machine-readable.

## Error handling

- Book not found → tell the user the expected path and stop.
- Zero chapters with `draft.md` → tell the user the checker only runs on
  drafted chapters and stop.
- Zero findings → that's a great result. Tell the user the prose is clean.
