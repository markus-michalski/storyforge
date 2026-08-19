---
title: book-rule-pattern-extraction
book_categories: [fiction, memoir]
---

# Book-Rule Pattern Extraction (manuscript-checker)

Loaded by both `manuscript-checker` and `manuscript-checker-memoir` — consult
when a `book_rule_violation` finding needs explaining, or when sanity-checking
a rule before it's scanned. Identical mechanism regardless of `book_category`.

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
- **Double-quoted phrases** (≥6 chars) — extracted *only* when a ban cue
  (`banned`, `avoid`, `never`, `don't use`, ...) appears in the *same
  sentence* as the quote — not merely anywhere in the rule text. A rule's
  bold title routinely uses a cue word rhetorically (e.g. "**Never** treat
  comedy as a timeout...") that has nothing to do with an unrelated quoted
  example in a *later* sentence of the same rule's explanatory prose —
  quoting a word there only illustrates a different concept, it isn't a
  literal ban (Issue #612). Put the cue and the quote in the same sentence
  (or write the phrase in backticks instead, which is always extracted
  regardless of sentence position) if a phrase isn't being picked up.
  This prevents positive rewrite examples, and unrelated quoted asides, from
  being interpreted as bans.
- Italics (`*foo*`) are **ignored** — they're for narrative examples.
- Rules without any extractable pattern produce no findings. Rephrase the
  rule text with backticks or a ban-cue-qualified quoted phrase in the same
  sentence — via `/storyforge:rules-audit`'s `update_book_rule(book_slug,
  rule_match=..., new_text=...)`, not by editing CLAUDE.md directly — to make
  it machine-readable. `lint_book_rules(book_slug)` flags exactly which
  existing rules the scanner will silently ignore or misinterpret.
- A rule whose prose documents its own quality exception (cues like "only
  when", "unless", "provided that" — e.g. "max 2-3 per chapter, and only
  when the comparison does real character work") still gets scanned and
  flagged as a `book_rule_violation`, but the gate treats it as WARN rather
  than a hard FAIL: a regex match can't evaluate whether a specific
  occurrence satisfies the documented exception, so it can never be more
  than an advisory signal (Issue #608).

*(Live-verified 2026-07-25: `append_book_rule` inserted into the DB while CLAUDE.md's
`RULES` markers stayed empty; `scan_manuscript` still flagged the violation from the
DB-stored rule — confirms the pre-Phase-4 CLAUDE.md-text extraction model described
here no longer applies.)*
