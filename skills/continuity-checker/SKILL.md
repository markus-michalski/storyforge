---
name: continuity-checker
description: |
  Scan all chapter drafts and validate against the story timeline, travel matrix (fiction),
  or people-log and real chronology (memoir).
  Use when: (1) User says "Continuity prüfen", "check continuity", "Zeitlinie prüfen",
  (2) After writing multiple chapters, (3) Before revision or export.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<book-slug>"
---

# Continuity Checker

## Step 0 — Resolve Book Category

Load `book_category` from MCP `get_book_full(book_slug)`. Treat missing as `fiction`.
Branch Prerequisites and Workflow Steps 3, 5, 6 on `book_category`.

## Purpose

**Fiction:** Scan for inconsistencies in invented chronology, Travel Matrix distances, and Canon Log facts.

**Memoir:** Scan for inconsistencies in real chronology, people-log facts, and real-world geography claims. No Travel Matrix exists — spatial claims are checked for real-world plausibility instead.

## Prerequisites

### Step 1 — Load the continuity brief (single MCP call)

Call MCP `get_continuity_brief(book_slug)`. This returns:

- `canonical_calendar` — parsed `plot/timeline.md` events (story_day/real_date/chapter_slug/key_events)
- `travel_matrix` — parsed `world/setting.md` Travel Matrix rows (**fiction only** — empty for memoir)
- `canon_log_facts` — parsed `plot/canon-log.md` facts (**fiction only** — empty for memoir)
- `character_index` — all character/people files as flat list (slug/name/role/description)
- `chapter_timelines` — intra-day timeline grids for ALL chapters
- `errors` — graceful degrade: non-empty means some files were missing or unreadable

Honor every populated field. Empty lists mean "file missing — degrade gracefully, do not invent."

**Memoir supplement:** If `book_category == "memoir"`, also directly read `{project}/plot/people-log.md` (analogue of canon-log for memoir). If it doesn't exist yet, note this in the report and proceed without it.

### Step 2 — Load book metadata

- Load book data via MCP `get_book_full()`

### Step 3 — Read the chapter drafts (direct file reads)

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

### Step 3: Validate Against Travel Matrix / Real-World Geography

Branch by `book_category`:

**Fiction — Validate Against Travel Matrix:**
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

**Memoir — Real-World Plausibility Check:**
No Travel Matrix exists for memoir. For each spatial claim with a stated travel time or distance:
1. Use common-sense real-world geography (or WebSearch for specific routes if needed)
2. Flag claims that are implausible (e.g., "the 10-minute walk to school" — if research shows the distance is 3km)
3. Do NOT construct or propose a Travel Matrix for memoir

Flag as **WARNING** if:
- A stated travel time seems implausible for the described distance/mode of transport
- A location's described size or layout contradicts what is known about the real place

### Step 4: Rebuild Timeline (if missing or incomplete)

If `plot/timeline.md` is empty or incomplete:
1. Build a proposed timeline from chapter evidence
2. Identify the most internally consistent interpretation
3. Write the proposed timeline to `plot/timeline.md`
4. Mark all entries as `[RECONSTRUCTED]` so the author can verify

**Memoir note:** Memoir timelines use real dates. If chapters reference verifiable public events (news, seasons, school years), use those as anchors for the reconstructed timeline.

### Step 5: Rebuild Travel Matrix (fiction only)

**Skip entirely for memoir.**

If Travel Matrix in `world/setting.md` is empty or has gaps (fiction only):
1. Collect all travel references from chapters
2. Build a proposed Travel Matrix (most frequently mentioned values win)
3. Note conflicts in the matrix
4. Add proposed entries with `[RECONSTRUCTED]` marker

### Step 6: Validate Fact Consistency

Branch by `book_category`:

**Fiction — Canon Log:**

If `plot/canon-log.md` exists:
1. For each fact marked `CHANGED`, scan all chapters AFTER the revision for references to the OLD version
2. For each fact marked `ACTIVE`, verify it isn't contradicted in any chapter

If `plot/canon-log.md` is empty or missing:
1. Extract key facts from each chapter (character traits, abilities, relationships, rules)
2. Build a proposed Canon Log organized by domain (Character, Relationship, World, Plot)
3. Identify contradictions between chapters
4. Write to `{project}/plot/canon-log.md` with `[RECONSTRUCTED]` markers

Fact categories: character abilities/limitations, descriptions, relationship status, world rules, object ownership.

**Memoir — People Log:**

If `{project}/plot/people-log.md` exists:
1. For each entry, verify that all chapters referencing that person are consistent with what the log records (what they did, said, believed in each chapter)
2. Flag any chapter that contradicts an established people-log entry

