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
session via `mcp__storyforge-mcp__get_session()` for `book_slug`.

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
      "target_section": "vocabulary | recurring_tics | style_principles | donts",
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

- **Promote (recommended)** — write to author target, optionally remove from book
- **Keep book-only** — leave the rule in book CLAUDE.md, no author write
- **Discard** — remove from book CLAUDE.md, do not promote (rule was wrong)
- **Edit and promote** — let user edit the value/text, then promote
- **Skip for now** — defer this candidate, don't decide

For `world_rule` candidates, default-highlight "Keep book-only" — these are
worldbuilding-specific and rarely transfer.

## Step 5: Execute the user's choice

### Promote (banned_phrase → vocabulary.md)

```python
# Use the existing author-rule writer.
mcp__storyforge-mcp__write_author_rule(
    phrase=candidate.value,
    reason=candidate.rationale,
    author_slug=author_slug,
    source_context="harvest-author-rules",
)
```

If that MCP tool isn't available, call the underlying `tools.rule_writer.write_author_rule` directly via a Python invocation in the skill — but prefer the MCP route once it's wired.

### Promote (style_principle / donts → profile.md ## Writing Discoveries)

```python
# tools.author.discovery_writer.write_discovery
write_discovery(
    profile_path=author_profile_path,
    section=candidate.target_section,  # "recurring_tics" | "style_principles" | "donts"
    text=user_edited_text or build_discovery_text(candidate),
    book_slug=book_slug,
    year_month=current_year_month(),  # e.g. "2026-05"
)
```

Build the discovery text with a bold title + dash + short rationale, e.g.:

```
**"math" as analytical metaphor** — cut on sight unless POV explicitly demands.
```

### Cleanup (after promote)

Ask (AskUserQuestion):

- **Remove from book CLAUDE.md** — clean break, rule lives only in author scope now
- **Annotate as promoted** — keep the rule in the book with `_(promoted to author profile, YYYY-MM-DD)_`

For source `book_rule` only — manuscript findings have no source rule to remove.

```python
remove_book_rule_after_promotion(
    claudemd_path=book_claudemd_path,
    rule_index=candidate.source_rule_index,
    mode="remove" | "annotate",
)
```

### Discard (without promote)

Same `remove_book_rule_after_promotion(mode="remove")` call, no author write.

### Edit and promote

Use AskUserQuestion to capture the edited text, then go through Promote +
Cleanup with the user's text.

## Step 6: Final report

After the walk:

```
Harvest complete.

Promoted to {author_slug}:
  - "{value}" → vocabulary.md
  - "{value}" → profile.md ## Writing Discoveries / Recurring Tics
  - ...

Removed from book CLAUDE.md:
  - rule {idx}: "{title}"
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
  in `vocabulary.md` or `profile.md ## Writing Discoveries`. The user never
  sees them.
- **Recurrence handling** — when a discovery resurfaces in a new book, the
  writer appends a second origin tag (`_(emerged from book-2, YYYY-MM)_`)
  rather than duplicating the bullet. This signals "stable pattern across
  books".
- **No auto-mirror** — promoted entries do NOT get auto-injected into the
  next book's CLAUDE.md. They live in the author profile and are picked up
  via skill load. This keeps book CLAUDE.md lean.
- **World rules stay** — magic-system terms, character names, glossary
  entries are detected via `world/glossary.md`, `plot/canon-log.md`, and
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
- **`MarkersNotFoundError` from `harvest_book_rules`** — book CLAUDE.md is
  missing `<!-- RULES:START -->` / `<!-- RULES:END -->`. Run
  `mcp__storyforge-mcp__init_book_claudemd(book_slug)` or migrate manually.
- **No author resolved** — book README has no `author` field. Ask the user
  to specify via `--author` and retry.
