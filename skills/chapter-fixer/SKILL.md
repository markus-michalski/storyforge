---
name: chapter-fixer
description: |
  Apply targeted, line-level fixes to an already-drafted chapter from chapter-reviewer or
  manuscript-checker findings (chapter+line+snippet anchored), or from the author's own
  ad-hoc read — no formal checker run required. Surgical Edit-tool patches only — never
  appends, never rewrites a scene wholesale, never re-runs chapter-writer's Scene Plan flow.
  Use when: (1) User says "chapter fixer", "Findings fixen", "Review-Findings umsetzen",
  "fix reviewer findings", (2) chapter-reviewer / chapter-reviewer-memoir returned FAIL or WARN
  with findings that need correction without a rewrite, (3) manuscript-checker flagged a
  `book_rule_violation` or other chapter-anchored issue for one chapter outside its
  full-manuscript loop, (4) the user points at a passage that violates a rule surfaced via
  rules-audit, (5) the user just noticed a sentence or two that reads oddly while re-reading a
  chapter and wants it fixed, with no reviewer run involved. For reconstructing a whole scene
  instead of a sentence or two, use `/storyforge:chapter-scene-rewriter`.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Chapter Fixer

Chapter-fixer closes the gap between "a checker found problems" and "the problems are fixed"
without going through `chapter-writer` — which is append-only (Step A2 never edits existing
prose) and corrupts an already-drafted `draft.md` if invoked on a chapter that already has
content. This skill reads the flagged text, patches exactly that span via the `Edit` tool, and
leaves everything else untouched.

**Position in workflow:** runs ad hoc, whenever `chapter-reviewer` / `chapter-reviewer-memoir` /
`manuscript-checker` produced chapter-anchored findings against one chapter's `draft.md` (or the
user manually identifies a passage that violates a rule surfaced via `rules-audit`). Not part of
the fixed pipeline order — it's invoked after any of those return FAIL/WARN, then the triggering
checker is normally re-run to confirm the fix landed.

## Prerequisites — MANDATORY LOADS

0. **Resolve book context** — Call MCP `get_book_full(book_slug)`. If it returns an `error` key,
   stop and tell the user the book wasn't found at the expected path. Otherwise extract `author`
   (→ `author_slug`), `book_category`, and this chapter's integer `number` from
   `chapters_data[chapter_slug].number` (needed for Step 5.5) — `get_book_full`'s raw book
   dict keys the chapter map as `chapters_data`, not `chapters`.
1. **Draft** — Call `resolve_path(book_slug, "chapters", "{chapter_slug}/draft.md")` (MCP), then
   read the returned `path`. If missing (`exists: false`), stop and tell the user: "Kein draft.md
   für dieses Kapitel gefunden — chapter-writer muss zuerst laufen."
2. **Author profile** — MCP `get_author(author_slug)`. **Why:** any rewritten span must match the
   author's documented voice — a syntactically-correct fix that reads like a different author is
   a regression, not a fix (same standard chapter-humanizer and manuscript-checker apply). If
   `author_slug` is empty or this call returns an `error` key, skip profile context and proceed —
   don't block the fix pass on it (same tolerance manuscript-checker Step 1b applies).
3. **Book CLAUDE.md** — MCP `get_book_claudemd(book_slug)`. **Why:** CLAUDE.md Rule 17 requires
   this before writing or reviewing a chapter — a `book_rule_violation` finding can't be verified
   against the actual rule text without it, and a proposed replacement could unknowingly break a
   *different* book rule. A book with no CLAUDE.md file yet returns whatever DB-rendered
   Rules/Callbacks/Workflows exist, or empty content, instead of an error (storyforge#573) —
   treat genuinely empty content (`content` is `""`, or has no Rules/Callbacks/Workflows entries)
   as "no additional rules" and continue. An `error` key still happens for two distinct causes,
   and neither means "no rules": the book project itself doesn't exist (already handled by
   Prerequisite 0, so this branch should not occur here in practice), or the book's `series:`
   frontmatter names a series it isn't registered in (`BookNotLinkedToSeriesError` — a real,
   reachable state for a book that DOES exist; see the `book_rules_unreadable` report category,
   storyforge#579/#584). On an `error` key here: stop and surface it to the user verbatim — "book
   rules could not be read, cannot verify this finding against the actual rule text" — rather than
   silently treating the check as passed. The user decides whether to fix the series link first or
   proceed anyway.
