---
book_category: fiction
status: scaffold
last_reviewed: 2026-04-27
---

# Fiction — Status Model

This file mirrors `book_categories/memoir/status-model.md` for symmetry. The
**canonical** definition of the fiction status progression lives in `CLAUDE.md`
under "Status Progressions" — that is the source of truth for ranks, aliases,
auto-sync rules, and the forward-only floor.

## Book status progression

```
Idea → Concept → Research → Plot Outlined → Characters Created →
World Built → Drafting → Revision → Editing → Proofread → Export Ready → Published
```

## Auto-derivation (Issue #21)

The indexer derives an effective book status from chapter aggregates. It only
ever escalates forward — never moves backward.

| Book tier | Trigger |
|-----------|---------|
| `Drafting` | any chapter past `Outline` |
| `Revision` | every chapter at Revision rank or higher (incl. alias `review`) |
| `Proofread` | every chapter `Final` |

`Editing`, `Export Ready`, and `Published` remain **explicit** — they require
qualitative judgment beyond chapter-state aggregation.

## Auto-sync to disk (Issue #25)

`rebuild_state()` writes the derived status back to README frontmatter when
it's a forward move from the on-disk value. Floor rule: a user-set higher
tier (`Export Ready`, `Published`) is never silently downgraded.

## Chapter-status aliases

| Alias | Canonical rank |
|-------|----------------|
| `review`, `reviewed` | Revision |
| `drafting` | Draft |
| `polishing` | Polished |
| `done` | Final |

## See also

- `CLAUDE.md` — canonical, authoritative version
- `book_categories/memoir/status-model.md` — memoir-specific stage interpretations and quality gates
