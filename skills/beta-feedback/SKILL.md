---
name: beta-feedback
description: |
  Process curated beta-reader feedback — triage, cross-reference, revision plan.
  Use when: (1) User says "beta feedback", "ARC feedback", "reader feedback", "Beta-Feedback verarbeiten",
  (2) Book is in eBook/revision stage with beta-reader responses collected.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> [--file path/to/feedback.md]"
---

# Beta Feedback Processor

## Purpose

Process curated beta-reader feedback through structured triage:
1. Parse the author's pre-filtered feedback file
2. Categorize each item by domain
3. Cross-reference against the book's canon, timeline, tone, and arcs
4. Deliver a verdict per item (with evidence when disagreeing)
5. Produce a prioritized revision plan
6. Optionally execute revisions via chapter-writer

Beta-reader feedback is qualitatively different from inline review comments:
- It covers the **entire manuscript**, not single scenes
- It addresses cross-chapter concerns: pacing, character consistency, plot holes, genre expectations
- It comes from readers who don't know the author's intent, foreshadowing strategy, or world rules
- It requires **stronger verification** before acting on it

## Prerequisites

1. Resolve book slug from argument or session via MCP `get_session()`
2. Load book data via MCP `get_book_full(slug)`
3. Resolve book path via MCP `resolve_path(slug, "book")`
4. Load per-book CLAUDE.md via MCP `get_book_claudemd(slug)` — Rules, Callbacks, Workflow
5. Read the feedback file:
   - Default: `{project}/research/beta-feedback.md`
   - Custom: path from `--file` argument
6. Read cross-reference sources:
   - `{project}/plot/canon-log.md` — established facts, revision tracking
   - `{project}/plot/timeline.md` — canonical timeline
   - `{project}/plot/tone.md` — tonal rules, warning signs, litmus tests
   - `{project}/plot/arcs.md` — character arcs and motivation setup
7. Read chapter drafts as needed during cross-referencing: `{project}/chapters/{slug}/draft.md`

## Input Format

The author writes a curated Markdown file with one feedback item per section:

```markdown
# Beta Reader Feedback — {Book Title}

## FB-001: Pacing drags in Ch 18-19
Palace arrival feels slow. Two readers mentioned skimming.
Affected: Ch 18, Ch 19

## FB-002: Kael's motivation unclear after Ch 21
"Why does he suddenly forbid it? Felt out of character."
Affected: Ch 21, Ch 20 (setup)

## FB-003: Kevin scene was perfect
Multiple readers highlighted Ch 10 as a favorite. No action needed.
Affected: Ch 10
```

Format rules:
- `## FB-NNN: Title` — numbered for reference
- Free text body — the author's summary of the feedback point
- `Affected: Ch N [, Ch M, ...]` — which chapters are involved
- Items the author considers invalid should NOT be in the file (author pre-filters)

## Workflow

### Phase 1: Load and Parse

1. Load all prerequisites listed above
2. Parse the feedback file into structured items:
   - ID: `FB-NNN`
   - Title: text after the colon
   - Body: all text between the heading and the next heading or `Affected:` line
   - Affected chapters: parse `Affected: Ch N, Ch M` into chapter slugs
3. Validate: file must contain at least one `## FB-` section. If empty or malformed, report error and stop.
4. Report to user: "Loaded X feedback items affecting Y unique chapters."

**Wait for user acknowledgement before proceeding to Phase 2 (Categorize).** The user may want to add or remove items from the file first.

### Phase 2: Categorize

Tag each item with one or more categories based on its content:

| Category | Signals |
|----------|---------|
| `plot` | Story logic, cause/effect, missing setup/payoff, plot holes |
| `character` | Motivation, consistency, voice, arc progression |
| `pacing` | Too slow, too fast, scene length, chapter length, skimming |
| `prose` | Word choice, repetition, style, clarity |
| `continuity` | Timeline errors, spatial contradictions, canon violations |
| `genre-expectation` | Reader expected something the genre promises but didn't get |
| `positive` | Praise, highlight, no action needed |

Present categories to user before proceeding:

```
FB-001: Pacing drags in Ch 18-19 → pacing
FB-002: Kael's motivation unclear → character, plot
FB-003: Kevin scene was perfect → positive
```

**Wait for user confirmation of the category mapping before proceeding to Phase 3.** Miscategorization at this stage cascades into wrong cross-references in Phase 3.

### Phase 3: Cross-reference

For each **non-positive** item:

1. **Read the affected chapter draft(s)** — `{project}/chapters/{slug}/draft.md`
2. **Check against canon-log.md** — Is the reader pointing at something that's actually correct canon? Was there a revision that the reader's copy didn't include?
3. **Check against timeline.md** — Is there a real timeline issue, or is the reader miscounting days?
4. **Check against tone.md** — Is the pacing concern valid per the tonal arc for that chapter's position, or is the reader expecting the wrong genre mode? Check the Tonal Arc table, Warning Signs, and Non-Negotiable Rules.
5. **Check against arcs.md** — Is the character motivation actually set up (just subtly)? Is the reader missing foreshadowing?

Document evidence for each check. This evidence is critical for Phase 4 verdicts.

### Phase 4: Triage

Present each item with a verdict and supporting evidence:

| Verdict | Meaning |
|---------|---------|
| **valid + actionable** | Real problem, needs revision. Propose specific fix direction. |
| **valid + cosmetic** | Real but minor. Note for polish pass, not a structural rewrite. |
| **disagree** | Reader misread intent, or the "problem" is deliberate. Explain why with evidence from canon/tone/arc docs. |
| **positive** | Log it. No action. |

**Critical rule:** Apply the same verify-first discipline as inline author comments (Rule #14 from CLAUDE.md). Beta readers are LESS reliable than the author — they don't know the rules, the foreshadowing strategy, or the tonal arc. **Push back with evidence** when the feedback would damage the book.

For **disagree** verdicts, always provide:
- The specific passage the reader is reacting to (quote from draft)
- The evidence that it's intentional (quote from canon-log, arcs, tone, or per-book CLAUDE.md callbacks)
- Why changing it would hurt the book

Present the full triage table to the user. Wait for confirmation before proceeding to Phase 5.

### Phase 5: Revision Plan

For all items the user confirms as `valid + actionable`:

1. **Group by affected chapter** — one section per chapter, ordered by chapter number
2. **Propose concrete revision tasks** — what to change, why, which scene(s)
3. **Flag cascades** — if changing Ch 18 pacing affects Ch 19-20 setup, note it
4. **Flag conflicts** — if two feedback items suggest contradictory changes, surface it
5. **Prioritize** — Critical (structural/plot) before cosmetic (prose/pacing polish)

Output format:

```markdown
## Revision Plan

### Chapter 18: Palace Arrival
- **FB-001 (pacing):** Cut the hallway description from 3 paragraphs to 1. Move world-building details to dialog with the steward instead. Estimated: tighten by ~400 words.
  - CASCADE: Ch 19 opening references "the endless corridors" — update if hallway description changes.

### Chapter 21: The Prohibition
- **FB-002 (character):** Kael's prohibition needs a visible trigger in the scene. Add 2-3 lines showing what he sees/realizes that makes him act. Setup in Ch 20 is sufficient but the payoff moment is too abrupt.
```

### Phase 6: Execute (optional, user-triggered)

**Wait for explicit user approval before executing any revision.** This phase rewrites prose — auto-execution corrupts drafts.

For each approved revision task:
- **Prose/pacing fixes:** Use `/storyforge:chapter-writer` in rewrite mode for the affected scene
- **Continuity fixes:** Update `plot/canon-log.md` first, then rewrite the affected passage
- **Character fixes:** Re-read the character file and `plot/arcs.md`, assess if the arc doc needs updating, then rewrite
- **After all revisions:** Update `{project}/research/beta-feedback.md` with resolution status per item

Resolution status format — append to each `## FB-NNN` section:

```markdown
**Resolution:** [Fixed in revision | Cosmetic — deferred to polish | Disagreed — intentional]
**Revised:** [date]
**Chapters touched:** [list]
```

## Output Artifacts

### Triage Report: `{project}/research/beta-feedback-triage.md`

Generate using `templates/beta-feedback-triage.md` as scaffold.

## Integration with Existing Skills

| Skill | Connection |
|-------|-----------|
| `chapter-writer` | Rewrites triggered by actionable items (Phase 6) |
| `chapter-reviewer` | Post-rewrite quality gate |
| `manuscript-checker` | If prose feedback mentions repetitive patterns, clichés, or punctuation issues |
| `continuity-checker` | If feedback mentions timeline/spatial errors |
| `voice-checker` | If rewritten chapters need AI-tell verification |

## Rules
- Apply Rule #14 rigorously: beta readers are LESS reliable than the author. Verify every claim before accepting.
- Always present the triage and wait for user approval before executing any revision. Auto-execution is forbidden.
- Quote specific passages from the draft when providing evidence for verdicts.
- Quote specific entries from canon-log, arcs, tone, or callbacks when disagreeing with feedback.
- Positive feedback is worth logging — it tells the author what's working. Treat it as protected from revision changes.
- If multiple feedback items conflict with each other, surface the conflict explicitly and let the author decide.
- The author already pre-filtered the feedback. Respect that curation — only push back on the verdict (valid vs. disagree), not on inclusion.
- Track cascade effects rigorously. A change in one chapter that breaks another is worse than the original problem.
