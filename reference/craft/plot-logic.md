---
book_categories: [fiction, memoir]
craft_topic: plot-logic
status: stable
last_reviewed: 2026-05-03
---

# Plot Logic: Cause, Knowledge, and the Things Stories Have to Keep Track Of

Story-logic gaps — the casual reader calls them "plotholes" — are the failure mode where the story breaks its own rules and the reader stops trusting it. Most plotholes aren't grand contradictions. They're small invisible cheats: a character who refers to a fact she hasn't been told yet; a decision that contradicts what we know the character wants; a magic rule established in chapter 3 that gets quietly broken in chapter 22; a gun on the mantel in chapter 1 that nobody ever fires.

This document defines six categories of plot-logic failure and how to recognize each one. The categories are deliberately narrow — broader concepts like "weak plot" or "sagging middle" belong in `plot-craft.md`. What follows is the *kind* of error a story-logic checker can actually find and an author can actually fix.

## What This Is Not

- **Not pacing.** A scene that drags is a craft problem, not a logic problem.
- **Not character likability.** A character making an unwise choice in service of theme is *not* a motivation break — it's a feature.
- **Not foreshadowing density.** Light foreshadowing is a style choice. A promise made and then broken is a logic break.
- **Not genre convention.** Vampires sparkling, FTL travel, magic rings — accepted premises, not violations. Violations are when the story changes its *own* premises mid-stream.

The test for a plothole is structural, not aesthetic: **does the story contradict something the story has already established?**

## The Six Categories

### 1. Information Leak

A POV character knows something they couldn't possibly know yet. Either the fact hasn't been revealed in the story, or the character wasn't present when it was revealed, or the character was present but the fact was hidden from them specifically.

**Failing:**
> Liam knew Theo's father was already dead.
> *— Chapter 12, draft.md*
>
> Theo opened the letter and read it twice before he understood what it said. His father, three weeks ago, in his sleep.
> *— Chapter 14, draft.md*

Chapter 12 reveals to the *reader* that Liam knows. But the letter — the source of the information — isn't opened until chapter 14. Liam can't have the fact yet.

**The fix:** Move the realization later, or supply an earlier source (a phone call, a rumor, a witnessed scene that placed Liam in the right room at the right time).

**Detection mechanic:** Build a per-character knowledge index from the canon log + timeline. For every named fact, the index records *at which story-day the fact was established* and *which characters were present in scenes where the fact surfaced*. Then scan POV prose for references to facts whose `established_in` is later than the current chapter, or whose source-scene didn't include the POV character.

**Limitation — the 95% rule:** "Character was present in chapter X" does not strictly mean the character heard or understood the fact. Char might have been asleep, distracted, in another room of the same scene. The detector therefore raises *information_leak* findings as **WARN by default**, escalating to **FAIL** only when the POV character was demonstrably absent from every scene where the fact surfaced.

### 2. Motivation Break

A character makes a decision that contradicts what the story has established about their wants, knowledge, or values — and the story doesn't acknowledge or explain the contradiction.

**Failing:**
> *Chapter 4:* Marcus tells Sarah he will never set foot in his father's house again. Not for any reason. The line lands hard; Sarah believes him.
>
> *Chapter 18:* Marcus drives to his father's house to retrieve a notebook. No interior dialog about breaking his vow. No new pressure that overrides it. He just goes.

The story established a hard line in chapter 4. Chapter 18 crosses it without paying any cost.

**The fix:** Either escalate the pressure visibly ("she's missing — that overrides every other rule"), or rewrite chapter 4 to be a softer commitment, or have Marcus refuse and someone else go.

**Detection mechanic:** Hard to automate. The detector flags candidate breaks by cross-referencing established character wants/values (from the canon log "Character Facts" section) with later decisions in prose. Most findings need human verification — pure pattern-matching can't tell the difference between "violated commitment" and "evolving character arc". Findings ship as **WARN**.

### 3. Premise Violation

A world-rule or magic-rule established in an earlier chapter gets quietly broken in a later one. Distinct from *motivation break* (which is about people) — this is about the laws of the story's universe.

**Failing:**
> *Chapter 3:* "Bound spirits cannot cross running water. That's the first thing every binder learns."
>
> *Chapter 21:* The bound spirit pursues Ada across the river without comment.

The reader who paid attention in chapter 3 will notice. The reader who didn't will sense the story's logic has gone soft.

**The fix:** Either honor the rule (the spirit stops at the riverbank, forcing Ada to confront it differently), or revise chapter 3 to give the rule an exception that chapter 21 invokes.