4. **Anti-AI patterns** — MCP `get_craft_reference("anti-ai-patterns")`. **Why:** every proposed
   replacement is new prose — it must be verified free of Section 11 elegant-abstraction shapes
   and flagged vocabulary before being presented, same requirement chapter-humanizer applies to
   its own alternatives (see Surgical Mode rule 3 below).
5. **Shared feedback-verification procedure** — MCP `get_craft_reference("chapter-writing-shared")`,
   specifically `§ User Feedback Handling`. **Why:** a finding can itself be wrong — a reviewer
   miscounts a punctuation hit, a manuscript-checker repetition is actually a deliberate motif.
   Every finding gets verified against this five-step procedure before a patch is proposed, not
   just user-authored corrections.
6. **Regression baseline** — Call MCP `validate_chapter(book_slug, chapter_slug)` and
   `count_words(book_slug, chapter_slug)` *before* any edit, and keep both results. Step 5 diffs
   against this baseline — `validate_chapter` returns every finding in the file, not just new
   ones, so without a pre-edit snapshot there is no way to tell a pre-existing hit from a
   regression this batch introduced.

## Step 1 — Gather Findings

Findings come from one of two sources — never invented by this skill itself:

- **(A) Already surfaced this session.** If `chapter-reviewer` / `chapter-reviewer-memoir` /
  `manuscript-checker` already ran against this chapter earlier in the conversation, reuse that
  output directly — do not re-derive it.
- **(B) Not yet available.** Ask the user to paste the findings (the Critical/Recommended/Minor
  list, or the specific manuscript-checker entries for this chapter), or offer to run
  `/storyforge:chapter-reviewer` (fiction) / `/storyforge:chapter-reviewer-memoir` (memoir) now
  and use its Critical findings as the mandatory fix list, asking the user whether to also include
  Recommended and/or Minor.
- **(C) User-identified rule violation.** If the user points at a specific passage they believe
  violates a rule from `rules-audit`/`list_book_rules`, treat their pointer + the rule text as one
  manual finding — `rules-audit` itself never produces the chapter+line anchor.
- **(D) Ad-hoc author observation.** The user doesn't need a formal checker run to flag something —
  "these two sentences read weird" while re-reading a chapter is a valid finding on its own. Treat
  the user's own pointer + description as one manual finding, same shape as (C): category is
  whatever they describe (or `prose_quality` if unstated), severity defaults to Recommended unless
  they say otherwise. Still goes through Step 3 verification like every other finding — an author's
  gut read is a candidate, not an automatic pass.

Normalize each finding to: **category** (e.g. `9b dialog punctuation`, `simile`, `book_rule_violation`),
**severity**, **location** (scene/chapter hint or quoted text), **issue**, **suggested fix** (if the
source provided one — chapter-reviewer usually does, manuscript-checker's structured findings
include `phrase` + `occurrences[].snippet`).

**Memoir-specific findings** (`anonymization_leak`, `tidy_lesson_ending`, `reflective_platitude`,
`timeline_ambiguity`, `real_people_consistency`) get the same category-specific treatment
`manuscript-checker` Step 1b/5 already defines — `anonymization_leak` is a pre-publication
blocker and goes first, un-skippable without an explicit override from the user.

## Step 2 — Locate Each Finding in the Draft

