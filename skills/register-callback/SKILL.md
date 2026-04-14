---
name: register-callback
description: |
  Register a rule, workflow instruction, or callback for the active book.
  Use when: (1) User types a line starting with `Regel:`, `Workflow:`, or `Callback:`,
  (2) User says "merke dir", "callback", "neue Regel", "ab jetzt immer",
  (3) User wants to persist a detail across sessions (e.g. "Gary soll wiederkommen").
  The entry is appended to the book's CLAUDE.md and survives context compaction.
model: claude-haiku-4-5
user-invocable: true
argument-hint: "<Regel|Workflow|Callback>: <text>"
---

# Register Callback / Rule / Workflow

Deterministic persistence of per-book context. No creativity needed — just extract and store.

## Inputs

- **Explicit prefix message**: `Regel: ...`, `Workflow: ...`, `Callback: ...`
- **Slash invocation with argument**: `/storyforge:register-callback Callback: Gary the cat`
- **Free-form user intent**: "merk dir Gary" → ask for the prefix, don't guess

## Workflow

1. **Resolve active book** — MCP `get_session()` returns the current `book_slug`.
   - If no active book: tell user to `/storyforge:resume <book>` first and stop.

2. **Verify CLAUDE.md exists** — MCP `get_book_claudemd(book_slug)`.
   - If missing: run `init_book_claudemd(book_slug, ...)` with best-effort facts
     pulled from `get_book_full(book_slug)`.

3. **Parse input** — Match one of the three prefixes (case-insensitive):
   - `Regel:` / `Rule:` → **rule**
   - `Workflow:` → **workflow**
   - `Callback:` → **callback**
   - Anything else: ask the user to add a prefix. Do NOT guess.

4. **Append via MCP** — Call the matching tool with the trimmed body:
   - rule → `append_book_rule(book_slug, text)`
   - workflow → `append_book_workflow(book_slug, text)`
   - callback → `append_book_callback(book_slug, text)`

5. **Confirm** — One-line confirmation: `✅ [kind] gespeichert in CLAUDE.md: "[text]"`

## Batch Mode

If the user provides multiple prefixed lines in one message, use
`sync_book_claudemd_from_text(book_slug, text)` to extract and persist all at once.
Report counts per kind.

## Rules

- Never invent a callback from context — only register what the user explicitly marks.
- Do not write plot details, character reveals, or world info here. Those belong in
  `plot/`, `characters/`, `world/`. Tell the user if they try to put plot content in
  a callback.
- Trim surrounding whitespace but preserve the exact text the user typed.
- Idempotent: duplicate entries are silently skipped by the MCP tool.