**Detection mechanic:** The detector pulls premise statements from the canon log "World / Setting Facts" section and from `world/rules.md`. It looks for negation patterns ("cannot X", "never Y", "always must Z") and then scans later prose for X, Y, Z without an exception clause. Findings ship as **high severity / FAIL** — premise violations break reader trust faster than any other category.

**Memoir note:** Premise violations are a fiction-only concept. Memoir doesn't invent rules; the world is whatever the world was. The detector skips this category for `book_category: memoir`.

### 4. Chekhov's Gun (Unfired Promise)

The story prominently introduces a setup element — a clue, a weapon, a skill, a relationship — and then the element is never returned to. The reader's expectation is honored by the introduction; the absence of payoff feels like a forgotten thread.

**Not every detail is a Chekhov's gun.** Texture, voice, world-building — those aren't promises. A Chekhov's gun is a prominently-introduced element that *shapes the reader's expectation of what's coming*: the locked drawer no one opens, the mentor's cryptic warning that never lands, the protagonist's claim that she can shoot a rifle that never gets tested.

StoryForge's mechanism: each chapter's `README.md` carries an optional `## Promises` section listing setup-elements placed in that chapter, with target chapters for payoff. The detector checks that every promise either (a) appears in a later chapter's draft, or (b) has been explicitly retired (revision deletes the section, or moves the promise to a `## Retired Promises` block).

**Detection mechanic:**
- *Dropped promise* — promise listed, target chapter has been drafted, no reference found → **high severity**
- *Deferred promise* — promise listed, more than 10 chapters silent, target not yet reached → **medium severity**
- *Unfired promise at book-end* — promise listed, all chapters at Final, never referenced → **high severity**

**Memoir note:** Memoir is plotted by life, not by setup-payoff structure. The detector skips this category for `book_category: memoir`. Memoir books with deliberately Chekhov-shaped framing (rare) can opt back in via book-level config — out of scope for the first release.

### 5. Causality Inversion

A character reacts to an event before the event has happened, in story-time. The most embarrassing plothole, because it's nearly always a copy-paste error from revision and almost always catchable mechanically.

**Failing:**
> *Chapter 7 (story-day 3):* "She'd been thinking about Thomas's confession all morning."
>
> *Chapter 9 (story-day 5):* Thomas confesses for the first time.

Chapter 7 is two days earlier in story-time. The thought cannot exist yet.

**The fix:** Either move the reaction to a chapter after the event, or remove it, or insert an earlier source for the foreknowledge (a dream, a guess, an earlier rumor).

**Detection mechanic:** The detector parses every chapter's `## Chapter Timeline` story-day anchor (already standardized — see Rule #16 of book CLAUDE.md). For every reference in prose to a named event in the canon log, it compares the chapter's story-day to the event's `established_in` story-day. If chapter precedes event, finding raises as **high severity / FAIL**.

This is the most reliably detectable category. The detector should be aggressive here.

### 6. POV Knowledge Boundary

Distinct from #1: the POV character knows something they *could* have heard, but the *narration attributes domain knowledge* to the POV that the character's profile says they don't have. Closer to a craft problem than a logic problem, but it lives on the same continuum — the narration has handed the POV character expertise the character doesn't own.

**Failing (POV is Sarah, profile says `knowledge.none: [forensics, ballistics]`):**
> She studied the entry wound. Nine-millimeter, fired from below at no more than three meters, judging by the powder burns.

Sarah is a school librarian. She doesn't know any of this. The narration has stolen the line from a forensic technician.

**The fix:** Either let Sarah notice what she would notice ("a small dark hole rimmed with something that looked like soot"), or move the analysis to a character who has the domain.

**Detection mechanic:** This is what `pov_boundary_checker.py` already does, using each character's `knowledge:` frontmatter (`expert | competent | layperson | none`) and the `reference/craft/knowledge-domains/` token catalog. The plot-logic check extends this with cross-chapter pattern: a character who suddenly demonstrates expertise at chapter 18 that the story never showed them acquiring should warn even if their profile is silent on the domain.

This category ships as **medium severity / WARN** — false-positive-prone, useful as a diagnostic flag for the reviewer to verify.

## The Knowledge Index — How the Detector Sees the Story

The plot-logic detector builds three index structures from existing data sources before it scans prose. None of these are new state — all of it is already in the book.

### Per-Character Knowledge Index

For each named character, what does the story know they know, and at which story-day?

| Source | What it provides |
|---|---|
| `plot/canon-log.md` "Established Facts" | Each fact's `established_in: "Ch X"` plus the inferred story-day from `plot/timeline.md` |
| `plot/timeline.md` `characters` field per row | Which characters were present in which chapter — candidate carriers of facts surfaced in that chapter |
| `characters/{slug}.md` `knowledge:` frontmatter | Domain expertise tiers — the floor for what the character could plausibly conclude on their own |