Read `draft.md` once for the whole batch (already loaded in Prerequisites, but re-read if this
step runs more than a few tool calls after that load — GH#27 applies to any stale in-memory copy).
For each finding:

1. Search for the finding's quoted text or described construction.
2. **Unambiguous single match** — record enough surrounding context to build a unique `old_string`
   for the `Edit` tool (the exact sentence/clause, not just the flagged word).
3. **No match** (the quote is paraphrased, the passage was already changed, or it's from a
   different chapter) — do not guess. Mark the finding **unresolved** and tell the user which one
   and why.
4. **Multiple matches** (e.g. a repeated phrase across scenes) — list every location and ask which
   occurrence(s) the finding targets, unless the finding's own category already implies "all of
   them" (e.g. `sentence_repetition`, cross-chapter n-gram categories where manuscript-checker's
   `occurrences` array already enumerates each one with its own location).

## Step 3 — Verify, Then Propose

For each located finding, run it through `§ User Feedback Handling` (chapter-writing-shared.md)
before drafting a fix: re-read the passage, check whether an earlier chapter or established voice
justifies the current text, assess whether "fixing" it would break continuity or a deliberate
motif. If the finding looks wrong, say so and propose leaving the text as-is instead of patching
it blind.

**Batch size cap — hard limit, check before writing the list, not after:** the 20-hit cap applies
to the total count of numbered hits this batch would produce, **including unresolved ones** — not
just verified survivors. Before truncating, sort `anonymization_leak` and `book_rule_violation`
hits to the top (see the precedence order in the carve-out below) so truncation can never push a
blocker into a later batch. If the sorted list has more than 20 numbered hits, present only the
first 20 and say explicitly how many remain for a follow-up batch (e.g. "Showing 20 of 23. 3 more
after this batch is resolved."). Never present more than 20 numbered hits in one message.

Present the surviving findings as a numbered list, same shape as chapter-humanizer's Scan Report:

```
## Fixer Batch — {book-slug} / {chapter-slug}

[1] **{category}** — Sc N, ~line M
> *"{quoted current text}"*
Proposed fix: *"{proposed replacement}"*

[2] **{category}** — Sc N, ~line M
> *"{quoted current text}"*
Proposed fix: *"{proposed replacement}"*
(unresolved) [3] **{category}** — not found in draft.md — flagged text may already be fixed or
from a different chapter. Provide the exact current wording, or skip.

Instructions: reply with hit numbers to apply as-is, numbers for a different alternative
(e.g. "3: shorter"), and numbers to skip. Example: "apply 1, 2 / rework 3: one sentence / skip 4"
```

> **--- APPROVAL GATE ---**
> Stop here. Do NOT call Step 4 or touch `draft.md` this turn.
> Unlocks only on an explicit apply/skip decision on THIS batch. A rework (`N: [instruction]`)
> does NOT unlock it — only its confirmed replacement does. The carve-out below still applies.
> Silence or generic enthusiasm is not approval — no "keep moving instead of asking"
> instruction overrides this gate.
> **--- END GATE ---**

### User Response Formats

- `apply all` — apply every proposed fix as-is, **except** `anonymization_leak` /
  `book_rule_violation` hits — see the carve-out below.
- `apply N, M, ...` — apply specific hit numbers as-is.
- `skip N, M, ...` — leave those unchanged.
- `N: [instruction]` — rework hit N with the given instruction before applying; present the
  reworked text for confirmation before it joins the write batch.
- Mixed responses are fine (`apply 1, 4 / skip 2 / 3: shorter`) — resolve any pending reworks
  first, THEN apply the full approved batch together (see Step 4).

**Carve-out — `anonymization_leak` and `book_rule_violation` are excluded from `apply all` / bulk
`apply N, M, ...`.** Both require their own individual apply/skip response, even inside a
batch that also has a plain bulk approval — same standard manuscript-checker applies to
`anonymization_leak`, extended here to `book_rule_violation` since Rules (below) treats it as the
highest-priority finding in any batch. **Numbered-list precedence when both appear in the same
batch:** `anonymization_leak` (a consent/legal pre-publication blocker) goes first, then
`book_rule_violation` (an author style rule) second, then everything else — a consent blocker
always outranks a style rule. If a user's `apply all` (or a bulk `apply N, M, ...` that
happens to include one of these hit numbers) is the ONLY response covering one of these findings,
that finding is NOT resolved yet — explicitly ask for its own apply/skip decision before touching
it, do not fold it into the bulk batch silently. If the user says `skip` on an `anonymization_leak`,
push back once — quote the person's `consent_status`/anonymization decision and ask for explicit
confirmation that leaving the real name in is intentional.

