---
name: chapter-scene-rewriter
description: |
  Replace a single already-drafted scene inside a chapter's draft.md in place — the scenes
  before and after stay untouched. Fills the gap between chapter-fixer (line-level patches
  only, never reconstructs a scene) and chapter-writer (append-only — corrupts a draft.md
  that already has content). Surgical at the scene grain, not the sentence grain.
  Use when: (1) User says "Szene umschreiben", "rewrite this scene", "scene neu schreiben",
  (2) chapter-fixer's Surgical Mode Rule 6 escalates because one scene's findings are too
  dense or overlapping for line patches, (3) chapter-reviewer's Suggested Next Step
  recommends a whole-scene reconstruction, (4) the user wants a scene reworked for a reason
  no checker flagged (pacing, emotional register, a scene that isn't landing) — no prior
  review required. Fiction books only for now; memoir books get redirected, see Step 0.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug> <chapter-slug> [scene-number]"
---

# Chapter Scene Rewriter

Chapter-scene-rewriter closes the gap between "a scene needs to be reconstructed, not
patched" and "chapter-writer can safely do that" — it can't: chapter-writer's Step A2 is
append-only and corrupts an already-drafted `draft.md` if invoked on a chapter that already
has content (same reason chapter-fixer exists for line-level fixes). This skill reads the
target scene, drafts a full replacement under the same craft standards chapter-writer
applies, and swaps it in via a single `Edit` call — everything outside the scene's
boundaries stays exactly as it was.

**Position in workflow:** ad hoc, whenever a scene inside an already-drafted chapter needs
reconstructing rather than patching — reached from chapter-fixer's Surgical Mode Rule 6,
chapter-reviewer's Suggested Next Step, or invoked directly by the user for reasons no
checker raised. Not part of the fixed pipeline order. After the swap, the chapter normally
goes back through `/storyforge:chapter-reviewer` — this skill does not auto-trigger that or
any other downstream checker; the author decides when.

## Step 0 — Resolve Book Context

Call MCP `get_book_full(book_slug)`. If it returns an `error` key, stop and tell the user the
book wasn't found at the expected path. Otherwise extract `author` (→ `author_slug`),
`book_category`, and — from `chapters_data[chapter_slug]` (the raw book dict keys the chapter
map as `chapters_data`, not `chapters`) — this chapter's integer `number` (needed for Step
6.5) and its `status` (needed for Step 7's Draft-Skip gate).

If `book_category == "memoir"`: stop and tell the user — *"chapter-scene-rewriter unterstützt
aktuell nur Fiction-Bücher (Consent-Gates und Anonymisierungs-Logik für Memoir fehlen noch).
Für eine Memoir-Szene bitte über chapter-fixer angehen, falls sich das Problem auf einzelne
Sätze eingrenzen lässt, oder die Szene manuell direkt in draft.md bearbeiten — chapter-writer-
memoir ist append-only und würde den bestehenden Draft beschädigen, genau das Problem, das
dieser Skill für Fiction löst."* Do not continue in this skill.

## Prerequisites — MANDATORY LOADS

Same standard chapter-writer applies for new prose — a rewritten scene is new prose and
carries the same continuity risk as one that was never drafted.

1. **Chapter writing brief** — MCP `get_chapter_writing_brief(book_slug, chapter_slug)`.
   Load and honor every populated field exactly as chapter-writer's Prerequisite 1 does;
   `pov_character_inventory` / `pov_character_state` warnings → surface, do not invent.
   `review_handle` — store as `{review_handle}`; used in Step 1 item 3 to keep any unresolved
   inline feedback block out of the located scene span.
2. **Author profile** — MCP `get_author(author_slug)`. `writing_discoveries.recurring_tics` /
   `style_principles` / `donts` apply to the replacement exactly as they would to new prose.
   **Style Suppressions:** Check the book CLAUDE.md's `## Style Suppressions` section
   (Prerequisite 9) — any `style_principles` heading matching an entry is skipped for this
   book, same as chapter-writer Prerequisite 2.
3. **Genre README(s)** — MCP `get_genre()` for each genre.
4. **Craft references** — MCP `get_craft_reference()`: `chapter-construction`,
   `dialog-craft`, `show-dont-tell`, `pacing-guide`, `anti-ai-patterns`, `prose-style`,
   `simile-discipline`.
5. **World files** — `resolve_path(book_slug, "world", "setting.md")` (MCP), then read.
   Travel Matrix and location facts.
6. **Story timeline** — `resolve_path(book_slug, "plot", "timeline.md")` (MCP), then read.
7. **Canon log** — `canon_brief` from the writing brief (`pov_relevant_facts` +
   `changed_facts`); `pov_relevant_facts_truncated` → call standalone `get_canon_brief()`.
8. **World Rules** — `resolve_path(book_slug, "world", "rules.md")` (MCP); if `exists` →
   read. Missing → skip silently.
9. **Book CLAUDE.md** — MCP `get_book_claudemd(book_slug)`. **Why:** CLAUDE.md Rule 17
   requires this before writing or reviewing a chapter — feeds the Style Suppressions check
   above and Pre-Logic Audit 4.5. If this returns an `error` key (no CLAUDE.md yet), treat it
   as "no additional rules/suppressions" and continue.
10. **Shared procedures** — MCP `get_craft_reference("chapter-writing-shared")`. This skill
    reuses `§ Pre-Logic Audit`, `§ EA-Scan Protocol`, `§ User Feedback Handling`, and
    `§ Fact Recording Gate` by name below — do not re-derive them inline.
11. **Chapter draft + outline** — Resolve and read `resolve_path(book_slug, "chapters",
    "{chapter_slug}/draft.md")` and the chapter's `README.md`. If `draft.md` doesn't exist:
    stop, tell the user chapter-writer must draft the chapter first — there is no existing
    scene to replace. Check `README.md` for a `## Scene Plan` section — if absent, this
    chapter was drafted in chapter-writer's Mode B (Full Chapter); see Step 1 item 2 for the
    fallback.
12. **Regression baseline** — MCP `validate_chapter(book_slug, chapter_slug)` and
    `count_words(book_slug, chapter_slug)` *before* any edit. Step 6 diffs against this.

## Step 1 — Locate and Confirm the Target Scene Span

This step's output is a **user-confirmed** text span — nothing gets drafted until the
boundary itself is confirmed. `draft.md` has no explicit scene-boundary marker: a blank line
is chapter-writer's append convention between scenes, but a blank line is also the ordinary
Markdown paragraph separator, so it cannot be trusted alone to delimit a span. Since Step 5's
swap is destructive, a wrong boundary here is not a "spot it in review and fix it" mistake —
it silently duplicates or drops prose the moment the `Edit` lands.

1. **Identify which scene.** If `scene_number` was given as the third argument, use it
   against the `## Scene Plan` in `README.md`. Otherwise identify it from context: an
   escalation from chapter-fixer/chapter-reviewer names the scene already; a direct user
   request needs a scene number, a quoted snippet, or a description ("the scene where they
   argue at the door") — ask if none of these narrow it to exactly one scene.
2. **No `## Scene Plan` (Mode B chapter, see Prerequisites 11).** There is no per-scene index
   to resolve a number against. Ask the user to identify the target directly — a quoted
   snippet or a specific description — and skip the Scene Plan cross-check in item 3; use the
   README's `Scene Beats` outline instead, if present, for the continuity check in Step 3.
3. **Locate the span.** Read the scene's one-line Scene Plan summary (or the user's
   description) and find where `draft.md`'s prose matches it. Read outward from that anchor,
   paragraph by paragraph, until the content clearly shifts — new time, new location, or a
   goal/conflict/outcome that the Scene Plan attributes to a different scene. A blank line
   alone is not a stop condition; keep reading past it if the content is still the same scene.
   A `{review_handle}:` block sitting at the span's edge is excluded from the boundary by
   default — it belongs to whichever scene it's commenting on, usually the neighbor, not this
   one. A block sitting *inside* the span is a different case: a contiguous `old_string` can't
   carve it out, and this skill never splits one scene into multiple `Edit` calls (Step 5 item
   3, Rules). So it necessarily becomes part of `old_string`. Before treating the span as
   located, surface it and ask the user to choose: (a) the rewrite addresses the feedback, and
   the block is dropped from `new_string`, or (b) the block doesn't apply to this rewrite and
   gets re-emitted verbatim in `new_string`, unresolved. Do not silently drop or silently carry
   it forward without that choice.
4. **Present the located span before drafting anything.** Show: the scene's first and last
   sentence, its word count, and one line each of the content immediately before and after the
   boundary. Ask explicitly: *"Ist das die richtige Szene, und stimmen die Grenzen?"* Do not
   proceed to Step 2 until the user confirms — this is the one decision in this skill that
   cannot be undone after Step 5.
5. **Ambiguous or not found** — do not guess. If two candidate spans both plausibly match, or
   the described scene isn't in this chapter's draft at all, ask the user to confirm which
   one, or point them at `/storyforge:chapter-fixer` if what they actually want is a
   sentence-level fix rather than a full scene swap.

Record the confirmed exact text (verbatim — this becomes the `old_string` in Step 5) and its
word count (for the Step 6 comparison).

## Step 2 — Verify the Rewrite Is Warranted

Run **§ User Feedback Handling** (chapter-writing-shared.md) on whatever triggered this
rewrite — a checker's findings, or the user's own read — before drafting anything:

1. Re-read the current scene. Does the stated problem actually hold up?
2. Check whether an earlier chapter or the established voice justifies what's there.
3. Assess whether "fixing" it would contradict continuity or drop a planted promise.
4. If the complaint doesn't hold up, say so and propose leaving the scene as-is.
5. If it holds up but a smaller fix would do (one or two sentences), redirect to
   `/storyforge:chapter-fixer` instead — this skill is for reconstructing the scene, not for
   what a targeted patch already covers.

## Step 3 — Preserve Continuity Anchors

Before drafting the replacement, establish what the rewrite must not break:

- **Neighboring scenes.** Read the scene immediately before and after the target (if any).
  Note the POV's emotional state and any facts/objects established at the end of the prior
  scene and referenced at the start of the next one — the replacement must still hand off
  correctly on both sides.
- **Scene Plan role.** Re-read this scene's one-line summary in `README.md`'s `## Scene Plan`
  (Mode B chapters without one: use the relevant `Scene Beats` from the outline instead, per
  Step 1 item 2). Unless the user explicitly wants the scene's plot function to change too,
  the replacement must still deliver the same beats — a rewrite changes *how* the scene lands
  them, not *whether* it does.
- **Promises.** If `research/manuscript-report.md` or `analyze_plot_logic` output shows a
  Chekhov's-gun element was planted specifically in this scene, note it — the replacement
  must still plant it, or the removal needs explicit user sign-off (it's a continuity break
  otherwise).
- **§ Pre-Logic Audit** (chapter-writing-shared.md) — run it for this scene exactly as
  chapter-writer's Step A1b does. Emit the bulleted block to chat before any prose. Any gap
  surfaces to the user; never paper over it.

## Step 4 — Write the Replacement Scene

Apply the same craft standard chapter-writer's Step A2 requires: author voice, all five
senses, scene-sequel structure, subtext in dialog, banned-word avoidance, no AI-tells. Target
the original scene's word count within roughly ±20% unless the user asked for a different
length.

**Pre-write tactical check** — same as chapter-writer: if the scene involves combat or group
movement, call `verify_tactical_setup(book_slug, scene_outline_text, characters_present)` and
resolve every warn-severity warning before drafting.

**Pre-swap gates (mandatory, same as chapter-writer Step 6c/6d):**
1. Simile Discipline Scan against `simile-discipline.md`'s two-question test — fix
   autonomously.
2. **§ EA-Scan Protocol** (chapter-writing-shared.md) — interactive hard-gate. No replacement
   text moves to Step 5 until every hit is fixed or explicitly skipped by the user.

## Step 5 — Present for Approval, Then Swap

Unlike chapter-writer's append-then-revise loop, this skill's edit is destructive — the old
scene text is gone the moment the `Edit` lands. The boundary itself was already confirmed in
Step 1; this approval is specifically for the replacement *content*. Approval happens
**before** the write, not after:

1. Show the full replacement scene in chat alongside a one-line diff summary (word count
   old → new, what changed and why).
2. Wait for explicit approval. Silence is not approval — same standard chapter-writer's WAIT
   GATE applies.
3. On approval: Read the full `draft.md` again immediately before writing (GH#27 — the copy
   from Prerequisites/Step 1 may be stale). Call `Edit` with `old_string` = the exact span
   confirmed in Step 1, `new_string` = the approved replacement. One `Edit` call for the whole
   scene, not a patchwork of smaller edits.
4. If the `Edit` fails (span no longer matches — e.g. the user or another tool touched the
   chapter mid-session), re-locate and re-confirm the span (Step 1) before retrying; never
   force a stale match.

## Step 6 — Re-Validate

1. `validate_chapter(book_slug, chapter_slug)` — diff explicitly against the Prerequisites 12
   baseline, same as chapter-fixer Step 5 item 1. State the result even when empty.
2. `count_words(book_slug, chapter_slug)` — compare against baseline; the delta should
   roughly match the scene's word-count change. Investigate before reporting success if it
   doesn't reconcile.
3. **Recommend re-running `/storyforge:chapter-reviewer`** — always, not conditionally. A
   full scene reconstruction is definitionally above chapter-fixer's own "recommend re-run"
   threshold (10+ fixes or 2+ categories); treat this the same way.

## Step 6.5 — Record Revision Summary

If Step 5 landed an `Edit`, call `add_canon_fact(book_slug, chapter_num=<this chapter's
number, from Step 0>, subject="chapter-scene-rewriter-pass", fact="Scene {scene_number}
rewritten: <one-line reason>", domain="revision")` — same pattern chapter-fixer Step 5.5 and
manuscript-checker §6 use. This is the only persistent record of the swap once the session
ends. **Skip entirely if the user declined approval at Step 5** — nothing changed, nothing to
record.

## Step 7 — Promise Re-Check

Gated the same way **§ Step 7 Draft-Skip Scope** (chapter-writing-shared.md) gates promise
extraction for chapter-writer: **skip this step entirely if this chapter's `status` (from
Step 0) is `Draft`** — a promise's fired/unfired status is a claim about the finished chapter,
not a still-in-progress one. For chapters at `Review` or `Final`:

