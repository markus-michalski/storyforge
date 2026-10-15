---
name: chapter-voice-harvest
description: |
  Learn the author's voice from a chapter's review feedback: classify the logged comments, rework
  results and rejected proposals, then walk through recurring patterns and promote the confirmed
  ones into the author profile (style_principles, donts) with genre scope.
  Use when: (1) User says "voice harvest", "chapter voice harvest", "Stimme ernten",
  "Feedback in die Autorenstimme", (2) A chapter's review loop (reviewer, fixer, scene-rewriter) is
  done and the chapter is about to go to humanizer and proofreader, (3) User wants to see which
  voice patterns their corrections have accumulated so far.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug> [chapter-slug]"
---

# Chapter Voice Harvest

The author's corrections are the most direct evidence of their real voice, and they used to vanish
after each session. Every verified comment, rework and rejected proposal is logged to the
`review_feedback` table with MCP `log_review_feedback(book_slug, chapter_slug, source_skill,
decision, comment_text, dimension, direction, normalized_rule)`. This skill mines that log for recurring
patterns and, with the author's confirmation, writes them into the author profile so
`chapter-writer` and the reviewers pick them up from then on.

**Position in workflow:** `chapter-writer → chapter-reviewer → [chapter-fixer / chapter-scene-rewriter] →
chapter-voice-harvest → chapter-humanizer → chapter-proofreader`. The fixer and the scene rewriter are
optional; the trigger is the content of the log, not the path taken.

It is NOT `harvest-author-rules` (that one promotes registered book rules at book end) and NOT
`study-author` (that one analyses foreign texts).

## Prerequisites — MANDATORY LOADS

0. **Resolve book and chapter** — MCP `get_book_full(book_slug)`. On an `error` key stop and tell
   the user the book was not found. Take `author` (→ `author_slug`), `book_category` and `genres`
   from it. If no chapter slug was passed, take `last_chapter` from MCP `get_session()` **only when
   its `last_book` equals this book**; otherwise ask which chapter just finished its review loop.
1. **Vocabulary** — MCP `get_craft_reference("voice-dimensions")`: the closed set of dimensions and
   directions, the precedence rules and the classification procedure. Never use a dimension or
   direction that is not in it.
2. **Author profile** — MCP `get_author(author_slug)`, to compare candidates with the existing
   `writing_discoveries` (Step 5).

## Step 1 — Count what is there

Call MCP `list_pending_feedback(book_slug, chapter_slug)`. It returns the author's open entries
across all books, including those carried over from earlier chapters.

Work only on entries whose `book_category` equals this book's category. Entries of the other
category stay untouched: report them as "N entries belong to {other category} books and are
harvested from one of those" and never print their text.

- No entries left: say in one line "Nothing to harvest: no open review feedback for {author_slug}."
  and stop. Never start a walk on an empty log.
- Otherwise report: entries in total, entries of this chapter (same `book_slug` and `chapter_slug`),
  carried over, still unclassified.

Humanizer and proofreader decisions are logged after this skill has run; they stay open and are
picked up by the next chapter's harvest.

## Step 2 — Classify the open entries

Skip this step when every entry already has a `dimension` (always the case for memoir books, which
are classified at logging time).

For each unclassified entry apply the procedure from `voice-dimensions` — classify once:

1. Read the direction from the `before_text → after_text` change first, the comment second.
2. A rejected proposal points opposite to the proposal; classify what the author kept or asked for.
3. Pick the narrowest dimension; use the precedence table when two fit.
4. Write `normalized_rule` as one plain sentence.

Store it with MCP `set_feedback_classification(book_slug, feedback_id, dimension, direction,
normalized_rule)`. `{"updated": false}` means the id is unknown, closed or not the author's: skip
it and say so. An `error` explains what to fix (allowed values, rule length, a name); correct the
input and retry once, then leave the entry open and report it.

One comment, several wishes: log each additional wish with MCP `log_review_feedback(book_slug, chapter_slug,
source_skill, decision, comment_text, dimension, direction, normalized_rule)` (same chapter,
decision `reworked`, its own classification) and classify the original with the dominant
wish. Never fold two wishes into one rule.

**Stale classifications.** When `get_voice_candidates` later reports `skipped_unknown > 0`, list the
open entries whose `dimension` is set but no longer in the vocabulary and re-classify them with
`set_feedback_classification`. That is the one exception to "classify once".

Entries that are not voice evidence (typos, continuity fixes, fact corrections, book-specific
rules) are listed with one line each; ask (AskUserQuestion) "Close these N entries as not voice
evidence?" and only then call MCP `discard_feedback(book_slug, ids)`. Never invent feedback the log
does not contain.

## Step 3 — Get the candidates

MCP `get_voice_candidates(author_slug, book_slug)`. It returns `candidates`, `conflicts`,
`suppressed`, `unclassified` and `skipped_unknown`. Print one line per count that is above zero.
When `candidates` and `conflicts` are both empty, say "Not enough recurring evidence yet: {n}
classified entries so far" (add "{suppressed} discarded patterns are waiting for more evidence" when
`suppressed > 0`) and stop.

