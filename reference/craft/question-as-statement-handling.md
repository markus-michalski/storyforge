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
