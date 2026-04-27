---
book_category: memoir
status: scaffold
last_reviewed: 2026-04-27
---

# Memoir — Book Category

Memoir is a **second-tier book category** in StoryForge alongside `fiction` (Path E in #49).
It activates when a book's `README.md` frontmatter carries `book_category: memoir`.

This file is the entry point for memoir-specific knowledge. Phase 2+ skills
load it (and the craft docs under `craft/`) when working on a memoir project.

## What memoir is — and is not

Memoir is a **personal narrative** focused on a specific period, theme, or
relationship in the author's own life. It is shaped from lived experience and
held to the standard of **emotional truth**, not invented plot.

Memoir is **not** autobiography (which aims for a complete life chronicle), and
it is **not** non-fiction in the broad sense (history, biography, how-to,
academic) — those subtypes are explicitly **out of scope** for v1 (see #49).

| Memoir | Autobiography | Fiction |
|--------|---------------|---------|
| Slice of life around a theme | Whole life, chronological | Invented narrative |
| Truth-shaped, scene-rendered | Comprehensive record | Plot-shaped, character-driven |
| Real people, with consent care | Real people, by default | Invented characters |
| ~50–80k words typical | ~80–150k words typical | Varies by `book_type` |

## Structure types

A memoir's structure is the **shape of the story being told** — independent of
the lived chronology. Pick one in `plot/outline.md` (or its memoir-equivalent)
during the conceptualization phase.

### Chronological

Events told in the order they happened. Simplest mental model. Risk: drifts
into autobiography if every year demands equal weight. Discipline: cut
sub-arcs that don't serve the central theme, even if they "really happened".

### Thematic

Chapters organized by topic (e.g., *Money / Faith / Bodies*) rather than
timeline. Same period of life can recur across chapters from different angles.
Strongest when the central question is conceptual, not temporal.

### Braided

Two or more parallel timelines or narrative threads interwoven (e.g., past
trauma + present-day reckoning). High craft demand — each thread must earn
its airtime, transitions must be deliberate. Cliché trap: lazy
"meanwhile-back-then" cuts.

### Vignette

Short, self-contained scenes (3–8 pages each), loosely connected by theme or
through-line rather than tight causal arc. Suits fragmented memory or
non-linear emotional landscapes. Risk: collapses into anecdote-collection
without a strong frame.

## Project structure differences

The fiction directory layout (`plot/`, `characters/`, `world/`) maps to memoir
with the same paths but **shifted meaning**:

| Fiction path | Memoir interpretation |
|--------------|----------------------|
| `characters/` | Real people who appear in the memoir. Consent + anonymization status tracked per person. |
| `plot/outline.md` | Narrative arc — the *angle* on the lived material, not invented events. |
| `plot/timeline.md` | Real chronology of events (memoir's "story bible"). |
| `world/setting.md` | Real places + eras (often requires factual research, not invention). |
| `world/rules.md` | Often empty for memoir (no magic system). May hold cultural/period rules instead. |

Phase 2 skill branches will rename or shadow some paths (`characters/` →
`people/` is under discussion in #59) — this README will be updated when those
land.

## Craft references

Memoir-specific craft docs live under `book_categories/memoir/craft/`:

- `memoir-structure-types.md` — chronological / thematic / braided / vignette (deeper than this overview)
- `scene-vs-summary.md` — when to dramatize, when to reflect
- `emotional-truth.md` — beyond facts, the felt sense
- `real-people-ethics.md` — consent, defamation, anonymization patterns
- `memoir-anti-ai-patterns.md` — hedging, "looking back I realize", reflective platitudes, tidy lessons

Existing fiction-craft docs in `reference/craft/` will be tagged with a
`book_categories: [fiction]` or `book_categories: [fiction, memoir]` frontmatter
in #56 so skills can filter what to load.

## Status progression

Memoir uses the same status sequence as fiction (Idea → Concept → … → Published)
but several stages carry **shifted intent** — see `status-model.md` in this
directory for the per-stage notes.

## Skill routing

CLAUDE.md will document memoir-specific skill routing in #67. Until that lands,
the existing fiction routing applies and skills do not yet branch on
`book_category`.

## See also

- `#54` — `book_category` field
- `#56` — memoir craft docs
- `#67` — CLAUDE.md routing table for memoir mode
- `#97` — Path E epic (full phase plan)
- `reference/research/non-fiction-integration.md` — decision rationale (gitignored)
