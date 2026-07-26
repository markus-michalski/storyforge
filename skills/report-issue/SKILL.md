---
name: report-issue
description: |
  Report a recurring prose issue and convert it into an enforceable rule.
  Use when: (1) User says "problem:", "recurring issue:", "/storyforge:report-issue",
  (2) User notices a prose tic, banned phrase, or structural pattern that keeps slipping through,
  (3) Beta feedback surfaces a repeating problem that should become a hard rule.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug] [\"phrase or pattern description\"]"
---

# Report Issue

Converts a user-reported prose problem into an enforceable rule at book, author, or global scope. Conversational — asks clarifying questions before writing anything.

## Step 1: Parse or Ask for the Issue

If the user provided a phrase or description as an argument, use it directly.
Otherwise ask (AskUserQuestion):

> "What's the recurring problem you're seeing? Describe the phrase, pattern, or behavior — the more specific the better."

Accept free-form input. Examples:
- `"the model uses 'pulsed with energy' constantly"`
- `"walking order is wrong in combat scenes — human at the back"`
- `"too many sentences starting with 'He'"`

## Step 2: Load Context

Resolve the active book first — `get_book_full()` needs a slug, it does not discover one on its own:

1. If a book slug was given as an argument, use it directly.
2. Otherwise call MCP `get_session()` — if its `last_book` field is set, propose it.
3. If there is no session book (or the user wants a different one), call MCP `list_books()` and ask the user to pick one (AskUserQuestion).

Once `book_slug` is known:
- MCP `get_book_full(book_slug)` — returns `title` (needed for `source_context` below) and `author` (the author_slug — the field is named `author`, not `author_slug`, in the response).
- MCP `get_author(author_slug)` — returns the author profile including `writing_discoveries.donts`. Used for the Author-scope dedup check in Step 3/Step 6 (does this phrase already exist as a banned phrase for this author?) and to confirm the author profile exists before Step 6 tries to write to it.

Compute `source_context` now, since Step 5's preview and Step 6's write both need the identical string:
- `source_context = "report-issue based on {book_title} Ch {chapter_number} review"` when a specific chapter was named in Step 1.
- `source_context = "report-issue based on {book_title} feedback"` otherwise.

## Step 3: Clarify the Rule

Ask **Pattern** first, on its own — its answer determines what (if anything) still needs asking, so it cannot be batched with Scope in a single call:

1. **Pattern** — "What's the exact phrase or regex trigger?"
   Options: Literal phrase (e.g. `pulsed with energy`) / Regex pattern / Structural rule (not a phrase)

**If Pattern = Structural rule:** don't ask Scope or Severity at all — scope defaults to book_rules DB, freeform text, no backtick-wrapped pattern. Skip straight to Step 5 (Step 4's scan is also skipped — see below).

**If Pattern = Literal phrase or Regex:** ask Scope on its own first (AskUserQuestion) — Severity's applicability depends on the Scope answer, so it cannot be in the same call:

2. **Scope** — "Where should this rule apply?"
   Options:
   - This book only — writes to book_rules DB
   - This author only — writes to author discoveries (applies to all books by this author)
   - Global (all books, all authors) — writes to `reference/craft/anti-ai-patterns.md`

**Then, in a second AskUserQuestion call, ask Severity — but only when Scope = "This book only".** For the other two scopes, tell the user the fixed behavior instead of asking (there is nothing to choose):

