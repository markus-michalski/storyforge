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
- `travel_matrix` — parsed `world/setting.md` Travel Matrix rows (**fiction only** — empty for memoir, since memoir books have no `world/setting.md`)
- `canon_log_facts` — canon facts from the shared `canon_facts` DB table for this book (Issue #297/#280). **Not category-filtered by the brief itself** — for a memoir book this list may already be non-empty if facts were previously recorded (e.g. by this skill's own Step 6, or by `chapter-writer-memoir`). An empty list means no facts have been recorded yet for this book, not that the book is memoir — use the Memoir supplement below (`get_canon_brief`) for the authoritative category-scoped view.
- `character_index` — all character/people files as flat list (slug/name/role/description)
- `chapter_timelines` — intra-day timeline grids for ALL chapters
- `character_snapshots` — latest per-character state (injuries/clothing/inventory/altered_states) from the `character_snapshots` DB table (Issue #281), one entry per character that has ever had a snapshot recorded. May be empty if no skill has called `update_character_snapshot` for this book yet — treat as supplementary signal for Step 6, not a required source.
- `errors` — graceful degrade: non-empty means some files were missing or unreadable

Honor every populated field. Empty lists mean "file missing — degrade gracefully, do not invent." Each field degrades **independently** — an error or missing file recorded against one field (e.g. `world/setting.md` missing, surfaced in `errors`) does not block processing of any other, unrelated field (e.g. `canon_log_facts` or `chapter_timelines` are still used for their own checks even when a different section failed to load).

**Memoir supplement:** If `book_category == "memoir"`, call `get_canon_brief(book_slug, chapter_slug)` to get people facts from DB (Issue #297). If `extraction_method == "none"`, the DB has no facts yet — note this and advise running `scripts/migrate_canon_log_to_db.py` to import from `plot/people-log.md`.

Also call MCP `check_memoir_consent(book_slug)` — this is the **only** source for `consent_status` in this skill. `character_index` (from Step 1 above) is built from `characters/`, not `people/`, and carries no `consent_status` field regardless of category; `canon_log_facts` doesn't carry it either. `check_memoir_consent` reads every profile in `people/` directly and returns a `people` list with a per-person verdict (`PASS`/`WARN`/`FAIL`, where `FAIL` means `consent_status: refused`). Use its `FAIL`-verdict entries as the input to the Step 7/Step 9 refused-consent rule below.

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

**Fiction — Canon Facts:**

Use `canon_log_facts` from the brief (DB, Issue #297) — a **flat** list; each entry carries `status` (`"ACTIVE"` or `"CHANGED"`), `fact`, `subject`, `established_in` (e.g. `"Ch 4"`), `notes`, `domain`. There is no `changed_facts`/`current_facts` sub-split and no per-entry `revision_impact(s)` list on these entries (those belong to the differently-shaped, uncalled `get_canon_brief` tool — see the Memoir note below for why that tool isn't the data source here either):
1. For each entry with `status == "CHANGED"`, `notes` holds the OLD value being replaced — scan **every** chapter AFTER `established_in` for references to that old value. Read and check ALL later chapter drafts yourself; there is no impact list to shortcut this with, so a stale reference in any later chapter (however recently added) must be caught here.
2. For each entry with `status == "ACTIVE"`, verify it isn't contradicted in any chapter
3. Cross-check against `character_snapshots` from the brief (Issue #281), if any entries exist: flag a **FACT CONFLICT** if a chapter describes a character's injuries/clothing/inventory/altered_states in a way that contradicts their latest recorded snapshot with no intervening scene explaining the change.

If `canon_log_facts` is empty (no facts recorded yet for this book):
1. Extract key facts from each chapter (character traits, abilities, relationships, rules)
2. Build a proposed fact set organized by domain (Character, Relationship, World, Plot)
3. Identify contradictions between chapters
4. Insert facts into DB via `add_canon_fact(book_slug, chapter_num, subject, fact, domain=domain)` — `chapter_num` is the chapter's integer number (not its slug), with `[RECONSTRUCTED]` note in subject or fact

Fact categories: character abilities/limitations, descriptions, relationship status, world rules, object ownership.

**Memoir — People Facts:**

Use `canon_log_facts` from the Step 1 brief as the primary source — it is **not** windowed by chapter. `get_canon_brief` is shaped differently and only partially windowed: its `current_facts` key returns a bounded `scope_chapters`-sized window (default 8 chapters, ending *before* a single given chapter — designed for chapter-writer's narrower "what do I know so far" use case), but its `changed_facts` key returns all revision entries regardless of age. Neither key is the right source for a whole-manuscript scan — use `canon_log_facts` for both ACTIVE and CHANGED facts here. Only use the `get_canon_brief` call from Step 1's Memoir supplement for its `extraction_method` signal (DB empty or not) — don't re-fetch facts through it as the data source here, or chapters more than `scope_chapters` back will silently drop out of the check.
1. For each `canon_log_facts` entry, verify all chapters referencing that person are consistent
2. Flag any chapter that contradicts an established fact entry

If `extraction_method == "none"` (DB empty, from the Step 1 Memoir supplement's `get_canon_brief` call):
1. Extract key facts about named people from each chapter (descriptions, behaviors, quotes attributed to them, relationship status)
2. Build a proposed People fact set organized by person
3. Identify contradictions between chapters (e.g., Ch 3 says "she never spoke about the accident" but Ch 7 has her describing it)
4. Insert into DB via `add_canon_fact(book_slug, chapter_num, subject, fact, domain=domain)` — `chapter_num` is the chapter's integer number (not its slug), with `[RECONSTRUCTED]` note

People fact categories: physical description, relationship to author, what they said/did/believed in each chapter, consent_status if known.

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
- FAIL — at least one CONFLICT, OR (memoir only) any person `check_memoir_consent` marked `FAIL` (i.e. `consent_status: refused`) **appears** in a chapter draft at all (per Step 9's memoir CRITICAL rule below — mere appearance is enough, it does not need to also contradict an established fact; appearing at all already violates that person's refused consent).

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

**Fiction:** If the DB was reconstructed or new facts were discovered:
1. All facts already inserted via `add_canon_fact()` in Step 6 (see above).
2. Report to the user which chapters were flagged in Step 6.1 as containing a stale reference to a `CHANGED` fact's old value — those drafts may now reference outdated facts and need a re-read against the new canon. (`canon_log_facts` entries carry no per-entry impact list — this is the chapter set found by that scan, not a stored field.)

**Memoir:** If people facts were reconstructed or new facts were discovered:
1. All facts already inserted via `add_canon_fact()` in Step 6 (see above).
2. Report which chapters were flagged in Step 6 as contradicting an established `canon_log_facts` entry — those drafts may need a re-read. (Same caveat as the fiction branch: there is no stored per-entry impact list, only the Step 6 findings themselves.)
3. If `check_memoir_consent(book_slug)` (called in Step 1's Memoir supplement) returned any person with verdict `FAIL` (`consent_status: refused`), check whether that person's name appears in any chapter draft read in Prerequisite Step 3 — if it does, flag as CRITICAL, route to `/storyforge:memoir-ethics-checker`

## Rules
- Report ALL conflicts, even minor ones. The author decides what to fix.
- Never silently correct chapter drafts — always report and let the author decide.
- If two chapters conflict, don't assume one is right — present both and let the author choose.
- A reconstructed timeline is a proposal, not canon. Mark it clearly.
- Focus on facts extractable from text — don't make assumptions about intent.
