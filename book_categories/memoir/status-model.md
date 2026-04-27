---
book_category: memoir
status: scaffold
last_reviewed: 2026-04-27
---

# Memoir — Status Model

Memoir uses the **same status sequence** as fiction (defined in `CLAUDE.md`
under "Status Progressions"). The progression strings, ranks, and auto-sync
behavior (Issues #19, #21, #25) are unchanged.

What differs is the **meaning** of each stage when the book's `book_category`
is `memoir`. Skills branching on category in Phase 2+ will use these
interpretations to drive different prompts, checks, and quality gates.

## Stage interpretations

| Status | Fiction meaning | Memoir meaning |
|--------|-----------------|----------------|
| `Idea` | A premise / what-if hook | A piece of life worth examining (theme, period, relationship) |
| `Concept` | Premise + logline + comp titles | Theme + central question + intended angle on the material |
| `Research` | World-building research, source material | Factual research: dates, places, public record, fact-checking |
| `Plot Outlined` | Acts, beats, scenes invented | **Narrative arc identified** — the shape imposed on lived events |
| `Characters Created` | Invented characters with arcs | **People profiles drafted**, with consent + anonymization decisions |
| `World Built` | Setting, magic, rules invented | Setting + era documented (usually researched, not invented) |
| `Drafting` | Same — chapters being written | Same |
| `Revision` | Same — structural and prose passes | Same, plus emotional-truth pass and consent re-check |
| `Editing` | Same | Same |
| `Proofread` | Same | Same |
| `Export Ready` | Same | Same |
| `Published` | Same | Same |

## Memoir-specific quality gates

These are **not** new statuses — they are checklists that gate transitions
between existing statuses. Phase 3 skills (#65 `memoir-ethics-checker`, #66
`emotional-truth-prompt`) will enforce them.

### Before `Plot Outlined → Characters Created`

- [ ] Theme is explicit and falsifiable (not "growing up was hard")
- [ ] Central question is named (the one the memoir is trying to answer)
- [ ] Structure type chosen (chronological / thematic / braided / vignette)

### Before `Characters Created → World Built`

- [ ] Every named real person in `characters/` has a consent status:
  `confirmed-consent` / `pending` / `anonymized` / `composite` / `public-figure`
- [ ] Anonymized people have a documented anonymization strategy
- [ ] Composite characters (multiple real people merged) are flagged in author's note plan

### Before `Drafting → Revision`

- [ ] No factual claim about a living named person without source or consent
- [ ] Emotional-truth pass complete (the felt sense, not just the events)
- [ ] Memoir-anti-ai patterns checked (hedging, tidy lessons, reflective platitudes)

### Before `Revision → Editing`

- [ ] Real-people-ethics review complete
- [ ] Defamation risk scan (#65 will automate)
- [ ] Author's note drafted (anonymization, composite, time-compression disclosures)

## Auto-sync behavior

Auto-sync rules (Issue #25) are **unchanged** for memoir. The forward-only
floor still applies — a user-set higher tier (`Export Ready`, `Published`)
is never silently downgraded by chapter-state aggregates.

## Open questions (for Phase 2/3)

- Should memoir add a sub-state `Consent Verified` between `Characters Created`
  and `World Built`? Decision deferred to #65 implementation.
- Should `world/` be renamed to `setting/` for memoir projects, or kept aliased
  like #17 did for `worldbuilding/`? Decision deferred to #59 implementation.

## See also

- `book_categories/memoir/README.md` — overview
- `CLAUDE.md` — canonical fiction status model + auto-sync semantics
- `book_categories/memoir/craft/real-people-ethics.md` — consent + defamation patterns (Phase 1.6)