3. **Severity** (Book scope only):
   Before asking, tell the user up front: *there is no flag-but-never-block tier for a scannable phrase* — the same backtick-wrapping that makes a phrase detectable at all is what the chapter-draft-save hook and the manuscript-checker's book-rule scanner both treat as a hard stop, regardless of whether the wording says "avoid" or "watch for". The only real dial is *when* it blocks:
   - **Block on first hit** — draft is rejected the moment the phrase appears once.
   - **Allow up to N per chapter** — ask for N; still a hard stop once a chapter exceeds the cap (scaled against draft progress), but tolerates occasional use first. Good for "fine occasionally, not every paragraph" tics.

   If the user wants a phrase that is genuinely never enforced (no blocking, ever), say that requires going back to Pattern = Structural rule instead — an un-backticked phrase is invisible to every scanner, so it only survives as freeform guidance the chapter-writer/chapter-reviewer prompts may or may not honor.

   For the other two scopes, state instead of asking:
   - **Author scope**: "Author-scope banned phrases are enforced as a hard block by the chapter-draft-save hook, across every book by this author. Note this is enforced only at draft-save time — it is not picked up by a full-manuscript `manuscript-checker` scan, which reads book-scope rules only."
   - **Global scope**: "Global anti-AI-patterns entries are always advisory (warn) — there's no hard-block tier at global scope."

## Step 4: Scan for Existing Occurrences

If the rule is a literal phrase or regex (not structural):

`scan_manuscript` cannot be used here — it has no parameter for an arbitrary search phrase; it only detects pre-registered categories (book rules already written to the DB, the curated cliché list, structural repetition, etc.), never a phrase the user is reporting for the first time. Count occurrences directly instead:

