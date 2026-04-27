---
book_category: fiction
status: scaffold
last_reviewed: 2026-04-27
---

# Fiction — Book Category

Fiction is the **default book category** in StoryForge. It is the implicit
category for every book whose `README.md` frontmatter has no
`book_category` field, and the explicit value `book_category: fiction` for
new books created since #54.

This file exists for **symmetry** with `book_categories/memoir/README.md`.
Most fiction-specific knowledge already lives in established places and is
**not duplicated here**:

| Topic | Canonical location |
|-------|--------------------|
| Skill routing for fiction workflows | `CLAUDE.md` (root) |
| Fiction craft references (18 docs) | `reference/craft/` |
| Genre-specific craft | `reference/genre/` and `genres/{name}/README.md` |
| Status progressions (Book / Chapter / Character) | `CLAUDE.md` "Status Progressions" |
| Project structure (plot/, characters/, world/, …) | `CLAUDE.md` "Project Structure" |
| Workflows (Outliner / Discovery / Plantser) | `CLAUDE.md` "Workflow Pipeline" |

## When to put something here

Add a file under `book_categories/fiction/` only if it is:

1. Specific to **fiction as a category**, not to a particular genre or skill
2. A meaningful **counterpart** to a memoir-specific decision (e.g., if memoir
   gets `craft/real-people-ethics.md`, fiction does **not** need
   `craft/invented-people-ethics.md` — that's just craft, not category-specific)

Most additions should go to `reference/craft/` instead, tagged with
`book_categories: [fiction]` frontmatter (added in #56).

## Status model

Fiction uses the canonical status progression documented in `CLAUDE.md`. See
`status-model.md` in this directory for a stable reference.

## See also

- `CLAUDE.md` — full skill routing, workflows, status progressions
- `book_categories/memoir/README.md` — the asymmetric companion (memoir has more category-specific knowledge because it diverges from the fiction-shaped defaults)
- `#54` — `book_category` field
- `#97` — Path E epic
