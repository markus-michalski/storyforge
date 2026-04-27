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

- MCP `get_book_full()` — to know the active book slug and author slug.
- MCP `get_author()` — to know which author vocabulary file to update.

## Step 3: Clarify the Rule

Ask (AskUserQuestion, up to 3 questions in one call):

1. **Pattern** — "What's the exact phrase or regex trigger?"
   Options: Literal phrase (e.g. `pulsed with energy`) / Regex pattern / Structural rule (not a phrase)

2. **Severity** — "Should hits block the draft or just warn?"
   Options: Block (hard stop — draft rejected if phrase found) / Warn (flag but allow)

3. **Scope** — "Where should this rule apply?"
   Options:
   - This book only — writes to book CLAUDE.md `## Rules`
   - This author only — writes to author `vocabulary.md` (applies to all books by this author)
   - Global (all books, all authors) — writes to `reference/craft/anti-ai-patterns.md`

For structural rules (walking order, POV boundary) that cannot be expressed as a phrase: scope defaults to book CLAUDE.md and severity to warn. Skip Step 4 (no scan).

## Step 4: Scan for Existing Occurrences

If the rule is a literal phrase or regex (not structural):

Use MCP `run_manuscript_scan(book_slug, pattern)` if available. Otherwise:
1. List all chapter draft files: `{project}/chapters/*/draft.md`
2. Read each draft and count occurrences of the phrase.
3. Report: "Found N occurrences across M chapters: [chapter list with counts]"

This confirms the pattern is real before committing the rule.

## Step 5: Confirm Before Writing

Present a summary:

```
Rule to add:
  Phrase:    "{phrase}"
  Severity:  {block|warn}
  Scope:     {book|author|global}
  Reason:    {one-line summary of what the user reported}
  Source:    report-issue based on {book_title} feedback

Found in:  {N} occurrences / "No existing occurrences — adding as preventive rule"

Write this rule?
```

Use AskUserQuestion:
- **Yes, write the rule** — proceed
- **Adjust scope/severity** — go back to Step 3 with current answers pre-filled
- **Cancel** — abort

## Step 6: Write the Rule

Call the appropriate `rule_writer` function based on scope:

- **Book scope**: MCP `write_rule_book(book_slug, phrase, reason, severity, source_context)`
- **Author scope**: MCP `write_rule_author(author_slug, phrase, reason, source_context)`
- **Global scope**: MCP `write_rule_global(phrase, reason, source_context)`

Where `source_context = "report-issue based on {book_title} Ch {chapter_number} review"`.

## Step 7: Optional Manuscript Scan with New Rule

If there were existing occurrences (Step 4 found hits), ask:

> "The pattern already appears in {N} places. Run `manuscript-checker` with this rule now to surface all violations?"

Use AskUserQuestion:
- **Yes, run scan** — trigger `/storyforge:manuscript-checker` with the new rule active. Report hits with chapter references and severity.
- **No, I'll address them later** — skip.

## Step 8: Report Result

```
Rule added:
  "{phrase}" — {severity} — {scope}
  Written to: {file path}
  Source: {source_context}

{If occurrences found}: {N} existing violations in {chapter list}.
  Run /storyforge:manuscript-checker to review them.

{If global scope}: Consider opening a PR to share this rule upstream
  if it's not book-specific vocabulary.
```

## Important Behavior

- **Never blindly accept user's first phrasing.** If the regex is too broad (e.g. `"the"`) or the description is vague, ask for a more specific trigger. A rule that fires on everything is worse than no rule.
- **Structural rules** (walking order, POV boundary) go in book CLAUDE.md as freeform rules, not phrase patterns. The manuscript-checker cannot scan them, but the skill prompts (chapter-writer, chapter-reviewer) will honor them.
- **Dedup**: If the phrase already exists at the requested scope, report this and offer to escalate scope instead of adding a duplicate.
- **Phase ordering**: Clarify first → scan → confirm → write. Never write without explicit confirmation.