1. Call `resolve_path(book_slug, "chapters", "")` (MCP) to get the chapters directory (handles series books — resolves within the correct book's own subtree), then list all `draft.md` files within it.
2. Read each draft and count occurrences of the phrase.
3. Report: "Found N occurrences across M chapters: [chapter list with counts]"

This confirms the pattern is real before committing the rule. Detection going forward depends entirely on scope:
- **Book scope**: once written in Step 6, `manuscript_checker`'s book-rule scanner (run via `/storyforge:manuscript-checker`) WILL detect it, because it reads book_rules DB directly.
- **Author scope**: only the chapter-draft-save hook enforces it going forward (see Step 3) — a full `/storyforge:manuscript-checker` pass will NOT surface it as a finding.
- **Global scope**: detection depends on the phrase landing in the exact section/format the global loaders parse — see Step 6.

## Step 5: Confirm Before Writing

Check for an existing duplicate first:
- **Book scope**: call MCP `list_book_rules(book_slug)` and compare the new phrase against each rule's `extracted_patterns`.
- **Author scope**: compare the new phrase against the `writing_discoveries.donts` entries already loaded from `get_author()` in Step 2.
- **Global scope**: skim the relevant section of `anti-ai-patterns.md` (Step 6 names the exact section) for the phrase.

If it already exists at the requested scope, report that and offer to escalate scope (via `/storyforge:promote-rule`) instead of writing a duplicate — do not proceed to write.

Otherwise, present a summary:

```
Rule to add:
  Phrase:    "{phrase}"
  Severity:  {"block on first hit" | "block after N per chapter" | "hard block (author scope, fixed)" | "advisory/warn (global scope, fixed)" | "n/a — structural rule, freeform text"}
  Scope:     {book|author|global}
  Reason:    {one-line summary of what the user reported}
  Source:    {source_context}

Found in:  {N} occurrences / "No existing occurrences — adding as preventive rule"

Write this rule?
```

Use AskUserQuestion:
- **Yes, write the rule** — proceed
- **Adjust scope/severity** — go back to Step 3 with current answers pre-filled
- **Cancel** — abort

## Step 6: Write the Rule

Call the appropriate tool based on scope:

- **Book scope**: MCP `append_book_rule(book_slug, text)` — this tool takes a single freeform `text` field, not separate phrase/reason/severity/source_context parameters. Enforcement is purely backtick-driven (see Step 3) — build `text` accordingly:
  - **Block on first hit**: `` Avoid `{phrase}` — {reason} _(added {date} — source: {source_context})_ ``
  - **Allow up to N per chapter**: `` Watch for `{phrase}` — max {N} per chapter — {reason} _(added {date} — source: {source_context})_ `` (the `max N per chapter` phrase is required verbatim — it's what `_extract_chapter_limit` parses to set the cap; without it the rule hard-blocks on first hit regardless of intent)
  - Check the tool's returned `warnings` and `extracted_patterns` — surface any to the user (e.g. if the phrasing doesn't actually extract a scannable pattern), and confirm `extracted_patterns` is non-empty so the rule isn't silently unscannable.
  - Report back the returned `rule_id`.
- **Author scope**: MCP `add_vocabulary_entry(author_slug, entry_type="banned", text=text)` where `text` is built as `` `{phrase}` — {reason} _(added {date} — source: {source_context})_ `` — stores to the same `author_discoveries` `donts` type the chapter-draft-save hook reads (`write_author_banned_phrase` stores the phrase in **bold**, which the hook's extractor does not pick up at all — always use `add_vocabulary_entry` with a backtick-wrapped phrase here instead, never `write_author_banned_phrase`). Report back the returned `discovery_type` and whether it was `already_present`.
- **Global scope**: Direct Write to `{plugin_root}/reference/craft/anti-ai-patterns.md`. The write target and exact line format depend on Pattern type — the loaders only recognize these two shapes, and a plain end-of-file append lands in neither and is silently never loaded:
  - **Literal phrase**: append a new numbered entry inside `### Heavily Flagged Words and Phrases (AI Tell Indicators)` (under `## 1. Known AI Tells — Vocabulary`), continuing the existing numbering: `` {N}. **{phrase}** — {reason} ``. Only `**bold**` terms inside that exact section are read by `load_global_ai_tells`.
  - **Regex pattern**: append a new line inside `## 11. Known AI Tells — Elegant Abstraction Register` (before the next `## N.` heading): `` **Banned shape:** `{regex}` ``. Only lines matching that exact prefix inside that exact section are read by `load_global_shape_bans`.
  - Both loaders hardcode `severity="warn"` — always advisory, matching Step 3.

Where `date` is today's date (from the current session context), formatted `YYYY-MM-DD`.

## Step 7: Optional Manuscript Scan with New Rule

If there were existing occurrences (Step 4 found hits):

- **Book scope**: ask "The pattern already appears in {N} places. Run `manuscript-checker` with this rule now to surface all violations?"
  Use AskUserQuestion:
  - **Yes, run scan** — trigger `/storyforge:manuscript-checker` with the new rule active. Report hits with chapter references and severity.
  - **No, I'll address them later** — skip.
- **Author scope**: skip this offer — `manuscript-checker` will not detect author-scope rules (Step 3/4); mention that the hook will catch new occurrences going forward, but existing ones must be found manually (the Step 4 grep result already lists them).
- **Global scope**: same caveat as Book scope — offer the scan, since `_scan_global_shape_bans` does read the global file.

## Step 8: Report Result

```
Rule added:
  "{phrase}" — {severity} — {scope}
  {Book scope}:   rule_id {rule_id} in book_rules DB
  {Author scope}: author_discoveries [donts] for {author_slug} ({"written" | "already present"})
  {Global scope}: {plugin_root}/reference/craft/anti-ai-patterns.md ({section name})
  Source: {source_context}

{If occurrences found}: {N} existing violations in {chapter list}.
  Run /storyforge:manuscript-checker to review them (book/global scope only — see Step 7).

{If global scope}: Consider opening a PR to share this rule upstream
  if it's not book-specific vocabulary.
```

## Important Behavior

- **Never blindly accept user's first phrasing.** If the regex is too broad (e.g. `"the"`) or the description is vague, ask for a more specific trigger. A rule that fires on everything is worse than no rule.
- **Structural rules** (walking order, POV boundary) go in book_rules DB as freeform rules, not phrase patterns. No scanner can detect them, but the skill prompts (chapter-writer, chapter-reviewer) will honor them.
- **Dedup**: check for an existing match at the requested scope before writing (Step 5) — report it and offer to escalate scope instead of adding a duplicate.
- **Phase ordering**: Clarify first → scan → confirm → write. Never write without explicit confirmation.