## Step 4 — Apply (Single Write Pass)

**Entry check.** Confirm the current message replies to the batch Step 3 just presented (GATE
above). Doubt which batch a stray "apply all" targets → ask, don't guess.

1. Read the full `draft.md` again immediately before writing (GH#27) — the copy from
   Prerequisites/Step 2 may be stale.
2. Apply every approved fix via the `Edit` tool, one finding at a time, in this single pass —
   don't split it across turns or ask for re-approval mid-batch. **Before each individual `Edit`
   call**, confirm its `old_string` still matches the file as it stands right now — an earlier
   edit in this same batch may have rewritten text that a later finding's `old_string` overlaps or
   depends on (e.g. two findings three words apart in the same sentence). If it no longer matches:
   re-locate that finding's span in the current text (same as Step 2) before issuing the edit, do
   not force a stale match.
3. If an `Edit` call still fails (span genuinely gone, or now ambiguous), stop applying further
   edits in the batch, keep whatever already landed, and report exactly which findings were
   applied vs. which one failed and why — never silently drop or retry-guess a failed edit.
4. **Hook interaction.** Every `Edit` triggers this repo's PostToolUse chapter-validator hook,
   which re-scans the *entire* file and can return a block report even for issues outside this
   batch. If a block report names the span an edit in *this* batch just wrote, treat it as a
   same-batch regression — fix or revert that specific edit before continuing to the next finding.
   If it names a different, pre-existing span that isn't one of this batch's findings, Surgical
   Mode rule 2 ("never invent a finding") still applies — do not fix it inline; note it in the
   report below as an existing issue outside this batch's scope, for a future chapter-fixer round.
5. Report every applied fix as an explicit `old → new` pair (not just a summary count) — this is
   the only revert record; no separate backup is written. To revert one later, issue a fresh
   `Edit` with the pair swapped. These pairs are the first line of the Closing Report Template
   below; fill in the rest of the template as Step 5 completes.

### Closing Report Template

Every fixer batch ends with this report — the individual Step 4/5/6 items below say *what* feeds
each line, this template is the single place that says *where* it goes. Emit all lines that apply
(omit a line only if its step says it's optional and wasn't triggered):

```
Applied N fixes. Skipped M. Unresolved: K.
{old → new} — one pair per applied fix (Step 4 item 5)
validate_chapter: {diff result, even if empty} (Step 5 item 1)
Word count: {baseline} → {new} ({delta}, reconciled) (Step 5 item 2)
Spot-check [{n}] {category} — {test}: {PASS/FAIL} — one line per finding in a category
  `validate_chapter` doesn't cover (Step 5 item 3)
Re-run recommended: {yes, with trigger / no} (Step 5 item 4, only when triggered)
Fixer round N/3 complete. (Step 6)
```

(Adjust N/M/K if Step 4 item 3's partial-failure path was hit — report what actually landed, not
what was planned.)

## Step 5 — Re-Validate

1. Call MCP `validate_chapter(book_slug, chapter_slug)` again and diff its findings **explicitly,
   one by one, against the Prerequisites 6 baseline list** (not a mental impression of it) — this
   covers banlist, author vocabulary, POV-knowledge boundary, time-anchor phrases, meta-narrative
   leakage, AI-tells, sentence-variance, book rule violations, and global shape violations (the
   full set `chapter_validator.py` emits). **Only a finding absent from the baseline counts as a
   regression** — a finding already present pre-edit is a pre-existing issue outside this batch's
   scope (see Step 4 item 4), not something this pass broke. **State the diff result on the
   `validate_chapter:` line of the Closing Report Template above, even when it's empty** — e.g.
   "validate_chapter: 1 pre-existing WARN (unchanged from baseline), 0 new findings" — never
   silently fold a post-edit finding into the success summary without first naming whether it was
   in the baseline. Any genuinely new hit: surface it immediately and offer to revert that specific
   edit (using the `old → new` pair recorded in Step 4) or refix it.
2. Call MCP `count_words(book_slug, chapter_slug)` and compare its total against the Prerequisites
   6 baseline. The delta should roughly match the net length change of Step 4's applied
   replacements — a much larger unexplained drop signals a lost passage (e.g. an `old_string` that
   swallowed more surrounding text than intended), not a clean patch. Investigate before reporting
   success if the delta doesn't reconcile. If investigation confirms real content is missing (not
   just an expected trim), treat it exactly like item 1's regression path: surface it immediately
   and offer to revert the specific edit (using its `old → new` pair) or refix it — do not report
   the batch as a clean success with an unexplained word-count gap still open.
