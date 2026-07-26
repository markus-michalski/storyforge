---
name: promote-rule
description: |
  Promote a banned-phrase rule from book scope to author or global scope.
  Use when: (1) User says "promote rule", "make this rule global", "promote to author",
  (2) A book-scoped rule proved useful and should apply to all books by this author or globally,
  (3) User runs /storyforge:report-issue and requests escalation of an existing rule.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug] [\"phrase\"] [--to author|global]"
---

# Promote Rule

Moves a banned-phrase rule from a lower scope to a higher scope.
Supported promotions: book → author, author → global, book → global.

`{plugin_root}` (used below) = the directory containing this plugin's own top-level `CLAUDE.md` — in a real install this is the plugin's cache/install directory, **never** any local source-repo checkout of the plugin. Resolve it as the plugin directory this SKILL.md file itself lives under (two levels up from `skills/promote-rule/SKILL.md`). If that's ever ambiguous in the running environment, ask the user to confirm the path before writing rather than guessing — a wrong guess either fails the write or silently edits a stale checkout.

## Step 1: Identify the Rule

If the user provided a phrase argument, use it. Otherwise ask (AskUserQuestion):

> "Which phrase or rule do you want to promote? Paste the exact text as it appears in the current scope."

Load candidates from **both** possible source scopes up front, so the exact value Step 6's removal call needs is already captured regardless of what the user confirms in Step 2:
- **Book scope**: MCP `list_book_rules(book_slug)` — structured `index`/`raw_text` per entry, backed by the book_rules DB (Phase 4 migration).
- **Author scope**: MCP `get_author(author_slug)` → `writing_discoveries.donts` — capture each entry's full **`.text`** field verbatim (includes Markdown bold and any reason/promotion-note suffix, not just the bare phrase; this exact string is required by Step 6's `delete_discovery` call).

Let the user pick from either list by index or pasted text.

## Step 2: Confirm Current Scope

Ask (AskUserQuestion):

> "Where does this rule currently live?"

