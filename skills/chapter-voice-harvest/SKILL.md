---
name: chapter-voice-harvest
description: |
  Learn the author's voice from a chapter's review feedback: classify the logged comments, rework
  results and rejected proposals, then walk through recurring patterns and promote the confirmed
  ones into the author profile (style_principles, donts, recurring_tics) with genre scope.
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
`review_feedback` table with MCP `log_review_feedback`. This skill mines that log for recurring patterns and, with the author's confirmation, writes them
into the author profile so `chapter-writer` and the reviewers pick them up from then on.

**Position in workflow:** `chapter-writer → chapter-reviewer → [chapter-fixer / chapter-scene-rewriter] →
chapter-voice-harvest → chapter-humanizer → chapter-proofreader`. The fixer and the scene rewriter are
optional; the trigger is the content of the log, not the path taken.

It is NOT `harvest-author-rules` (that one promotes registered book rules at book end) and NOT
`study-author` (that one analyses foreign texts).

## Prerequisites — MANDATORY LOADS

0. **Resolve book and chapter** — MCP `get_book_full(book_slug)`. On an `error` key stop and tell
   the user the book was not found. Take `author` (→ `author_slug`), `book_category`, `genres` and the
   chapter list from it. If no chapter slug was passed, take `last_chapter` from MCP `get_session()`;
   if that is empty too, ask which chapter just finished its review loop.
1. **Vocabulary** — MCP `get_craft_reference("voice-dimensions")`. It defines the closed set of
   dimensions and directions, the precedence rules and the classification procedure. Never use a
   dimension or direction that is not in it.
2. **Author profile** — MCP `get_author(author_slug)`, to compare candidates with the existing
   `writing_discoveries` (Step 5).

## Step 1 — Count what is there

Call MCP `list_pending_feedback(book_slug, chapter_slug)`. It returns the author's open entries,
including those carried over from earlier chapters and books.

- `count == 0`: say in one line "Nothing to harvest: no open review feedback for {author_slug}."
  and stop. Never start a walk on an empty log.
- Otherwise report: total entries, entries of this chapter, carried over, still unclassified.

Humanizer and proofreader decisions are logged after this skill has run; they stay open and are
picked up by the next chapter's harvest. Say so if the user asks why they are missing.

## Step 2 — Classify the open entries

Skip this step when every entry already has a `dimension` (always the case for memoir books, which
are classified at logging time).

For each unclassified entry apply the procedure from `voice-dimensions` — classify once, never
re-derive a stored classification:

1. Read the direction from the `before_text → after_text` change first, the comment second.
2. A rejected proposal points opposite to the proposal; classify what the author kept or asked for.
3. Pick the narrowest dimension; use the precedence table when two fit.
4. Write `normalized_rule` as one plain sentence.

Store it with MCP `set_feedback_classification(book_slug, feedback_id, dimension, direction,
normalized_rule)`. An `error` response lists the allowed values; fix the pair and retry.

Entries that are not voice evidence (typos, continuity fixes, fact corrections, book-specific
rules) are listed to the user with one line each, then closed with MCP
`discard_feedback(book_slug, ids)` after the user agrees. Never invent feedback the log does not
contain.

## Step 3 — Get the candidates

MCP `get_voice_candidates(author_slug, book_slug)`. It returns `candidates`, `conflicts`,
`suppressed`, `unclassified` and `skipped_unknown`. Print a three-line summary. If both lists are
empty say "Not enough recurring evidence yet" with the number of classified entries, and stop.

A candidate needs a weighted evidence sum of 3 from at least two chapters; its scope is the
intersection of the genres of its evidence (empty intersection = universal).

## Step 4 — Conflicts first

For each entry of `conflicts` show both sides (direction, weight, chapters, rule, scope) and ask
(AskUserQuestion):

- **Both are right in context** — keep watching; nothing changes.
- **Side A is my voice** — discard the evidence of side B with `discard_feedback`.
- **Side B is my voice** — discard the evidence of side A.

Resolved conflicts re-enter the candidate list through a new `get_voice_candidates` call.

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

Fiction: add up to three examples, each a `before → after` pair or the declined proposal, taken from
the entries' `before_text`/`after_text`/`proposal_text`. Memoir: no examples at all — the table
holds none.

Check the rule against `get_author` `writing_discoveries`. If an existing discovery says the
opposite, quote both sides and let the user decide: replace, keep both as genre variants, or drop
the candidate.

Ask (AskUserQuestion):

- **Promote** — write it as proposed
- **Edit and promote** — the user rewrites the rule text, then as above
- **Keep watching** — change nothing
- **Discard** — the pattern is not the author's voice; `discard_feedback(book_slug, evidence_ids)`

Never write or promote without an explicit answer for that candidate. Silence is not approval.

## Step 6 — Promote

Compose the entry as `**{short title}** — {normalized_rule}` (one line) and write it with
MCP `write_author_discovery(author_slug, section=target_section, text=text, book_slug=book_slug,
genres="{comma-separated scope.genres}", universal={scope.universal})`. For fiction pass one
`before → after` pair as `example`; for memoir never pass an example.

Show `warnings` from the response. Style rules ("fewer similes") are guidance for `chapter-writer`
and carry no scannable phrase; a `scanner_extracts_nothing` warning is expected for them and is not
a reason to rewrite. Offer an edit only for other warnings.

After a successful write call MCP `mark_feedback_harvested(book_slug, evidence_ids)` so the entries
are not counted again. If the write fails, leave the entries open.

## Step 7 — Report

```
Voice harvest — {book_slug} / {chapter_slug}
Promoted:      {n}   ({section}: {rule} [{scope}])
Keep watching: {n}
Discarded:     {n}
Conflicts:     {n} resolved, {n} left open
Next: /storyforge:chapter-humanizer
```

## Memoir rules

- The log holds classifications only. Never print, quote or reconstruct comment text, before/after
  text or names of real people, and never ask the user to paste them back.
- A rule that names a person is rejected by the tool. Rewrite it without names or facts.
- `set_feedback_classification` is only for entries that are still open; memoir entries arrive
  classified, so this step normally only reviews candidates.

## Rules

- **Nothing is written without confirmation** for that candidate.
- **Classify once.** Stored classifications are not re-derived; a wrong one is corrected through
  `set_feedback_classification` while the entry is open.
- **The log is the source.** No feedback is invented, inferred from the draft or taken from memory
  of the conversation; if it is not in `list_pending_feedback`, it does not exist for this skill.
- **Counts decide, not wording.** Candidates come from `get_voice_candidates`; do not promote a
  pattern the engine did not return, however convincing a single comment felt.
- **Fiction and memoir stay separate.** Candidates of the other category are never shown.

## Error handling

- `get_book_full` error → book not found, stop.
- Book has no author → tell the user to set `author` in the book README; nothing can be attributed.
- Database or vocabulary error from a tool → show the message, stop, change nothing; re-running is safe.
- `write_author_discovery` error → keep the entries open and report which candidate failed.