### Story-Day Index

For each chapter, the canonical story-day on which it occurs. Drives causality_inversion detection.

| Source | What it provides |
|---|---|
| `chapters/{NN-slug}/README.md` `## Chapter Timeline` section | Story-day anchor (Rule #16) |
| `plot/timeline.md` events | Reference points for foreshadowed-vs-not-yet-occurred checks |

### Promise Index

For each chapter, the setup-elements placed there with their target chapters.

| Source | What it provides |
|---|---|
| `chapters/{NN-slug}/README.md` `## Promises` section | Promise descriptions + `target_chapter` (or `[unfired]`) |

The `## Promises` section is populated either (a) automatically by `chapter-writer` at the Draft → Review transition (LLM extraction, persisted via `register_chapter_promises` MCP tool), or (b) by `/storyforge:backfill-promises` for books drafted before the feature shipped, or (c) hand-edited by the author. All three paths produce the same structure.

## Severity Mapping Summary

| Category | Default severity | Rationale |
|---|---|---|
| `causality_inversion` | high / FAIL | Mechanically detectable, almost always a real bug |
| `premise_violation` | high / FAIL | Breaks reader trust, fiction-only |
| `information_leak` | medium-high / WARN→FAIL | WARN when POV was present in source-scene; FAIL when demonstrably absent |
| `chekhov_gun` (dropped) | high / FAIL | Unkept promise, fiction-only |
| `chekhov_gun` (deferred) | medium / WARN | Tolerable for novels; flag for tracking |
| `motivation_break` | medium / WARN | Pattern-matched, needs human verification |
| `pov_knowledge_boundary` | medium / WARN | False-positive-prone, useful as diagnostic |

The aggregator (`run_quality_gates`) escalates any high finding to a FAIL gate. WARN findings flow through to the reviewer for triage but don't block the pre-export gate.

## Memoir Differences

Two of the six categories don't apply to memoir books. They're skipped automatically when `book_category == "memoir"`:

- `chekhov_gun` — memoir narrative arcs aren't built on setup/payoff structure
- `premise_violation` — memoir doesn't invent magic rules or world-rules to violate

The four remaining categories all apply: information leaks happen in memoir (the narrator-now using knowledge the narrator-then didn't have yet), motivation breaks happen in memoir (decisions that contradict the people-log), causality inversions happen in memoir (memory misordering events), and POV knowledge boundary happens any time the narrator attributes expertise the past-self didn't have.

For memoir, `information_leak` has an additional flavor: the past-self narrator referencing a fact they only learned afterward, presented as if known in the moment. This is a craft choice when intentional ("I didn't know it then, but —"), a plothole when accidental.

## Repair Strategies

When the detector raises a finding, the author has four options, in order of preference:

1. **Move the dependent passage.** Reaction after event, knowledge after revelation, payoff after setup. Often the cleanest fix.
2. **Insert a source.** Add an earlier scene where the character could have learned the fact. Costs a paragraph or two; preserves the later passage.
3. **Revise the established fact.** Change chapter 3 so the rule has the exception chapter 21 needs. Risks downstream churn — every later reference may need re-checking.
4. **Cut the dependent passage.** Sometimes the foreshadowing wasn't earning its place anyway. Quickest fix; sometimes the right one.

Avoid the fifth option: leaving the contradiction in and hoping no reader notices. Readers notice. Reviewers notice. Beta-readers notice. The cost of the fix is always lower than the cost of the lost trust.

## Pre-Review Checklist

Before a chapter draft transitions Draft → Review, the chapter-writer skill runs a `## Promises` extraction pass. Before a manuscript transitions Drafting → Revision, the manuscript-checker skill runs the full plot-logic scan. Authors writing without those skills can run the gates manually:

- [ ] `analyze_plot_logic(book_slug, scope="chapter", chapter_slug=...)` clean for the chapter being closed
- [ ] No `causality_inversion` findings — if any exist, they are showstoppers
- [ ] No unresolved `premise_violation` findings (fiction)
- [ ] All `information_leak` WARNs reviewed manually
- [ ] `## Promises` section populated for the chapter (or `[no promises this chapter]` noted)
- [ ] `chekhov_gun` deferred-list reviewed at every revision pass (fiction)

## Related

- `plot-craft.md` — Plot structure, beats, and the larger architecture this builds on (fiction).
- `book_categories/memoir/craft/memoir-structure-types.md` — Memoir narrative arcs (memoir).
- `point-of-view.md` — POV discipline; the foundation for `pov_knowledge_boundary`.
- `chapter-construction.md` — Chapter-level promise/payoff at the local scale.
- `gate-contract.md` — How findings map to PASS/WARN/FAIL gate status.
