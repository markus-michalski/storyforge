---
name: continuity-checker
description: |
  Scan all chapter drafts and validate against the story timeline and travel matrix.
  Reports temporal and spatial inconsistencies with chapter references.
  Use when: (1) User says "Continuity prüfen", "check continuity", "Zeitlinie prüfen",
  (2) After writing multiple chapters, (3) Before revision or export.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<book-slug>"
---

# Continuity Checker

## Purpose
Systematically scan all chapter drafts for inconsistencies in:
1. **Temporal continuity** — days, dates, durations, day-of-week claims
2. **Spatial continuity** — distances, travel times, location descriptions

## Prerequisites

### Step 1 — Load the continuity brief (single MCP call, replaces 4+ direct file reads)

Call MCP `get_continuity_brief(book_slug)`. This returns:

- `canonical_calendar` — parsed `plot/timeline.md` events (story_day/real_date/chapter_slug/key_events)
- `travel_matrix` — parsed `world/setting.md` Travel Matrix rows (from/to/distance/transport/travel_time/notes)
- `canon_log_facts` — parsed `plot/canon-log.md` facts with status (ACTIVE / CHANGED / SUPERSEDED) and domain
- `character_index` — all character files as flat list (slug/name/role/description)
- `chapter_timelines` — intra-day timeline grids for ALL chapters (any status); use these as the source of truth for chapter start/end anchors and scene-level clock times instead of re-parsing each `README.md`
- `errors` — graceful degrade: non-empty means some files were missing or unreadable

Honor every populated field in the brief. Empty lists mean "file missing — degrade gracefully, do not invent."

### Step 2 — Load book metadata

- Load book data via MCP `get_book_full()`

### Step 3 — Read the chapter drafts (direct file reads — this is the content under review)

Chapter draft texts are intentionally NOT in the brief — they are the data being checked, not project-state metadata.

- Read ALL chapter drafts: `{project}/chapters/*/draft.md`

## Workflow

### Step 1: Build Extraction Lists

Scan each chapter draft for:

**Temporal claims** — extract every mention of:
- Specific days ("Monday", "on Friday", "next Tuesday")
- Relative time ("three days later", "the next morning", "five days")
- Durations ("he stayed for a week", "two hours passed")
- Time of day tied to events ("that evening", "early Sunday morning")

**Spatial claims** — extract every mention of:
- Travel times ("it took two hours", "a 40-minute drive")
- Distances ("only 12 km", "across town")
- Location descriptions that imply distance ("nearby", "far away", "just around the corner")

Format extraction as:

```
Chapter 3, Para 2: "He arrived on Monday after five days away"
→ Temporal: arrived Monday, was gone 5 days
→ Implies: left Wednesday (Monday - 5 days)
```

### Step 2: Validate Against Timeline

For each temporal claim:
1. Look up the chapter's position in `plot/timeline.md`
2. Calculate what day/date the claim implies
3. Check if this matches the established timeline

Flag as **CONFLICT** if:
- A stated day-of-week doesn't match the calculated date
- A duration implies an impossible arrival/departure date
- Two chapters claim different days for the same event

Flag as **WARNING** if:
- The timeline doesn't have an entry for this chapter yet
- A relative time reference is ambiguous

### Step 3: Validate Against Travel Matrix

For each spatial claim:
1. Identify the route (From → To)
2. Look up the route in `world/setting.md` Travel Matrix
3. Compare stated time/distance with canonical values

Flag as **CONFLICT** if:
- Stated travel time differs by more than 30% from Travel Matrix value
- Stated distance contradicts Travel Matrix distance
- Route doesn't exist in Travel Matrix (unknown route)

Flag as **INFO** if:
- Route exists but travel time varies within 30% (traffic, weather — acceptable)

### Step 4: Rebuild Timeline (if missing or incomplete)

If `plot/timeline.md` is empty or incomplete:
1. Build a proposed timeline from chapter evidence
2. Identify the most internally consistent interpretation
3. Write the proposed timeline to `plot/timeline.md`
4. Mark all entries as `[RECONSTRUCTED]` so the author can verify

### Step 5: Rebuild Travel Matrix (if missing or incomplete)

If Travel Matrix in `world/setting.md` is empty or has gaps:
1. Collect all travel references from chapters
2. Build a proposed Travel Matrix (most frequently mentioned values win)
3. Note conflicts in the matrix
4. Add proposed entries with `[RECONSTRUCTED]` marker