If `people-log.md` is missing:
1. Extract key facts about named people from each chapter (descriptions, behaviors, quotes attributed to them, relationship status)
2. Build a proposed People Log organized by person
3. Identify contradictions between chapters (e.g., Ch 3 says "she never spoke about the accident" but Ch 7 has her describing it)
4. Write to `{project}/plot/people-log.md` with `[RECONSTRUCTED]` markers

People-log fact categories: physical description, relationship to author, what they said/did/believed in each chapter, consent_status if known.

Flag as **FACT CONFLICT** if:
- Two chapters make contradictory claims about the same person or fact
- A chapter contradicts an established people-log entry

### Step 7: Output Report

Fiction report includes Travel Matrix section. Memoir replaces it with Real-World Plausibility and uses People Log instead of Canon Log.

```markdown
# Continuity Check Report — {Book Title}
Generated: {date}
Book category: {fiction | memoir}

## Summary
- Chapters scanned: X
- Timeline entries: X
- [Fiction] Travel Matrix routes: X | [Memoir] Spatial plausibility checks: X
- [Fiction] Canon facts tracked: X | [Memoir] People-log entries: X
- CONFLICTS: X (temporal: X, spatial: X, fact: X)
- WARNINGS: X

VERDICT: PASS | WARN | FAIL

Verdict mapping (per the gate contract — see `reference/gate-contract.md`):
- PASS — zero CONFLICTS and zero WARNINGS.
- WARN — WARNINGS only (ambiguous time markers, missing matrix entries, minor people-log gaps).
- FAIL — at least one CONFLICT, OR any chapter contradicts a `consent_status: refused` person.

---

## Temporal Conflicts

### CONFLICT: Chapter 3 vs Chapter 7
**Chapter 3:** "He arrived back on Monday after five days at the campground"
**Chapter 7:** "It had been a Tuesday when he left, and he'd stayed through the weekend"
**Analysis:** If he left Tuesday and stayed 5 days → returns Sunday. Chapter 3 says Monday.
**Suggested fix:** Change Chapter 3 "Monday" to "Sunday", or adjust Chapter 7 departure day.

---

## [Fiction] Spatial Conflicts — Travel Matrix

### CONFLICT: Chapter 5 vs Travel Matrix
**Chapter 5:** "The city was only 12 km away, and the drive took 40 minutes"
**Travel Matrix:** City → Campground = 120 km / 2h 30min
**Suggested fix:** Update Chapter 5 or Travel Matrix for consistency.

## [Memoir] Spatial Plausibility

### WARNING: Chapter 5 — implausible travel time
**Chapter 5:** "the 10-minute walk to school"
**Real-world assessment:** ~3km distance = approx 35-40 minutes on foot.
**Suggested fix:** Revise the stated duration or distance.

---

## [Fiction] Fact Conflicts — Canon Log / [Memoir] Fact Conflicts — People Log

### CONFLICT: Chapter 4 vs Chapter 8
**[Fiction] Canon Log / [Memoir] People Log:** [established fact]
**Chapter 8:** [contradicting text]
**Suggested fix:** [options]

---

## Warnings (verify manually)
- Chapter 4: "a few days later" — ambiguous, not reflected in timeline.md
- [Fiction] Chapter 9: travel route "downtown → warehouse" not in Travel Matrix

---

## Reconstructed Timeline
*(Only shown if timeline.md was empty/incomplete)*
...
```

### Step 8: Save Report

Write report to `{project}/research/continuity-report.md`.

Suggest: Fix conflicts manually or ask chapter-reviewer to address specific chapters.

### Step 9: Update Fact Log

**Fiction:** If the Canon Log was reconstructed or new facts were discovered:
1. Save to `{project}/plot/canon-log.md`
2. Populate the Revision Impact Tracker with chapters that need attention
3. Report to the user which chapters are flagged as `[STALE]`

**Memoir:** If the People Log was reconstructed or new facts were discovered:
1. Save to `{project}/plot/people-log.md`
2. Flag chapters that contradict the log as `[STALE]`
3. If any person with `consent_status: refused` appears in a chapter — flag as CRITICAL, route to `/storyforge:memoir-ethics-checker`

## Rules
- Report ALL conflicts, even minor ones. The author decides what to fix.
- Never silently correct chapter drafts — always report and let the author decide.
- If two chapters conflict, don't assume one is right — present both and let the author choose.
- A reconstructed timeline is a proposal, not canon. Mark it clearly.
- Focus on facts extractable from text — don't make assumptions about intent.
