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
- **This author** — author `author_discoveries` DB

(Global → higher is not possible. If the user requests it, explain and offer to improve the reason or pattern instead.)

## Step 3: Choose Target Scope

Ask (AskUserQuestion):

> "Where should this rule apply after promotion?"

Options:
- **This author** (all books by this author) — available when current scope is book
- **Global** (all books, all authors) — available from book or author scope

## Step 4: Verify Rule Is Not Already Present

- **Target is author scope**: Load `mcp__storyforge-mcp__get_author(slug)` and scan
  `writing_discoveries.donts` for the phrase (case-insensitive substring).
- **Target is global scope**: Read `{plugin_root}/reference/craft/anti-ai-patterns.md` directly.

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
- **Author → Global** or **Book → Global**: Direct Write — append the rule entry to `{plugin_root}/reference/craft/anti-ai-patterns.md`.

The `reason` is extracted from the existing rule entry or asked if not present:
- Book CLAUDE.md: extract text after `` `{phrase}` — ``
- Author vocabulary: use the section name as reason context

**Remove from source (only when user chose "Yes, promote" in Step 5):**
- **From book scope**: Read the book's CLAUDE.md via `get_book_claudemd(book_slug)`. Remove the rule entry via direct Edit. Call `get_book_claudemd(book_slug)` once more to confirm.
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

## Important Behavior

- **Dedup protection**: always check target before writing.
- **Reason preservation**: carry the original reason text to the promoted entry plus a promotion note: `_(promoted from {from_scope} on {date})_`.
- **Never promote without confirmation.** Especially global writes affect every user of the plugin.
- **Structural rules** (non-phrase rules in book CLAUDE.md) cannot be promoted to author or global scope via this skill — they are book-specific by nature. Explain this if the user tries.