3. For finding categories `validate_chapter` doesn't cover (dialogue punctuation, simile,
   continuity, plot logic, phrase echo, structure, cross-chapter repetition — `book_rule_violation`
   and `global_shape_violation` ARE covered by item 1 above, no separate spot-check needed for
   those) — spot-check each *fixed* passage against the same rule the source checker used for that
   category (e.g. re-apply the 9b question-mark scan, or the two-question simile test from
   `simile-discipline.md`) to confirm the specific finding is actually resolved, not just reworded.
   **Emit one `Spot-check` line per such finding on the Closing Report Template above** (e.g.
   "Spot-check [3] simile — two-question test: PASS") — this is mandatory chat output, not an
   internal check whose result stays unstated.
4. **Recommend re-running the original checker** (`chapter-reviewer` / `chapter-reviewer-memoir` /
   `manuscript-checker`) for a full confirmation, instead of trusting the spot-check alone, whenever
   **this fixer round's cumulative total** — summed across every batch applied so far in the
   current gather→apply→validate cycle (Step 6), not just this batch — exceeds 10 fixes OR touches
   more than 2 distinct finding categories. Concrete triggers, not a vague "if it feels large"
   judgment call. Track the running per-round fix count and category set alongside the round
   counter from Step 6. State this recommendation on the `Re-run recommended:` line of the Closing
   Report Template when triggered; below both thresholds, omit the line (it's optional).

## Step 5.5 — Record Revision Summary

If Step 4 applied at least one fix, call `add_canon_fact(book_slug, chapter_num=<this chapter's
number, from Prerequisites 0>, subject="chapter-fixer-pass", fact="<N fixes applied: category
breakdown>", domain="revision")` — same pattern manuscript-checker §6 uses. This is the only
persistent record of what changed once the session ends; skip this call entirely if zero fixes
were applied.

## Step 6 — Offer to Loop

After reporting results: *"Nochmal `/storyforge:chapter-reviewer` laufen lassen, um FAIL→PASS/WARN
zu bestätigen?"* If the user agrees and the checker still returns findings, chapter-fixer can
process that new list in another round. Track **fixer rounds** in this session (a round = one
gather→apply→validate cycle, regardless of how many ≤20-hit batches it took) — **state the current
round number on the `Fixer round N/3 complete.` line of the Closing Report Template** (see Step 4)
so the count stays visible and auditable across a long session instead of being tracked silently.
**Hard cap: 3 rounds
per session** — one higher than chapter-humanizer's 2-pass cap, since a fixer round can span
findings from multiple independent checkers (reviewer + manuscript-checker) rather than a single
self-contained scan type. If a 4th round is requested, decline and redirect: *"Drei Fixer-Runden sind das
Limit für diese Session. Für weitere Änderungen: neue Session starten oder manuell anpassen —
oder, falls die Findings so dicht sind, dass Einzel-Fixes nicht mehr greifen, eine
Szenen-Überarbeitung erwägen"* — via `chapter-scene-rewriter` for fiction, or manually for
memoir (no in-place scene rewriter exists for memoir yet, see Surgical Mode rule 6).

## Surgical Mode — Core Constraints

1. **Touch only the flagged span.** The replacement covers the finding and nothing else —
   surrounding prose, structure, and content stay exactly as the source checker left them.
2. **Never invent a finding.** Every patch traces back to an item from Step 1 — no opportunistic
   cleanup of unflagged text, even if it looks wrong while reading past it (see Step 4 item 4 for
   the hook-noise case this most often comes up in).
3. **Verify the replacement is clean.** Confirm every proposed fix is free of Section 11
   elegant-abstraction shapes and flagged vocabulary (Prerequisites 4) before presenting it — a
   fix that trades one AI-tell for another isn't a fix.
4. **Author voice is mandatory.** Every replacement matches the author's documented tone, rhythm,
   and vocabulary. A grammatically-fixed line that sounds like a different author is a regression.
5. **Read the full file before writing.** GH#27 — see Step 4, item 1.
6. **No wholesale rewrites.** If findings are so dense or overlapping that individual patches
   would require reconstructing a scene, stop and ask. **Fiction** (`book_category` from
   Prerequisites 0): *"Szene [N] hat [X] überlappende Findings — eine gezielte Überarbeitung
   der ganzen Szene über chapter-scene-rewriter wäre effizienter als Einzelfixes. Soll ich das
   stattdessen vorschlagen?"* **Memoir:** *"Szene [N] hat [X] überlappende Findings — für
   Memoir gibt es noch keinen sicheren Ganze-Szene-Rewriter (chapter-writer-memoir ist
   append-only und würde den Draft beschädigen). Vorschlag: die Findings in kleineren
   Fixer-Runden abarbeiten, oder die Szene manuell direkt in draft.md überarbeiten."* Wait for
   explicit confirmation before proceeding either way. `chapter-writer` /
   `chapter-writer-memoir` are never the right destination for this — both are append-only and
   would corrupt the existing draft rather than replace one scene in it.

## Error Handling

- No `draft.md` for this chapter → stop, tell the user `chapter-writer` must run first.
- No findings available and the user declines running a checker → stop, ask for at least the
  Critical findings text.
- A finding's flagged text cannot be located → mark unresolved (Step 2), never guess-edit.
- Zero findings survive verification (Step 3) → report that explicitly: *"Alle vorgelegten
  Findings haben die Verifikation nicht bestanden oder sind bereits behoben — keine Änderungen
  vorgenommen."*

## Rules

- **Edit-only, never append.** This skill never calls `chapter-writer`'s Scene Plan / Step A2
  flow. If the fix requires new prose beyond a sentence-level rewrite, that's out of scope — say
  so and point at `chapter-writer` or `chapter-humanizer` instead.
- **Never blind-apply — hard block, not a default.** Every fix needs an explicit apply/skip
  decision before it's written; batch approval via the mini-DSL counts. Not met by proceeding
  without a reply or any "keep moving instead of asking" instruction — see the Step 3 GATE.
- **Book rules are authoritative.** A `book_rule_violation` finding is the user's own rule for
  this book — treat it as the highest-priority fix in any batch, same standing manuscript-checker
  gives it.
- **A repeated phrase isn't always a bug.** Some repetition is a deliberate motif. When Step 3's
  verification raises doubt, ask before proposing a fix rather than patching on the checker's say-so
  alone.
