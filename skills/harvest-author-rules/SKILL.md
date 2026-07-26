---
name: harvest-author-rules
description: |
  Harvest a finished book's findings (book CLAUDE.md rules, banned phrases, recurring tics)
  and migrate the author-level ones into the author profile so they survive into the next book.
  Use when: (1) User says "harvest author rules", "book to author", "author rules", "promote findings",
  "Findings ins Autorenprofil", "Buch-Erkenntnisse promoten",
  (2) Book is in `Revision` status or later — typically pre-export,
  (3) After running `manuscript-checker` and `chapter-reviewer` you want the cross-book stuff to stick.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug] [--author author-slug]"
---

# Harvest Author Rules

The systematic bulk-promotion variant of `promote-rule`. At book end, walks all
buchspezifischen findings and lets you decide per item whether it belongs to
the author identity (next book gets it for free) or stays book-canon (world
rule, magic system, character voice).

This is how the author identity grows over time. `promote-rule` handles single
phrases mid-flight. `harvest-author-rules` handles the systematic pre-export
sweep.

## When to run

- **Status gate**: book must be in `Revision` or later. Earlier than that,
  the manuscript-checker hasn't had enough material to produce stable
  patterns. If `Drafting` — warn the user, offer to run anyway, but recommend
  finishing the manuscript pass first.
- **Sequencing**: ideally after `/storyforge:manuscript-checker` and a full
  pass of `/storyforge:chapter-reviewer`, before `/storyforge:export-engineer`.

## Step 1: Resolve book + author

If a book slug was passed as argument, use it. Otherwise check the active
session via `mcp__storyforge-mcp__get_session()` — the book slug is the
response's `last_book` field (there is no `book_slug` field on that
response).

If no book is resolvable, ask (AskUserQuestion):

> "Which book do you want to harvest from? List of books with status Revision+
> via `/storyforge:book-dashboard`."

Author slug: pulled from the book's README frontmatter `author` field. Override
via `--author` flag if needed.

Resolve book metadata via `mcp__storyforge-mcp__get_book_full(book_slug)`:

- `book.status` — must be `Revision`, `Editing`, `Proofread`, `Export Ready`, or `Published`.
- `book.author` — used as default author slug.

If status is `Drafting` or earlier, ask (AskUserQuestion):

- **Run anyway** — the user knows what they're doing
- **Cancel and finish drafting first** — recommended

## Step 2: Run the harvester

```python
mcp__storyforge-mcp__harvest_book_rules(book_slug, author_slug=resolved_author)
```

Returns:

```json
{
  "book_slug": "firelight",
  "author_slug": "ethan-cole",
  "candidates": [
    {
      "id": "rule-007",
      "type": "banned_phrase | style_principle | world_rule",
      "value": "math",
      "context": "From book CLAUDE.md ## Rules — Math metaphor",
      "evidence": "Book rule index 7",
      "recommendation": "promote | keep_book_only",
      "rationale": "...",
      "source": "book_rule",
      "target_section": "recurring_tics | style_principles | donts",
      "source_rule_index": 7
    }
  ],
  "summary": {
    "total": 18,
    "recommended_promote": 9,
    "recommended_keep_book": 7,
    "recommended_discuss": 2
  }
}
```

If `summary.total == 0`: report "No promotion candidates found." and exit.

## Step 3: Show the summary

Display before walking each candidate:

```
Harvest summary for {book_slug} → {author_slug}:

  {total} candidates total
    {recommended_promote} recommended to promote
    {recommended_keep_book} recommended to keep book-only
    {recommended_discuss} flagged for discussion

I'll walk you through them one at a time.
```

## Step 4: Walk each candidate

For each candidate, present:

```
Candidate {n}/{total} — {type}

  Value:           {value}
  Context:         {context}
  Evidence:        {evidence}
  Recommendation:  {recommendation}
  Why:             {rationale}
  Target section:  {target_section}
```

Use AskUserQuestion with options:

- **Promote (recommended)** — write to author target, optionally remove from book rules
- **Keep book-only** — leave the rule in the book_rules DB, no author write
- **Discard** — remove from the book_rules DB, do not promote (rule was wrong)
- **Edit and promote** — let user edit the value/text, then promote
- **Skip for now** — defer this candidate, don't decide

For `world_rule` candidates, default-highlight "Keep book-only" — these are
worldbuilding-specific and rarely transfer.

## Step 5: Execute the user's choice

### Promote (banned_phrase → author_discoveries DB)

```python
mcp__storyforge-mcp__write_author_banned_phrase(
    author_slug=author_slug,
    phrase=candidate.value,
    reason=candidate.rationale,
)
```

