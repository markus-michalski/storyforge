# ADR-0001: Data Briefs Over Prompt Instructions

**Status:** Accepted  
**Date:** 2026-04-27  
**Deciders:** Markus Michalski (BDFL)  
**Related:** Epic #69 (Writing-quality hardening), Sprint 2 #78

---

## Context

StoryForge skills contain a large number of natural-language instructions of the form "please load X", "please honor Y", "please check Z". Under normal context load these instructions are followed. Under heavy context pressure — deep prereq stacks, long chapter drafts, session state from 22 prior chapters — the model deprioritizes self-check in favor of output. Instructions become soft; data does not.

Concrete failure modes observed in *Blood & Binary: Firelight*:

- Timeline drift: `chapter-writer` did its own date math and lost the anchor under prereq load (9-day error)
- Per-scene tic overuse: per-chapter limits in the prompt did not prevent 5 hits of `"the way"` in a single 900-word scene
- Meta-narrative leakage: reviewer vocabulary in the prose itself
- POV knowledge boundary breaks: IT-guy narrating forensic blood-smell detail
- Tactical implausibility: walking-order errors that a pre-write check would have caught

Root cause in all cases: the rule lived only in the skill prompt, not in tool output.

## Decision

**Where a skill needs facts about the current state of the project, those facts must be served by an MCP tool as structured JSON, not described as instructions in the skill prompt.**

Skill prompts reduce to: *"Call `get_X_brief()`. Honor every field."*

## Principle in Detail

### What counts as data

Anything the model must treat as ground truth rather than advice:

- Anything stored in the project filesystem: timeline, characters, callbacks, world/setting
- Anything computable from project state: story date anchor, recent simile counts, satisfied callbacks
- Anything user-configured: banned words, severity tiers, per-book linter config

If it can be expressed as a key-value pair or list in JSON, it is data.

### What stays as instruction

Craft guidance — *how* to write a good scene — stays in skill prompts and `reference/craft/` documents. These are advice for the model's reasoning, not facts about the project state.

Examples of legitimate prompt instructions:

- How to balance showing vs. telling
- How to handle a difficult emotional beat
- How to structure a scene-sequel unit
- How to differentiate dialog voices

A practical test: **if removing the instruction would cause a factual error, it is data and belongs in an MCP tool. If removing it would only reduce craft quality, it is instruction and belongs in the prompt.**

### The brief pattern

```
MCP tool: get_X_brief(book_slug, ...) → JSON

{
  "story_anchor": { "date": "2026-12-25", "day_of_week": "Thursday" },
  "banned_phrases": ["clocked", "the way", "pulsed with energy"],
  "callbacks_due": [{ "id": "cb-14", "description": "...", "status": "open" }],
  "tactical_constraints": [{ "severity": "warn", "message": "..." }],
  "errors": ["get_recent_chapter_timelines: book has no chapters yet"]
}
```

The model treats every populated field as non-negotiable. Empty fields and `errors` entries signal graceful degradation, not failure.

## Consequences

### Positive

- Invariants that matter (dates, banned phrases, walking order) are never deprioritized under context pressure
- Rules are testable: a unit test can assert that a brief contains the correct anchor, not that a prompt "mentions" the date
- Rules are traceable: each entry in a JSON brief has a source (book CLAUDE.md, author vocabulary.md, global anti-ai-patterns.md)
- Adding a new rule requires only a data change, not a skill-prompt edit

### Negative

- More MCP tools to build and maintain
- Skills that currently work via prompt instructions need refactoring (migration cost)
- `get_X_brief()` tools become load-bearing; a bug there affects every write

## Compliance status as of 2026-04-27

| Skill | Compliance | Notes |
|---|---|---|
| `chapter-writer` | **Full** | Uses `get_chapter_writing_brief()` — the reference implementation. Bundles 12 context sources into one structured payload. |
| `chapter-reviewer` | **Partial** | Loads author + craft via MCP but reads `plot/timeline.md`, `world/setting.md`, `plot/canon-log.md` directly. No structured review brief. Follow-up: #99 |
| `continuity-checker` | **Partial** | Uses `get_recent_chapter_timelines()` but reads timeline.md and setting.md directly. No brief. Follow-up: #100 |

MCP tools that serve briefs:

- `get_chapter_writing_brief(book_slug, chapter_slug)` — chapter-writer's prereq bundle
- `get_current_story_anchor(book_slug)` — canonical date anchor (#72)
- `get_recent_chapter_timelines(book_slug, n)` — intra-day grids (#77)
- `verify_tactical_setup(book_slug, scene_outline, characters)` — combat/travel pre-check (#75)
- `get_book_claudemd(book_slug)` — raw CLAUDE.md (partial; needs brief wrapper)

New entries are added here as tools are built.

## Migration guide

For an existing skill that uses prompt instructions to describe data:

1. **Identify data references in the skill prompt.** Look for: "load X", "honor Y", "check that Z", "use the current date from".
2. **Classify:** is this data (ground truth) or craft (advice)?
3. **For data:** expose it via an MCP tool. Either add a field to an existing brief or create a new `get_X_brief()`.
4. **Reduce the skill prompt** to: "Call `get_X_brief()`. Honor every populated field."
5. **Write a test** that asserts the brief returns the field with the expected value for a known book state.
6. **Remove the prompt instruction.** If removing it breaks something, the data is not correctly served yet.

The final skill prompt for a data-heavy operation should be short. If it is longer than 50 lines of instructions (not workflow steps), it probably contains prompt instructions that should be data.

## Future-skill template

New skills that need project-state data must follow this structure:

```markdown
## Prerequisites

Call `get_X_brief(book_slug)` before any work. Honor every populated field.
Degrade gracefully on empty fields and `errors` entries.
```

No "please load", "please check", or "please honor X" in new skill prompts. If the rule cannot be expressed as a JSON field, write it in `reference/craft/` and load it via `get_craft_reference()`.