A candidate needs a weighted evidence sum of 3 from at least two chapters; its scope is the
intersection of the genres of its evidence (empty intersection = universal).

## Step 4 — Conflicts first

For each entry of `conflicts` show `sides[0]` and `sides[1]` (direction, weight, `chapter_count`,
rule, scope) and ask (AskUserQuestion):

- **Both are right in context** — keep watching; nothing changes.
- **Side 0 is my voice** — `discard_feedback(book_slug, conflicts[i].sides[1].evidence_ids)`.
- **Side 1 is my voice** — `discard_feedback(book_slug, conflicts[i].sides[0].evidence_ids)`.

After resolving any conflict call `get_voice_candidates` again before Step 5.

## Step 5 — Walk the candidates

One at a time, highest weight first:

```
Candidate {n}/{total} — {dimension} / {direction}   [{target_section}]

  Rule:      {normalized_rule}
  Evidence:  {evidence_count} entries in {chapter_count} chapters ({books})
  Scope:     {universal | genres}
  Rejected:  {rejected_share as %} of the weight were proposals you declined
  Opposed:   {opposed_by or "none"}
```

Fiction: add up to three examples by matching the candidate's `evidence_ids` against the entries
from Step 1 (re-list if needed) and showing their `before → after` pair or declined proposal.
Memoir: no examples at all — the table holds none.

Compare the rule with `get_author` `writing_discoveries`. If an existing discovery says the
opposite, quote both sides and let the user decide: replace, keep both as genre variants, or drop
the candidate. If the candidate has `harvested_weight > 0` or an existing discovery already says
the same, offer **Already in profile** instead of Promote: close the evidence with
`mark_feedback_harvested` without writing.

Ask (AskUserQuestion):

- **Promote** — write it as proposed
- **Edit and promote** — the user rewrites the rule text, then as above
- **Already in profile** — only when stated above; close without writing
- **Keep watching** — change nothing
- **Discard** — the pattern is not the author's voice; `discard_feedback(book_slug, evidence_ids)`

Never write or promote without an explicit answer for that candidate. Silence is not approval.
When `opposed_by` is not empty, offer to discard that weak opposing evidence together with a promotion.

## Step 6 — Promote

Compose the entry as `**{short title}** — {rule}` on one line, where the rule is the
`normalized_rule` or the user's edit. Write it with MCP `write_author_discovery(author_slug,
section=target_section, text=text, book_slug=book_slug, genres=..., universal=...)`:

- **Fiction:** `genres` is the comma-separated `scope.genres`, `universal` is `scope.universal`; pass
  one `before → after` pair as `example`.
- **Memoir:** `genres="memoir"`, `universal=False` and no `example`. The tag `memoir` keeps the
  rule out of the author's fiction books; the memoir skills treat it as a genre of every memoir book.

The tool refuses text with a person's name from a memoir book; rewrite the rule without names.

Show `warnings` and `extracted_patterns` from the response to the user. A `donts` entry for a style
direction ("fewer similes") has no concrete phrase and the scanner extracts nothing
(`scanner_extracts_nothing`); tell the author up front that such a Don't is guidance for
`chapter-writer` and the reviewers, not an enforced ban, and do not rewrite it for that reason.
Offer an edit for any other warning.

`written: true` and `already_present: true` both count as success. After either, call MCP
`mark_feedback_harvested(book_slug, evidence_ids)` and compare `changed` with the number of ids;
mention a difference. If the write returns an `error`, leave the entries open.

## Step 7 — Report

```
Voice harvest — {book_slug} / {chapter_slug}
Promoted:      {n}   ({target_section}: {rule} [{scope}])
Keep watching: {n}
Discarded:     {n}
Conflicts:     {n} resolved, {n} left open
Next: /storyforge:chapter-humanizer
```

## Memoir rules

- The log holds classifications only. Never print, quote or reconstruct comment text, before/after
  text or names of real people, and never ask the user to paste them back.
- `set_feedback_classification`, `log_review_feedback` and `write_author_discovery` reject rules and
  titles that contain the name of a person from the book. Rewrite without names or facts.
- Memoir entries arrive classified, so Step 2 normally does not apply.

## Rules

- **Nothing is written without confirmation** for that candidate.
- **Classify once.** Stored classifications are not re-derived, except for the stale ones named in
  Step 2.
- **The log is the source.** No feedback is invented, inferred from the draft or taken from memory
  of the conversation; if it is not in `list_pending_feedback`, it does not exist for this skill.
- **Counts decide, not wording.** Candidates come from `get_voice_candidates`; do not promote a
  pattern the engine did not return, however convincing a single comment felt.
- **Fiction and memoir stay separate.** Entries and candidates of the other category are never
  classified, discarded, shown or promoted here.
- **recurring_tics is not a target.** That section feeds the banlist; a quirk the author kept is a
  style principle.

## Error handling

- `get_book_full` error → book not found, stop.
- Book has no author → tell the user to set `author` in the book README; nothing can be attributed.
- Database or vocabulary error from a tool → show the message, stop, change nothing; re-running is safe.
- `write_author_discovery` error → keep the entries open and report which candidate failed.
