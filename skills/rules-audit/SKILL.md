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

If the user passed a book slug as argument, use it directly. Otherwise:

1. Check the active session via MCP `get_session()` — if there's a
   current book, propose it.
2. If no session book or user wants a different one, use AskUserQuestion
   with the output of `list_books()` (limit to active books).

Verify via `find_book(slug)` that the book exists. If not, exit with a
clear error.

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

Then briefly explain the warning codes that appear:

- **`italic_examples_with_ban_cue`** — Italic-wrapped examples (`*"foo"*`)
  combined with a ban cue. Scanner ignores italics, examples are silently
  invisible.
- **`mixed_positive_negative_quotes`** — Multiple `"..."` phrases with
  a ban cue. Scanner extracts every quoted phrase as a ban, so positive
  rewrite examples get flagged too.
- **`bracket_placeholder`** — Backtick body contains `[noun]`/`[verb]`
  style placeholders that read as character classes, not as `\w+`.
- **`scanner_extracts_nothing`** — Ban cue without backticks or quoted
  phrase. Scanner sees nothing; the rule does not enforce.

## Step 4: Triage Each Finding

Iterate over `issues` in order. For each finding present:

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
| `mixed_positive_negative_quotes` | Move positive examples to italic, keep banned phrases in backticks. Use `→` to mark the rewrite suggestion |
| `bracket_placeholder` | Ask whether the placeholder was meant as `\w+` (variable) or as a literal character class |
| `scanner_extracts_nothing` | Ask whether to add a backticked phrase, document an alternative, or both |

Then ask via AskUserQuestion:

> "How do you want to handle Rule {index}?"

Options (always provide all four):

- **Apply suggested rewrite** — show the proposed `new_text`, confirm,
  call `update_book_rule(book_slug, rule_match=title, new_text=...,
  validate=True)`.
- **Edit text manually** — let the user paste a custom replacement,
  then call `update_book_rule` with that text and re-display the
  resulting warnings.
- **Mark as narrative (drop quotes/italic)** — when the rule isn't
  meant to be a scanner pattern (e.g. "Jace must appear in every
  chapter from Ch 17 onward"). Strip the quote/italic noise so the
  scanner stops trying to match. Call `update_book_rule` with cleaned
  text.
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

## Step 5: Re-Lint

After all findings are processed, call `lint_book_rules(book_slug)`
again. Compare:

- Issues fixed
- Issues remaining (skipped or new warnings introduced by the fixes)

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
- **`rule_match` resolves by title first.** When you call
  `update_book_rule`, prefer `rule_match=title` (the bold-titled
  prefix). Fall back to `rule_index` only when there's no title or when
  multiple rules share a title (then `rule_match` raises and you have
  to disambiguate).
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