Options:
- **This book** — book_rules DB, book-scoped (rendered under `## Rules` in `get_book_claudemd()`'s combined output)
- **This author** — author `author_discoveries` DB

**If the user says the rule is already at global scope:** stop here — do not proceed to Step 3. Global is the highest scope and cannot be promoted further. Tell the user this explicitly, then offer to help improve the existing global rule's reason or pattern text instead (a plain edit to `reference/craft/anti-ai-patterns.md`, not a promotion).

## Step 3: Choose Target Scope

Ask (AskUserQuestion):

> "Where should this rule apply after promotion?"

**Build the options list based on Step 2's answer — do not always offer both:**
- If current scope is **book**: offer both **This author** (all books by this author) and **Global** (all books, all authors).
- If current scope is **author**: offer **only Global**. Do not re-offer "This author" — the rule already lives there, so promoting it to itself is not a meaningful choice.

## Step 4: Verify Rule Is Not Already Present

- **Target is author scope**: Load `mcp__storyforge-mcp__get_author(slug)` and scan
  `writing_discoveries.donts` for the phrase (case-insensitive substring).
- **Target is global scope**: Read `{plugin_root}/reference/craft/anti-ai-patterns.md` and check specifically within the `### Heavily Flagged Words and Phrases` section (the section Step 6 writes into) — the file's other sections and explanatory prose can incidentally contain the same words without that being a duplicate rule.

If already present:

> "This phrase already exists in the target scope. No action needed."

Offer to show where it appears and exit.

## Step 5: Confirm Before Acting

Present summary:

```
Promote rule:
  Phrase:     "{phrase}"
  From:       {from_scope}
  To:         {to_scope}
  Will write: {target file path}
  Will remove from source: Yes (keeps scopes clean)

Proceed?
```

Use AskUserQuestion:
- **Yes, promote** — proceed
- **Promote but keep original** — write to target, skip removal from source
- **Cancel** — abort

## Step 6: Execute Promotion

Execute in two sub-steps:

**Write to target scope:**
- **Book → Author**: MCP `write_author_banned_phrase(author_slug, phrase, reason)` with reason including `_(promoted from book-scope on {today's date})_`.
- **Author → Global** or **Book → Global**: Direct Write. Global enforcement is parsed **only** by `tools/banlist_loader.py::load_global_ai_tells()`, which reads numbered entries (`N. **term** — reason`) strictly inside the `### Heavily Flagged Words and Phrases` section of `{plugin_root}/reference/craft/anti-ai-patterns.md`. A rule written anywhere else — a new section, appended at end-of-file, or any other heading — is invisible to every scanner and the promotion becomes a silent no-op. Reproduce the exact append logic that `tools/rule_writer.py::write_global_rule()` already implements for this (that function is dead code — not wired to any MCP tool — so replicate its logic as a direct Write, do not try to call it):
  1. Read the file; locate `### Heavily Flagged Words and Phrases` (case-insensitive).
  2. Find the section's end — the next `##` or `###` heading (currently `### Why These Words Signal AI`).
  3. Within that slice only, find the highest existing leading entry number `N.` and use `N+1`.
  4. Insert `{N+1}. **{phrase}** — {reason} _(promoted from {from_scope} on {today's date})_` as a new line immediately before that next heading, keeping the blank line separating the section from the heading.
  5. Re-run the Step 4 duplicate check against that section slice right before inserting, to avoid a race with a concurrent write.
  **Never** insert at or after `## 11. Known AI Tells — Elegant Abstraction Register` or the trailing `### Sources` section — that region is parsed by the separate `load_global_shape_bans()`, which has no closing heading before end-of-file, so any appended text matching `` **Banned shape:** `regex` `` there would be silently compiled and applied as a global regex ban with no review.
  **This edits the plugin's own shared reference file, not per-book or per-author state — see the caveat in Step 7 for exactly what this write does and does not achieve.**

The `reason` is extracted from the existing rule entry or asked if not present:
- Book rule (from `list_book_rules()`'s `raw_text`): extract text after `` `{phrase}` — ``
- Author vocabulary: use the section name as reason context

**Remove from source (only when user chose "Yes, promote" in Step 5):**
- **From book scope**: Call `update_book_rule(book_slug, rule_index=index, delete=True)` using the `rule_index` already captured in Step 1's listing (preferred — avoids substring-match ambiguity entirely). Only fall back to `rule_match=phrase` if no index was captured. Book rules live in the book_rules DB (Phase 4 migration), not in the raw CLAUDE.md file on disk — a direct file Edit targeting the rendered `## Rules` text would silently do nothing, since that text isn't physically present in the file.
  Check the result **error-first**, not `result.found` directly — `update_book_rule` returns `{error, code}` with no `found` key on three paths, and treating an error payload as "not found" reports the rule as already-gone while it is untouched:
  - `code == "ambiguous_match"` (likely for short phrases — `rule_match` is a case-insensitive substring match over the full rule body, so a phrase like "thing" can match several rules): retry the same call with `rule_index` from Step 1's listing instead of `rule_match`.
  - `code == "disagreeing_resolution"` or `"invalid_args"`: stop and report the error to the user — do not claim removal.
  - No `error` key: proceed as before — check `result.found`/`result.changed`; if `found` is `False`, inform the user the rule was not found (may have been removed already).
- **From author scope**: Call `mcp__storyforge-mcp__delete_discovery(author_slug, discovery_type="donts", text=phrase_text)` where `phrase_text` is the **exact `.text` field value** as returned by `get_author().writing_discoveries.donts[n].text` (full formatted string including any Markdown bold, reason clause, and promotion annotation — not the bare phrase). Check `result.deleted` — if `False`, inform the user the entry was not found (may have been removed already).

Write to target first — confirm success before removing from source.

## Step 7: Report Result

```
Promoted:
  "{phrase}"
  From: {from_scope} ({source_file})
  To:   {to_scope} ({target_file})

{If remove_from_source}: Original entry removed from {source_file}.

The rule is now active for {scope description}.
Run /storyforge:manuscript-checker to see existing violations across your library.
```

**If the target scope is Global**, append this instead of an unconditional "now active" claim: global entries load at **`SEVERITY_WARN` only** (`tools/banlist_loader.py` — `load_global_ai_tells()` and `load_global_shape_bans()` both hardcode warn severity), never block — a global promotion is always weaker enforcement than a book- or author-scope rule authored at block severity, not stronger. It also only changed the plugin's own local `reference/craft/anti-ai-patterns.md` file — it is not committed and will not persist across a plugin update or sync to other installations until it is. Tell the user: "This now warns locally (not blocks) for every book on this install. Consider committing this change (and opening a PR) so it takes effect for other installations too." Do not claim the promotion is durably, universally active, or block-severity, the way a book/author-scope write can be.

**If the target scope is Author**, soften the claim similarly: `write_author_banned_phrase` currently stores the phrase in bold-Markdown (`**{phrase}**`), which the manuscript-checker's Don'ts scanner does not yet recognize (it looks for backtick-wrapped or italic+ban-cue phrasing) — see [storyforge#452](https://github.com/markus-michalski/storyforge/issues/452), open. Report the write as succeeded, but do not claim the phrase is now actively enforced by manuscript-checker until #452 is fixed.

## Important Behavior

- **Dedup protection**: always check target before writing.
- **Reason preservation**: carry the original reason text to the promoted entry plus a promotion note: `_(promoted from {from_scope} on {date})_`.
- **Never promote without confirmation.** Especially global writes affect every user of the plugin.
- **Structural rules** (non-phrase rules in book CLAUDE.md) cannot be promoted to author or global scope via this skill — they are book-specific by nature. Explain this if the user tries.
