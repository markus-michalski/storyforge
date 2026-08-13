---
title: repetition-category-rules
book_categories: [fiction, memoir]
---

# Repetition Category Rules (manuscript-checker Interactive Fix Mode)

Loaded by both `manuscript-checker` and `manuscript-checker-memoir`'s
interactive fix mode (Step 5), only when the walkthrough actually reaches a
repetition category with special handling. This file covers only the
categories with a documented special case below — anything else in the
`simile` / `character_tell` / `blocking_tic` / `sensory` / `structural` /
`signature_phrase` set follows the "Default treatment" rule and needs no
further guidance. The underlying detector output is identical regardless of
`book_category`.

## Default treatment

For high-severity repetition in categories `simile`, `character_tell`,
`blocking_tic`, and `sensory`: default to "pick one to keep". For
`structural` and `signature_phrase`: be more cautious — these may be
intentional voice markers.

## `character_tell` — paraphrased-tic findings

**`character_tell` findings whose `phrase` ends in `(varied phrasing)`** are the
paraphrased-tic detector, not the n-gram one — the phrase is a synthetic label
("shoulder (varied phrasing)"), not text that appears anywhere in the manuscript. "Pick
one to keep" doesn't apply: there's no single literal phrase to keep or cut. Instead, walk
the listed occurrences with the user and vary the physical signal across them — a
different body part, a different kind of beat, or fewer repeats of the same character's
tell. A book's `## Allowed Repetitions` in CLAUDE.md (matched on the body-part word) is the
right escape hatch for a deliberate motif. E.g. for `"shoulder (varied phrasing)"` with
occurrences "her shoulders came down" (ch 02), "her shoulders had dropped" (ch 08), "his
shoulders squared" (ch 15), "her shoulders loosened" (ch 22), "his shoulders slumped"
(ch 29): the recommendation should propose varying the physical signal itself for at least
one occurrence (a different body part, or a beat that isn't a body-part release at all) —
not "keep ch 08's phrasing, cut the other four." (5 occurrences is medium severity — the
same treatment applies once it crosses into high at 10+.)

## `simile` — applying the two-question test's outcome

For `simile` findings specifically: apply the two-question test from
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
