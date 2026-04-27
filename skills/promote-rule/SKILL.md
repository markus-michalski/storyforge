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

## Step 1: Identify the Rule

If the user provided a phrase argument, use it. Otherwise ask (AskUserQuestion):

> "Which phrase or rule do you want to promote? Paste the exact text as it appears in the current scope."

Load the current book's CLAUDE.md via MCP `get_book_claudemd(book_slug)` and list all `## Rules` entries so the user can pick from the list.

## Step 2: Confirm Current Scope

Ask (AskUserQuestion):

> "Where does this rule currently live?"

Options:
- **This book** — book CLAUDE.md `## Rules`
- **This author** — author `vocabulary.md`

(Global → higher is not possible. If the user requests it, explain and offer to improve the reason or pattern instead.)

## Step 3: Choose Target Scope

Ask (AskUserQuestion):

> "Where should this rule apply after promotion?"

Options:
- **This author** (all books by this author) — available when current scope is book
- **Global** (all books, all authors) — available from book or author scope

## Step 4: Verify Rule Is Not Already Present

Check the target file for the phrase. If already present:

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

Call MCP `promote_rule(phrase, reason, from_scope, to_scope, book_slug, author_slug, remove_from_source)`.

The `reason` is extracted from the existing rule entry or asked if not present:
- Book CLAUDE.md: extract text after `` `{phrase}` — ``
- Author vocabulary: use the section name as reason context

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

## Important Behavior

- **Dedup protection**: always check target before writing.
- **Reason preservation**: carry the original reason text to the promoted entry plus a promotion note: `_(promoted from {from_scope} on {date})_`.
- **Never promote without confirmation.** Especially global writes affect every user of the plugin.
- **Structural rules** (non-phrase rules in book CLAUDE.md) cannot be promoted to author or global scope via this skill — they are book-specific by nature. Explain this if the user tries.
