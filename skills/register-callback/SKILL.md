---
name: register-callback
description: |
  Register a rule, workflow instruction, or callback for the active book.
  Use when: (1) User types a line starting with `Regel:`, `Workflow:`, or `Callback:`,
  (2) User says "merke dir", "callback", "neue Regel", "ab jetzt immer",
  (3) User wants to persist a detail across sessions (e.g. "Gary soll wiederkommen").
  The entry is stored in the book_rules database and survives context compaction.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<Regel|Workflow|Callback>: <text>"
---

# Register Callback / Rule / Workflow

Mostly-deterministic persistence of per-book context — extract and store, plus a light
advisory judgment call on whether an entry reads as plot/world content (see step 4).

## Inputs

- **Explicit prefix message**: `Regel: ...`, `Workflow: ...`, `Callback: ...`
- **Slash invocation with argument**: `/storyforge:register-callback Callback: Gary the cat`
- **Free-form user intent**: "merk dir Gary" → ask for the prefix, don't guess

## Workflow

1. **Parse input first** — Match one of the three prefixes (case-insensitive):
   - `Regel:` / `Rule:` → **rule**
   - `Workflow:` → **workflow**
   - `Callback:` → **callback**
   - Anything else (including a bare "merke dir ..." with no prefix): ask the
     user to add a prefix. Do NOT guess — and do not make any MCP call at all
     for this turn, not even `get_session()`.
   - If the message contains **multiple** prefixed lines: this is **Batch
     Mode** — note that now, it changes step 4 below.

2. **Resolve active book** — MCP `get_session()` returns the current session
   dict, with the active book in its `last_book` field (there is no
   `book_slug` key).
   - If no active book: tell user to `/storyforge:resume <book>` first and stop.
   - (Only reached once step 1 found at least one valid prefix — never resolve
     the book or touch CLAUDE.md for a message that turns out to have none.)

3. **Verify CLAUDE.md exists** — MCP `get_book_claudemd(book_slug)`.
   - If missing: call `get_book_full(book_slug)` first for a best-effort
     `title`, then run `init_book_claudemd(book_slug, book_title=title)`
     (the parameter is `book_title`, not `title`). `get_book_full` does not
     return `pov` or `tense` — never guess those or invent a `genre` here;
     leave them blank. A slug-only `init_book_claudemd(book_slug)` call is
     legal (the template renders missing facts as em-dashes) if no title is
     available either — this mirrors `harvest-author-rules`' fallback call.
     Getting real `pov`/`tense`/`genre` values means asking the user, which is
     out of scope for this skill; point them at `new-book`'s Book Facts step
     or have them edit the book's CLAUDE.md directly if they want it filled in
     now.

4. **Append via MCP**:
   - **Batch Mode** (multiple prefixed lines, per step 1): call
     `sync_book_claudemd_from_text(book_slug, text)` once with the full message
     text — do not loop and call the per-kind tools below line by line.
     Reconcile: the tool's extractor only matches lines where the prefix
     starts at the very beginning of the line (a leading `-`, a quote marker,
     or a `/storyforge:register-callback` command prefix will NOT match) and
     silently drops any rule/workflow/callback body over 300 characters — so
     compare the returned `counts` total against the number of prefixed lines
     you actually found in step 1. If they don't match, tell the user which
     line(s) are missing and ask them to resend those individually via
     `Single entry`. Always surface a non-empty `errors` array from the
     response verbatim. Then skip step 5's single-entry template.
   - **Single entry**: call the matching tool with the trimmed body:
     - rule → `append_book_rule(book_slug, text)`
     - workflow → `append_book_workflow(book_slug, text)`
     - callback → `append_book_callback(book_slug, text)`

     Advisory content check (not a hard gate — never refuse to call the tool
     over this): if the trimmed body clearly reads as new plot resolution or
     world-building exposition — not just naming a character or prop that
     should recur, which is this skill's normal use case (e.g. "Gary the cat
     soll wiederkommen" is exactly what `Callback:` is for) — still store it,
     but add a one-line note afterward that this kind of detail usually
     belongs in `plot/`, `characters/`, or `world/` instead. Never let this
     check block or delay the actual `append_*` call.

5. **Confirm** — check the tool's response before confirming:
   - If the response has an `error` key: relay that error message and stop —
     do not print a success confirmation.
   - If `inserted` is `false`: tell the user this exact text is already
     stored (duplicate), not that a fresh save happened.
   - Otherwise, one-line confirmation: `OK: [kind] gespeichert in der
     Book-Rules-Datenbank: "[text]"` — this echoes what you sent, not
     necessarily the stored bytes (see the trim/normalize note below).
   - If the response has a non-empty `warnings` list (only `append_book_rule`
     returns these), surface them too — they flag a rule shape the
     manuscript-checker scanner may not be able to enforce.
   - (Batch Mode: report per-kind counts plus any reconciliation note from
     step 4 instead — no single-entry template.)

## Threading Callbacks — Intensity Metadata

A callback that asks the chapter-writer to thread a **prop or motif** through
specific chapters can optionally carry intensity metadata to control
recurrence density. If the user's callback text already includes an
`intensity:` clause, store it as typed. If it doesn't, you can mention this
format and ask whether they want to add one — but see the note below: do not
inject it yourself.

**Format:**
```
Callback: <prop> — Ch N: thread | intensity: <level> | max_mentions: <N> | <note>
```

**Intensity levels:**

| Level | Meaning |
|---|---|
| `passive` | Background only. Max 1 mention per scene. No sensory close-up. No emotional emphasis. |
| `active` | Present and noticed. 2–3 mentions allowed. Character may register it. **(default)** |
| `prominent` | A scene beat. Close-up and emotional emphasis allowed. |

**Example:**
```
Callback: Das Amulett — Ch 32: thread | intensity: passive | max_mentions: 1 | Do not explain before Ch 33.
```

Without intensity metadata the chapter-writer applies `active` behavior. Do
**not** inject an `intensity:` clause yourself when the user didn't write one —
that default is applied downstream by chapter-writer, not by this skill.

Note on storage: the MCP tool trims surrounding whitespace and, for rules
only, may rewrite the first ban-cued quoted phrase to backticks (e.g. `Avoid
"clocked"` → `` Avoid `clocked` ``) so the enforcement hook can pick it up —
do not edit the text yourself beyond trimming, but the tool's own
normalization can still make the stored bytes differ slightly from what the
user typed.

## Rules

- Never invent a callback from context — only register what the user explicitly marks.
- Naming a character or prop that should recur (e.g. "Gary the cat soll wiederkommen")
  is this skill's normal use case, not a violation. Only new plot resolution or
  world-building exposition belongs in `plot/`, `characters/`, `world/` instead — see
  step 4's advisory check. This is a heads-up, not a refusal: still register the entry.
- Trim surrounding whitespace before storing. The MCP tool itself may further normalize
  ban-cued quoted phrases in rules (see the storage note above) — the confirmation echoes
  what you sent, which is not guaranteed to be byte-identical to what ends up stored.
- Idempotent: duplicate entries are silently skipped by the MCP tool (`inserted: false`).