The MCP tool wraps the rule-writer AND invalidates the state cache, so the
next `get_author()` and the next chapter-writing brief reflect the new
phrase without a session restart.

### Promote (style_principle / donts → author_discoveries DB)

```python
result = mcp__storyforge-mcp__write_author_discovery(
    author_slug=author_slug,
    section=candidate.target_section,  # "recurring_tics" | "style_principles" | "donts"
    text=user_edited_text or build_discovery_text(candidate),
    book_slug=book_slug,
    year_month=current_year_month(),   # optional — defaults to today's YYYY-MM
    validate=True,                      # default — emits warnings + extracted_patterns
)
```

Cache invalidation happens automatically. Build `text` as
`**bold title** — short rationale.` so the parser and the manuscript-checker
both pick the bold title up as the scannable phrase. When the bold title
contains a double-quoted phrase (e.g. `**Vague-noun "thing" als Fallback**`),
the manuscript-checker scans for that quoted phrase; otherwise it scans for
the entire bold-title text.

Build the discovery text with a bold title + dash + short rationale, e.g.:

```
**"math" as analytical metaphor** — cut on sight unless POV explicitly demands.
```

#### Surface lint warnings after the write (Issue #218)

The MCP response carries `warnings` and `extracted_patterns` whenever
`validate=True` (the default). Lint never blocks the write — but the
warnings often reveal a write that the manuscript-checker scanner won't
enforce the way the user expects. Always surface them to the user before
moving to the cleanup step:

```
Wrote discovery to author profile.

Extracted scan patterns ({N}):
  - "The room received it."
  - "the silence held it."

Warnings ({M}):
  - mixed_positive_negative_italics
      Italic phrases on both sides of a recommendation marker.
      Italics after the marker silently do NOT extract as banned patterns.
      → Verify the post-marker italics are recommendations, not bans.

  - bold_title_unscannable
      Bold title carries no quoted phrase, the body has no quotes/backticks,
      and the title text contains non-ASCII characters — the title-text
      fallback compiles a non-English rule name that won't match English prose.
      → Add a double-quoted example phrase to the title, or put scannable
        phrases in the body.

The bullet was written as-is. Want to edit and rewrite?
```

If the user picks **Edit and rewrite**, restart the promote step with the
revised text and a fresh `write_author_discovery(validate=True)` call.
Otherwise continue to Cleanup.

Lint code reference:

| Section | Code | What it means |
|---------|------|---------------|
| donts | `mixed_positive_negative_italics` | Italics on both sides of a recommendation marker; post-marker italics are silently NOT extracted |
| donts | `mixed_positive_negative_quotes` | Multiple double-quoted phrases under a ban cue — both extract as bans |
| donts | `scanner_extracts_nothing` | Ban cue without any backtick / quoted / italic — scanner sees nothing |
| donts, recurring_tics, style_principles | `bracket_placeholder` | Backtick body has `[word]` — that's a character class, not `\w+` |
| recurring_tics | `bold_title_unscannable` | German title + no body pattern — title-text fallback won't match English |

### Cleanup (after promote)

Ask (AskUserQuestion):

- **Remove from book rules** — clean break, delete the row from the `book_rules`
  DB, rule lives only in author scope now
- **Annotate as promoted** — keep the rule in the `book_rules` DB with
  `_(promoted to author profile, YYYY-MM-DD)_` appended

For source `book_rule` only — manuscript findings have no source rule to remove.

**Index drift across the walk** — deleting a book rule (this Remove path, or
Discard below) shifts every LATER rule's index down by one in the
`book_rules` DB. `harvest_book_rules()`'s `source_rule_index` values are all
captured once, at Step 2 — they go stale the moment an EARLIER-indexed rule
is removed later in the same walk (annotating does not delete a row, so it
never causes drift — only Remove and Discard do). Track how many
earlier-indexed rules have already been removed so far in this session and
subtract that count from `source_rule_index` before every `update_book_rule`
call below. If unsure, re-run `mcp__storyforge-mcp__list_book_rules(book_slug)`
immediately before the call and confirm the rule at the adjusted index still
matches this candidate's original text before touching it.

Remove:

```python
mcp__storyforge-mcp__update_book_rule(
    book_slug=book_slug,
    rule_index=candidate.source_rule_index,
    delete=True,
)
```