### Step 6: Validate Fact Consistency (Canon Log)

**If `plot/canon-log.md` exists:**
1. For each fact marked `CHANGED`, scan all chapters AFTER the revision for references to the OLD version
2. For each fact marked `ACTIVE`, verify it isn't contradicted in any chapter

**If `plot/canon-log.md` is empty or missing:**
1. Extract key facts from each chapter (character traits, abilities, relationships, rules)
2. Build a proposed Canon Log organized by domain (Character, Relationship, World, Plot)
3. Identify contradictions between chapters (e.g., Ch 4 says "eats normally" but Ch 8 says "doesn't eat")
4. Write the proposed Canon Log to `{project}/plot/canon-log.md` with `[RECONSTRUCTED]` markers

**Fact categories to extract:**
- Character abilities/limitations (e.g., "can/cannot eat", "has/doesn't have powers")
- Character descriptions (appearance, age, occupation)
- Relationship status (who knows whom, family ties)
- Rules of the world (how magic/supernatural elements work)
- Object ownership/possession (who has the key, where is the artifact)

Flag as **FACT CONFLICT** if:
- A chapter references the old version of a `CHANGED` fact
- Two chapters make contradictory claims about the same fact
- A character behaves inconsistently with established abilities/traits

### Step 7: Output Report

```markdown
# Continuity Check Report — {Book Title}
Generated: {date}

## Summary
- Chapters scanned: X
- Timeline entries: X
- Travel Matrix routes: X
- Canon facts tracked: X
- CONFLICTS: X (temporal: X, spatial: X, fact: X)
- WARNINGS: X

---

## Temporal Conflicts

### CONFLICT: Chapter 3 vs Chapter 7
**Chapter 3:** "He arrived back on Monday after five days at the campground"
**Chapter 7:** "It had been a Tuesday when he left, and he'd stayed through the weekend"
**Analysis:** If he left Tuesday and stayed 5 days → returns Sunday. Chapter 3 says Monday.
**Suggested fix:** Change Chapter 3 "Monday" to "Sunday", or adjust Chapter 7 departure day.

---

## Spatial Conflicts

### CONFLICT: Chapter 5 vs Travel Matrix
**Chapter 5:** "The city was only 12 km away, and the drive took 40 minutes"
**Travel Matrix:** City → Campground = 120 km / 2h 30min
**Analysis:** 12 km at normal speed = ~10 minutes, not 40. 40 minutes ≈ 40 km. Neither matches.
**Suggested fix:** Update Chapter 5 to "120 km / 2.5 hours" or update Travel Matrix if 12 km is correct.

---

## Fact Conflicts

### CONFLICT: Chapter 4 (revised) vs Chapter 8
**Canon Log:** "Marcus eats normal food" (CHANGED in Ch 4 revision, was: "Marcus doesn't eat")
**Chapter 8:** "You don't eat, remember?" — Lena said, pushing her plate aside.
**Analysis:** Chapter 8 still references pre-revision fact. Marcus now eats normally per Ch 4.
**Suggested fix:** Rewrite Ch 8 dialog to reflect that Marcus eats.

---

## Warnings (verify manually)

- Chapter 4: "a few days later" — ambiguous, not reflected in timeline.md
- Chapter 9: travel route "downtown → warehouse" not in Travel Matrix

---

## Reconstructed Timeline

*(Only shown if timeline.md was empty/incomplete)*
...
```

### Step 8: Save Report

Write report to `{project}/research/continuity-report.md`.

Suggest: Fix conflicts manually or ask chapter-reviewer to address specific chapters.

### Step 9: Update Canon Log

If the Canon Log was reconstructed or new facts were discovered:
1. Save the updated Canon Log to `{project}/plot/canon-log.md`
2. Populate the Revision Impact Tracker with chapters that need attention
3. Report to the user which chapters are flagged as `[STALE]`

## Rules
- Report ALL conflicts, even minor ones. The author decides what to fix.
- Never silently correct chapter drafts — always report and let the author decide.
- If two chapters conflict, don't assume one is right — present both and let the author choose.
- A reconstructed timeline is a proposal, not canon. Mark it clearly.
- Focus on facts extractable from text — don't make assumptions about intent.