If Step 3 flagged a promise planted in the original scene, or the replacement plants a new
one, run the **Promise / Setup-Element Extraction** procedure from **§ Fact Recording Gate**
(chapter-writing-shared.md), scoped to re-examining this scene for setup-elements. Then call
`register_chapter_promises` — `upsert_promises` merges by `description`, so submit **only this
scene's new or revised entries**; every other scene's promises are left untouched
automatically and must NOT be re-submitted (an LLM-paraphrased copy of an unchanged entry
misses the merge key and appends a duplicate row instead of no-op'ing). To **retire** a promise
the original scene planted that the replacement no longer does: call `get_chapter_promises`
first, copy that promise's `description` **verbatim**, and resubmit it with `status:
"retired"` — the merge key must match exactly or a new row gets added alongside the stale one
instead of replacing it. Skip silently if neither applies.

## Rules

- **One scene per invocation.** If the rewrite grows to cover multiple scenes, that's a
  chapter-level reconstruction — stop and point at `chapter-writer`'s Mode A instead (reusing
  its own Scene Plan), rather than chaining several scene-rewriter passes.
- **Never blind-swap.** The replacement needs explicit user approval before the `Edit` call —
  there is no post-hoc revision loop the way chapter-writer's append mode has, because the
  original text is gone once the swap lands.
- **No auto-trigger of downstream checkers.** Recommend re-running chapter-reviewer (Step 6);
  do not invoke it, chapter-humanizer, or chapter-proofreader automatically. The author
  decides when.
- **Abstain from invention.** Same standard as chapter-writer: if a concrete detail isn't
  sourced from the brief, `world/setting.md`, `characters/*.md`, `plot/timeline.md`, or a
  neighboring chapter's draft, surface the gap and ask instead of inventing it.
- **Author voice is mandatory.** A replacement that's craft-clean but reads like a different
  author is a regression, not a fix — same standard chapter-fixer applies to its patches.

## Error Handling

- No `draft.md` for this chapter → stop, tell the user `chapter-writer` must draft it first.
- Target scene not locatable or ambiguous → ask (Step 1 item 5), never guess-edit.
- Step 2 verification finds the complaint doesn't hold up → report that explicitly, propose
  no change, stop.
- `Edit` fails because the span went stale → re-locate before retrying (Step 5 item 4).
