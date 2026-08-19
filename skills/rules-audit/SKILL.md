---
name: rules-audit
description: |
  Audit a book's CLAUDE.md rules: scan for scanner-blind shapes,
  triage findings one by one, apply fixes via update_book_rule.
  Use when: (1) User says "rules audit", "regeln prüfen", "rules check",
  "rules cleanup", "audit my rules", (2) User runs /storyforge:rules-audit,
  (3) After importing or migrating rules and you want to verify they
  enforce as intended, (4) When the manuscript-checker repeatedly misses
  things you thought were banned.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug]"
---

# Rules Audit

Walks every rule in a book's `CLAUDE.md` `## Rules` block through the
manuscript-checker pattern contract. For each finding the user decides
whether to fix, mark narrative, or skip — no blind rewrites.

Backed by three MCP tools (issue #145):

- `list_book_rules(book_slug)` — inventory
- `lint_book_rules(book_slug)` — bulk findings
- `update_book_rule(book_slug, rule_match, new_text, validate=True)` — write

## Step 1: Resolve the Book

Resolve `book_slug` first, from whichever of these applies:

1. If the user passed a book slug as argument, use it directly.
2. Otherwise, check the active session via MCP `get_session()` — if
   there's a current book, propose it.
3. If no session book, or the user wants a different one, use
   AskUserQuestion with the output of `list_books()` (limit to active
   books).

Regardless of which path resolved the slug (including path 1 — a
directly-supplied argument is not exempt), always verify the book
exists via `find_book(query=book_slug)` — the real tool's parameter is
named `query`, not `slug`. **`find_book` matches against both slug and
title, and does partial/substring matching, so it can return more than
one result** (e.g. querying `my-book` also matches `my-book-2`).
Resolve `book_slug` from the response as follows:

- **Exactly one match** — adopt that match's `slug` as `book_slug`,
  even if the user's input was a title (e.g. "Blood and Bone") rather
  than the slug itself. A single unambiguous match is a resolved
  match, not a mismatch.
- **Multiple matches, one with `slug` exactly equal to the input** —
  use that one; the exact-slug hit wins over the looser partial hits.
- **Multiple matches, none with an exact-slug hit** — disambiguate via
  AskUserQuestion, same as Step 1 paths 2/3.
- **Zero matches** — exit with a clear error before calling any Step 2
  tool.

## Step 2: Initial Scan

Call MCP tools in this order, parse JSON results:

```
list_book_rules(book_slug)   → inventory of all managed rules
lint_book_rules(book_slug)   → only the rules with warnings
```

If `rules_total == 0`:

> "No managed rules in this book yet. Use `/storyforge:report-issue`
> to add the first rule."

Exit.

If `len(issues) == 0`:

> "All N rules pass the manuscript-checker pattern contract. No audit
> work to do."

Exit cleanly.

## Step 3: Present the Findings

Show a compact table sorted by `rule_index`:

```
{N rules total} · {M with findings}

Idx  Title                                          Findings
---  ---------------------------------------------  -------------------------
0    {title 1}                                      {warning codes}
3    {title 2}                                      {warning codes}
...
```

Then briefly explain **only** the warning codes that actually appear in
this book's findings above — the four bullets below are a reference
glossary to pick from, not fixed boilerplate to print in full every
time. If only 1-2 codes occur, explain only those 1-2; do not paste the
other definitions just because they exist in this list.

- **`italic_examples_with_ban_cue`** — Italic-wrapped examples (`*"foo"*`)
  combined with a ban cue. Scanner ignores italics, examples are silently
  invisible.
- **`mixed_positive_negative_quotes`** — Multiple `"..."` phrases with
  a ban cue. Scanner extracts any quoted phrase that shares a sentence with
  the ban cue as a ban (Issue #612 — cue and quote must be in the same
  sentence, or the rule's bold title, to count), so a positive rewrite
  example in that same sentence gets flagged too. Put the cue and its
  banned phrase in the same sentence, or use backticks instead (always
  extracted regardless of sentence position).
- **`bracket_placeholder`** — Backtick body contains `[noun]`/`[verb]`
  style placeholders that read as character classes, not as `\w+`.
- **`scanner_extracts_nothing`** — Ban cue without backticks or quoted
  phrase. Scanner sees nothing; the rule does not enforce.

## Step 4: Triage Each Finding

Iterate over `issues` (from `lint_book_rules`) in order. Each `issues`
entry only carries `rule_index`, `title`, `warnings`, and
`extracted_patterns` — it does **not** carry the rule's raw text.
Source `{raw_text}` below by matching this `rule_index` against the
`index` field of the matching entry in Step 2's earlier
`list_book_rules` inventory (that tool's entries carry `index`, not
`rule_index` — different key, same underlying position, so `rule_index
== index` is the correct match) — never by looking for a `raw_text`
field on the `issues` entry itself, since it has none.

For each finding present:

```
Rule {index}: {title}
Current text:
  {raw_text}

Findings:
  - [{code}] {message}
    hint: {hint}

Scanner currently extracts: {extracted_patterns or "(nothing)"}
```

Then propose a **suggested rewrite** based on the warning code(s):

| Warning code | Suggested rewrite |
|---|---|
| `italic_examples_with_ban_cue` | Replace each `*"phrase"*` with `` `phrase` `` |
| `mixed_positive_negative_quotes` | Move positive examples out of double-quotes entirely (into italics, or drop them from the rule body) and keep only the banned phrase(s) in backticks — `_QUOTED_CONTENT_RE` re-triggers this same warning on `new_text` if 2+ double-quoted phrases remain, so the arrow notation below must not end up inside `new_text` itself. When presenting the change to the user, show it as `old phrasing → new phrasing` for readability — that `→` is for the on-screen diff only |
| `bracket_placeholder` | Ask whether the placeholder was meant as `\w+` (variable) or as a literal character class |
| `scanner_extracts_nothing` | Ask whether to add a backticked phrase, document an alternative, or both |

Then ask via AskUserQuestion:

> "How do you want to handle Rule {index}?"

**Before any of the three write-path options below calls
`update_book_rule`, resolve its target argument the same way every
time:** `rule_match` resolution is a case-insensitive **substring**
match against every rule's title, not an exact-title match — so it's
ambiguous not only on an exact duplicate title but whenever this
rule's title is a substring of (or identical to) any OTHER rule's
title (e.g. "No filter words" is a substring of "No filter words in
dialogue" — a very common shape for book rules). Check Step 2's
inventory: if no OTHER rule's title contains this rule's title
case-insensitively, call with `rule_match=title, new_text=...,
validate=True`. If at least one does, `rule_match` would raise
`AmbiguousMatchError` — call with `rule_index=<this rule's index>,
new_text=..., validate=True` instead (see "rule_match resolves by
title first" below — do not default to `rule_match=title` without this
check, for any of the three options below).

Options (always provide all four):

- **Apply suggested rewrite** — show the proposed `new_text`, confirm,
  then call `update_book_rule` with the resolved target argument.
- **Edit text manually** — let the user paste a custom replacement,
  then call `update_book_rule` with the resolved target argument and
  that text, and re-display the resulting warnings.
- **Mark as narrative (drop quotes/italic)** — when the rule isn't
  meant to be a scanner pattern (e.g. "Jace must appear in every
  chapter from Ch 17 onward"). Strip the quote/italic noise so the
  scanner stops trying to match. Call `update_book_rule` with the
  resolved target argument and the cleaned text.
- **Skip (false positive)** — leave the rule unchanged, record the
  decision for the report.

After every `update_book_rule` call, **show the returned warnings**.
If warnings remain on the new text, ask whether to iterate again or
accept and move on.

### Important: never blind-apply

This is Rule #14 territory. Always show the proposed `new_text` before
calling `update_book_rule`. The user must confirm. If your suggestion
misreads the rule's intent, the user pushes back and you revise — you
do not silently rewrite a working rule.

**This holds even if the user says "just apply them all, I trust you,
don't bother showing me each one."** A blanket delegation like that is
not the per-rule confirmation this rule requires — still show each
proposed `new_text` individually (even briefly) before each
`update_book_rule` call. Rule #14's confirmation requirement is a
structural safety gate, not a courtesy the user can waive with a
one-line aside.

## Step 5: Re-Lint

After all findings are processed, call `lint_book_rules(book_slug)`
again. Compare the new `issues` list against Step 2/3's original one,
by `rule_index`:

- Issues fixed — rule_index present originally, absent now.
- Issues remaining — rule_index present in both (skipped, or a fix
  that didn't fully clear its own warnings).
- **Newly appeared** — rule_index present now but absent originally,
  even on a rule that was never part of this run's findings at all
  (e.g. a coincidental side effect). Call this bucket out explicitly by
  name/index in the comparison — don't fold it silently into "issues
  remaining", which reads as "still the same known problem" and would
  hide that something new and unexpected just showed up.

## Step 6: Report

Print a concise summary:

```
Rules audit — {book_title}

Before:  {N} rules, {M_before} with findings
After:   {N} rules, {M_after} with findings

Fixed:    {count} ({list of rule indices/titles})
Cleaned:  {count} (marked as narrative)
Skipped:  {count} (kept as-is, false positive)
Still flagged: {count}

Next:
- Run /storyforge:manuscript-checker to see the impact across drafts
- {if any "still flagged"}: Use /storyforge:rules-audit again later
  if you change your mind on the skipped rules
```

## Important Behavior

- **Audit is read-then-write, not auto-fix.** Every change goes through
  user confirmation. Lint findings are advisory; the user owns the
  rule semantics.
- **`rule_match` resolves by title first, via case-insensitive
  substring match — not exact-title match.** When you call
  `update_book_rule`, prefer `rule_match=title` (the bold-titled
  prefix). Fall back to `rule_index` whenever there's no title, or
  whenever this rule's title is a substring of (or identical to) any
  OTHER rule's title case-insensitively — not just on an exact
  duplicate title. A title like "No filter words" being a substring of
  another rule's "No filter words in dialogue" is enough to make
  `rule_match` raise `AmbiguousMatchError`, so check the full inventory
  before assuming `rule_match=title` is safe.
- **Validate every write.** `update_book_rule(validate=True)` re-lints
  the new text. Show the warnings to the user — fixing a rule should
  not introduce new warnings, and if it does, the user gets to decide
  whether to iterate.
- **Idempotent re-runs.** Running rules-audit twice in a row with no
  intervening edits should produce the same findings. Use this to
  verify the fixes from the first run actually landed.
- **Don't touch static rules above the marker.** `list_book_rules`
  only surfaces rules inside `<!-- RULES:START -->` /
  `<!-- RULES:END -->`. Anything above is template boilerplate and
  the editor refuses to touch it. If the user wants to change those,
  they edit `CLAUDE.md` directly.
