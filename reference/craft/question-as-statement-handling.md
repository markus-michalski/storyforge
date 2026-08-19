---
title: question-as-statement-handling
book_categories: [fiction, memoir]
---

# `question_as_statement` Handling (manuscript-checker Interactive Fix Mode)

Loaded by both `manuscript-checker` and `manuscript-checker-memoir`'s
interactive fix mode (Step 5), when the walkthrough reaches a
`question_as_statement` finding. The detector and the dialogue-punctuation
craft judgment are identical regardless of `book_category`.

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

## Variant: comma before the closing dialogue tag

A grammatically interrogative sentence sometimes closes with a comma instead
of `?` right before its tag — `"Who did this," he said.` instead of
`"Who did this?" he asked.` Unlike the period-ending case above, this rarely
carries the deliberate flat delivery a complete period-ending sentence can —
a comma grammatically subordinates the quote to the tag, which reads as
ordinary punctuation rather than a chosen flatness. Default to (A) here;
offer (B) only if the author says the flatness is intended.

Exceptions where the comma is correct as-is, not a bug — do not convert:

- **The quote continues after the tag:** `"Who did this," he said, "and
  why?"` The comma is doing normal split-dialogue work here.
- **The Q-word opens an exclamative or rhetorical, not a question:**
  `"What a mess," he said.` / `"How strange," she said.`

**This variant will not show up in a `question_as_statement` scan.** The
detector only matches dialogue ending in `.` — a trailing comma is discarded
before the check runs, so this case never produces a walkthrough finding.
Catch it on a manual read or during proofreading instead.