Annotate: read the rule's current text first via
`mcp__storyforge-mcp__list_book_rules(book_slug)` — matched by the row's
`index` field (there is no `rule_index` field on `list_book_rules` rows;
`rule_index` is only the request/response key on `update_book_rule`) —
using that row's `raw_text` field. `update_book_rule`'s `new_text` REPLACES
the rule body, so the annotation must be appended to the existing text, not
written in place of it.

**Whitespace is collapsed on write, every time, not just here** —
`update_book_rule` normalizes `new_text` (`re.sub(r"\s+", " ", text.strip())`
in `tools/claudemd/rules_editor.py`, then stripped again on the DB write)
before storing it. If `raw_text` spans multiple lines, every newline and
run of spaces collapses into a single space in the row written back — the
rule's line structure is not preserved. This is inherent to
`update_book_rule` and not something this call can opt out of; if the
candidate's `raw_text` is multi-line, mention to the user that the annotated
version will read as one flattened line before writing it.

```python
today = date.today().isoformat()  # requires `from datetime import date`
mcp__storyforge-mcp__update_book_rule(
    book_slug=book_slug,
    rule_index=candidate.source_rule_index,
    new_text=f"{raw_text} _(promoted to author profile, {today})_",
    validate=False,  # raw_text is pre-existing, already-approved book content —
                     # only appending a note, not new prose — so skip the
                     # manuscript-checker re-lint the default validate=True
                     # would otherwise trigger (that lint pass is scoped to
                     # genuinely new writes; see write_author_discovery above)
)
```

Check the response's `found`/`changed` flags before reporting the rule as
removed/annotated — `found=False` means the rule no longer exists at that
index (already removed, or the book's rules were renumbered since the
harvest ran).

### Discard (without promote)

Same removal call as Cleanup's Remove path —
`mcp__storyforge-mcp__update_book_rule(book_slug=book_slug,
rule_index=candidate.source_rule_index, delete=True)` — no author write. The
same index-drift adjustment documented under Cleanup's Remove path above
applies here too: subtract the count of already-removed earlier-indexed
rules from `source_rule_index` before calling.

### Edit and promote

Use AskUserQuestion to capture the edited text, then go through Promote +
Cleanup with the user's text.

## Step 6: Final report

After the walk:

```
Harvest complete.

Promoted to {author_slug}:
  - "{value}" → author_discoveries DB [donts]
  - "{value}" → author_discoveries DB [recurring_tics]
  - ...

Removed from book rules (book_rules DB):
  - rule {candidate.source_rule_index} (original harvest index — not the
    drift-adjusted index actually passed to update_book_rule): "{title}"
  - ...

Kept book-only:
  - "{value}"
  - ...

Skipped (deferred):
  - "{value}"

Discarded:
  - "{value}"

Author profile is now richer by {N} entries. The next book by {author_slug}
will inherit these automatically — `chapter-writer` and `chapter-reviewer`
read `## Writing Discoveries` on every load.
```

## Important behavior

- **Dedup is automatic** — the harvester drops candidates that already exist
  in the `author_discoveries` DB. The user never sees them.
- **Recurrence handling** — when a discovery resurfaces in a new book, the
  writer appends a second origin tag (`_(emerged from book-2, YYYY-MM)_`)
  rather than duplicating the bullet. This signals "stable pattern across
  books".
- **No auto-mirror** — promoted entries do NOT get auto-injected into the
  next book's CLAUDE.md. They live in the author profile and are picked up
  via skill load. This keeps book CLAUDE.md lean.
- **World rules stay** — magic-system terms, character names, glossary
  entries are detected via `world/glossary.md`, canon facts DB (Issue #297), and
  the characters/people directories. The harvester defaults them to
  `keep_book_only`.
- **Origin tags survive edits** — the parser tolerates manual edits to the
  profile body. As long as the bullet shape stays intact, harvesting remains
  idempotent.

## Failure modes

- **`SectionMissing` from `write_discovery`** — the author profile predates
  Issue #151 and has no `## Writing Discoveries` section. Offer to migrate:
  read the current profile, append the template scaffold (Recurring Tics /
  Style Principles / Don'ts with `_Frei._` placeholders), then retry.
- **`FileNotFoundError` from `harvest_book_rules`** — the book has no
  CLAUDE.md file at all ("CLAUDE.md not found for book {slug}"). Run
  `mcp__storyforge-mcp__init_book_claudemd(book_slug)` to scaffold one.
  (`MarkersNotFoundError` / missing `<!-- RULES:START -->` /
  `<!-- RULES:END -->` markers can no longer fire here — rules moved to the
  `book_rules` DB in Phase 4, and those markers stopped being load-bearing.)
- **No author resolved** — book README has no `author` field. Ask the user
  to specify via `--author` and retry.
