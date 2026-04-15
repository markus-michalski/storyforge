---
name: repetition-checker
description: |
  Scan a complete book manuscript for repeated comparisons, similes, character
  tells, blocking tics, signature phrases, and structural patterns across all
  chapters. Produces a structured report with revision recommendations.
  Use when: (1) User says "repetition check", "Wiederholungen prüfen",
  "scan for repetition", "prose tics", (2) Book status transitions from
  Drafting to Revision, (3) The user is doing a full-manuscript revision pass.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<book-slug> [--interactive]"
---

# Repetition Checker

Cross-chapter prose-repetition gate. Catches the kind of repeated similes,
character tells, and signature phrases that creep in when chapters are written
in isolation and only become visible when the manuscript is read in one sitting.

## When to run

- After **all** chapter drafts exist (or at least most of them).
- During the **revision phase**, before chapter-reviewer and voice-checker.
- It does not replace `chapter-reviewer` (single-chapter craft check) or
  `voice-checker` (AI-tell gate). It catches a different problem: cross-chapter
  prose drift.

## Workflow

### 1. Resolve target book

If the user provided a slug, use it. Otherwise call MCP `get_session()` and use
the active book. If still ambiguous, call `list_books()` and ask which one.

### 2. Run the scan

Call MCP tool `scan_book_repetitions(book_slug)` with default thresholds.
Optional parameters:

- `min_occurrences` (default 2) — raise to 3 for very long books to focus
  on the worst offenders.
- `max_findings_per_category` (default 40) — cap to keep the report focused.
- `write_report` (default true) — also writes
  `<book>/research/repetition-report.md`.

The tool returns:

```json
{
  "book_slug": "...",
  "chapters_scanned": 34,
  "findings_count": 80,
  "summary": { "simile": {"high": 6, "medium": 14}, ... },
  "report_path": ".../research/repetition-report.md",
  "findings": [ { phrase, category, severity, count, occurrences: [...] } ]
}
```

### 3. Read the generated report

Read `report_path` so you have the full Markdown context. The detector ranks
phrases by severity (high = 4+ occurrences, medium = 2-3), groups them into
categories (similes, character tells, blocking tics, sensory, structural,
signature phrases), and writes a recommendation per finding.

### 4. Present a focused summary

Don't dump the whole report into chat. Instead:

1. State chapters scanned + total findings + high-severity count.
2. Show the top 5 highest-severity findings across categories with phrase,
   count, and category.
3. Tell the user the report path so they can open it.
4. Offer the next step (see section 5).

Example:

```
Repetition scan complete: 34 chapters, 80 findings (12 high-severity).

Top offenders:
1. "for the first time" — 18× (structural)
2. "kael looked at him" — 15× (signature phrase)
3. "the back of his" — 15× (character tell)
4. "the kind of person" — 11× (structural)
5. "stared at the ceiling" — 10× (signature phrase)

Full report: research/repetition-report.md

Want me to walk you through the high-severity findings interactively, or do
you want to revise on your own?
```

### 5. Optional: interactive fix mode

If the user says yes (or passes `--interactive`):

For each high-severity finding, in order:

1. Show the phrase, category, and ALL occurrences with chapter + line + snippet.
2. Recommend which one to keep (usually the first or the most narratively
   important — explain your reasoning).
3. Propose concrete rewrites for the others, anchored in each scene's senses /
   POV / mood. Do NOT generate generic alternatives — read the surrounding
   prose first if needed.
4. Ask the user: keep all / accept rewrites / skip / quit.
5. If the user accepts, apply the edits via the Edit tool to the affected
   chapter `draft.md` files.

Move on to medium-severity only if the user explicitly asks.

### 6. Update the canon log if the user fixed anything

If edits were applied, append a brief note to `<book>/plot/canon-log.md`:

```markdown
## Revision: Repetition pass — YYYY-MM-DD

- Removed N repeated phrases across M chapters
- Categories touched: similes, character tells, structural tics
```

This keeps the canon log honest about what was changed during revision.

## Rules

- Never auto-fix without user confirmation. The detector finds candidates;
  the human picks the keepers.
- A repeated phrase isn't always a bug. Some are deliberate motifs (e.g.
  "for a hundred and fifty years" might be a thematic refrain). When in
  doubt, ask the user before recommending removal.
- For high-severity items (4+ occurrences) in categories `simile`,
  `character_tell`, and `blocking_tic`: default to "this is too many, pick
  one to keep". For `structural` and `signature_phrase`: be more cautious —
  these may be intentional voice markers.
- The user explicitly wants to be challenged (see global CLAUDE.md). If you
  think the detector is wrong about a finding, push back.
- Honor the author profile. If a profile defines a signature phrase as
  intentional, exclude it from rewrite recommendations.
- **Honor the book's CLAUDE.md rules.** The scan automatically loads
  `<book>/CLAUDE.md`, extracts the `## Rules` section (static entries + the
  `<!-- RULES:START -->` block), and reports matches as `book_rule_violation`
  findings with severity `high` — independent of n-gram frequency. These
  always sort to the top of the report, and the offending rule text is shown
  verbatim so the user sees *why* something was flagged. Treat these as the
  most important findings: the user explicitly wrote the rule for this book.

## Algorithmic notes (for transparency)

The underlying detector lives at `tools/analysis/repetition_checker.py`.

- N-gram lengths: 4..7 tokens.
- Per-length thresholds: 4-grams need 5+ hits, 5-grams need 3+, 6/7-grams
  need 2+. Without this filter, common English fragments dominate the report.
- Stop-word-only n-grams are dropped.
- Longer accepted phrases suppress contained shorter phrases (within ±1
  occurrence count) to avoid duplicate near-identical findings.
- Categories are heuristic — based on body-part vocabulary, blocking-verb
  vocabulary, simile cues (`like`, `as if`, `as though`), structural cues
  (`the kind of`, `for X years`), and sensory tokens.
- Pure stdlib — no NLP dependencies — so the scan runs in seconds even on
  100k-word manuscripts.

### Book-rule pattern extraction

For `book_rule_violation` findings, the scanner extracts patterns from each
rule bullet using simple heuristics:

- **Backtick-wrapped regex** — if the content contains regex metacharacters
  (`|`, `(`, `)`, `[`, `]`, `\`, `^`, `$`, `?`, `+`, `*`, `{`, `}`), it's
  compiled as a case-insensitive regex. Example: `` `the (specific|particular) [a-z]+ (that|of)` ``
- **Backtick-wrapped literal** — otherwise treated as a literal case-insensitive
  substring. Example: `` ` thing ` ``
- **Double-quoted phrases** (≥3 chars) — treated as literal substring patterns.
  Example: `"opened his mouth. Closed it."`
- Italics (`*foo*`) are **ignored** — they're used for narrative examples, not
  scannable bans.
- Rules without any extractable pattern produce no findings, even if the rule
  text references a concept. Rephrase the rule with backticks or quotes to
  make it machine-readable.

## Error handling

- Book not found → tell the user the expected path and stop.
- Zero chapters with `draft.md` → tell the user the checker only runs on
  drafted chapters and stop.
- Zero findings → that's a great result. Tell the user the prose is clean.
