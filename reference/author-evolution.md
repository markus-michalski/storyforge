# Author Evolution — How an Author Identity Grows Across Books

*Issue #151 concept document. The companion to `harvest-author-rules` (skill)
and `harvest_book_rules` (MCP tool).*

## Why this exists

A book-writing system that treats every book as a fresh start throws away
hard-won insight. By the end of a draft + revision cycle, an author has
accumulated dozens of finely calibrated craft decisions — banned phrases that
turned out to be tics, structural patterns that proved themselves as habits,
voice principles that emerged through trial.

In StoryForge before #151 these all landed in the **book's** `CLAUDE.md`. The
next book started clean. The author identity was effectively static — what
the user typed into `create-author` once, plus whatever `study-author` could
extract from PDFs.

`harvest-author-rules` closes that loop. The author profile becomes a
**living artifact** that grows with every completed book.

## The three-tier hierarchy

Three places hold rules. Each has a distinct lifecycle and decay rate:

| Tier | Where | Lifecycle | Example |
|------|-------|-----------|---------|
| **Book** | `{book}/CLAUDE.md ## Rules` | Lives with the book — exported, archived together. | "Lykos sense fire affinity by scent" — magic-system canon. |
| **Author** | `~/.storyforge/authors/{slug}/profile.md ## Writing Discoveries` + `vocabulary.md` | Lives with the author across books. Grows over time. | `"math"` as analytical metaphor — Theo-style POV tic. |
| **Global** | `reference/craft/anti-ai-patterns.md` | Lives with the plugin. Applies to every author. | `delve`, `tapestry`, `nuanced` — generic AI tells. |

The hierarchy is **strict**: a finding starts at the book level (where it was
first noticed), and the user explicitly promotes it upward when the pattern
proves cross-cutting.

`promote-rule` handles single-phrase promotions during writing.
`harvest-author-rules` handles the systematic post-draft sweep.

## What lives where in the author profile

### `vocabulary.md`

Single-word and short-phrase bans. Format: bullets under
`### Absolutely Forbidden`. The manuscript-checker scanner reads this as
literal patterns.

```markdown
### Absolutely Forbidden

- delve
- math
- clocked
```

### `profile.md ## Writing Discoveries`

Structural / pattern findings. Three sub-sections:

- **`### Recurring Tics`** — habitual word/metaphor/structure tics. Bold the
  pattern, dash, short rationale, origin tag.
- **`### Style Principles`** — positive craft heuristics that proved
  themselves while writing.
- **`### Don'ts (beyond banned phrases)`** — author-level don'ts that aren't
  single banned phrases.

Each entry carries one or more origin tags:
`_(emerged from {book-slug}, YYYY-MM)_`. When a discovery resurfaces in a
later book, the `harvest-author-rules` writer **appends** a second origin tag
rather than duplicating the bullet — multiple tags signal a stable
cross-book pattern.

## What does NOT promote

`harvest-author-rules` defaults to `keep_book_only` for:

- **World rules** — magic-system canon, glossary terms, kingdom names. These
  are book-canon, not author identity. The classifier checks `world/glossary.md`,
  `plot/canon-log.md`, and the characters/people directories to detect them.
- **Plot canon** — character relationships, world events, plot hooks. Same
  reason as world rules.
- **Character voice quirks** — bound to the character, not the author. A
  character's "math metaphor" is an author tic only if multiple characters in
  multiple books default to it.

The user can still override the classifier and force-promote anything via the
**Edit and promote** option in the skill walk.

## Recurrence: the second-origin-tag rule

When a finding from book 2 matches an existing entry from book 1, the writer
**does not** create a new bullet. It appends the new origin tag to the
existing bullet. After three books, an entry might look like:

```markdown
- **"math" as analytical metaphor** — cut on sight unless POV demands.
  _(emerged from firelight, 2026-05)_
  _(emerged from emberkeep, 2026-09)_
  _(emerged from heartwood, 2027-02)_
```

This is signal: the pattern is stable, the author has a real default. Three
tags carry more weight than one. A future enhancement could surface this in
the chapter-writer brief — "this tic has been flagged in N books, treat as
hard rule."

## What we deliberately did NOT build

- **Auto-mirror to next book** — promoted entries do **not** get auto-injected
  into the next book's `CLAUDE.md`. They live only in the author profile.
  Skills (`chapter-writer`, `chapter-reviewer`) load the profile on every
  call and apply discoveries from there. This keeps each book's CLAUDE.md
  lean and avoids stale duplication.
- **Manuscript-finding integration** — v1 only sources from book CLAUDE.md
  rules. Manuscript-checker findings (cross-chapter repetitions, structural
  tics caught by the scanner) can land in v2 — the harvester already has
  the parameter shape (`findings: list[Finding] | None`); the composition
  layer just doesn't read a pre-computed report yet.
- **Promotion analytics** — no telemetry on which discoveries got applied
  in subsequent books. Could be added later by parsing review reports.

## Workflow recap

```
1. Finish drafting + manuscript-checker pass + chapter-reviewer pass.
2. Book status reaches `Revision`.
3. /storyforge:harvest-author-rules
   → Walk each candidate, decide promote / keep / discard / edit+promote.
   → Promoted entries land in vocabulary.md or profile.md ## Writing Discoveries.
   → Original rules optionally removed from book CLAUDE.md.
4. Start next book.
   → chapter-writer loads `writing_discoveries` automatically via get_author().
   → chapter-reviewer treats `recurring_tics` hits as Major findings.
```

## Failure modes

- **Discovery section missing** — author profiles created before #151 lack the
  `## Writing Discoveries` section. The skill detects this via `SectionMissing`
  and offers to migrate the profile.
- **Origin tag drift** — manual edits to the profile that break the
  `_(emerged from X, YYYY-MM)_` shape will silently drop the origin from the
  parser's output. The bullet text still parses; only the origin is lost.
  This is acceptable — the entry itself remains effective.
- **Conflicting recurrences** — if the same discovery emerges in two books in
  the same month with different rationales, the writer appends the duplicate
  origin tag once and merges. Use `Edit and promote` to reconcile rationales.

## See also

- `skills/harvest-author-rules/SKILL.md` — the user-facing skill workflow.
- `skills/promote-rule/SKILL.md` — single-phrase promotion variant.
- `tools/author/rule_harvester.py` — pure classification + dedup layer.
- `tools/author/discovery_writer.py` — write-side: profile.md + book CLAUDE.md cleanup.
- `templates/author-profile.md` — the `## Writing Discoveries` scaffold.
