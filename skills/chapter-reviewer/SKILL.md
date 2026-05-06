---
name: chapter-reviewer
description: |
  Review and critique a chapter for craft quality, voice consistency, and AI-tells.
  Use when: (1) User says "Kapitel reviewen", "review chapter",
  (2) After chapter-writer completes a draft.
  Memoir books → use `/storyforge:chapter-reviewer-memoir` instead.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Chapter Reviewer

## Step 0 — Resolve Book Category

Read `book_category` from the review brief (Step 1). Treat missing as `fiction`.

If `book_category == "memoir"` → invoke `/storyforge:chapter-reviewer-memoir` instead. Do not continue in this skill.

## Prerequisites — MANDATORY LOADS

### Step 1 — Load the review brief (single MCP call, replaces 6+ direct file reads)

Call MCP `get_review_brief(book_slug, chapter_slug)`. This returns:

- `book_category` — must be `fiction`; if `memoir` → see Step 0
- `chapter_timeline` — intra-day time grid for this chapter
- `previous_chapter_timeline` — same for the preceding chapter
- `canonical_timeline_entries` — parsed `plot/timeline.md` events
- `travel_matrix` — parsed `world/setting.md` Travel Matrix rows
- `canon_log_facts` — parsed `plot/canon-log.md` facts
- `tonal_rules` — non-negotiable rules, litmus test, banned patterns from `plot/tone.md`
- `active_rules` — book CLAUDE.md ## Rules with severity
- `active_callbacks` — book CLAUDE.md ## Callback Register items
- `errors` — non-empty means some files missing; degrade gracefully, do not invent

Honor every populated field. Empty lists / null means "file missing — degrade gracefully."

### Step 2 — Load author and craft context

- **Author profile** via MCP `get_author()`. **Why:** Voice consistency check needs the documented baseline. `writing_discoveries.recurring_tics` (Issue #151) lists cross-book tics — flag any hit as Major findings. `style_principles` and `donts` feed the same review pass.
- **Author vocabulary** from `~/.storyforge/authors/{slug}/vocabulary.md`. **Why:** Banned-word scan and preferred-word check both run against this list.
- **Craft references** via MCP `get_craft_reference()`:
  - `dos-and-donts` — general craft baseline for the Craft section (5 points).
  - `anti-ai-patterns` — AI-tell catalog for the Anti-AI section (5 points).
  - `chapter-construction` — hook/scene-sequel/ending criteria for the Structure section (5 points).
  - `dialog-craft` — subtext, voice differentiation, tag discipline — for points 9 and 15.
  - `show-dont-tell` — show/tell balance check for points 6 and 24.
  - `simile-discipline` — the two-question test for point 10b.
- **Detect if Chapter 1:** Check chapter slug (starts with `01-` or `001-`) or frontmatter chapter number. If Chapter 1: also load `openings-and-endings` craft reference.

### Step 3 — Read the prose (direct file reads)

- Read the chapter draft: `{project}/chapters/{chapter}/draft.md`
- Read the chapter outline: `{project}/chapters/{chapter}/README.md`
- Read previous chapter draft for continuity context
- Optional: If `{project}/research/manuscript-report.md` exists, check whether any of THIS chapter's distinctive 5-7 word phrases appear in earlier chapters. Flag matches in the Continuity Report.

## First Chapter Checklist — 13 Points (ONLY for Chapter 1)

If this is Chapter 1, run this checklist BEFORE the standard review. Rate each point: PASS / WARN / FAIL.

**Set the Stage**
1. **Orient the reader** — Time period and location established early without info dump.
2. **Set the tone** — Words, events, dialogue, and setting convey the story's mood.
3. **Establish the genre** — Reader knows what type of story they're entering.

**Spotlight the Protagonist**
4. **Protagonist in their element** — Shown doing what defines them best (not sitting, not waking up).
5. **Protagonist wants something** — A concrete desire or longing exists before the main plot hits.
6. **Normal world revealed** — Everyday life before disruption is visible.
7. **Problem illustrated** — Something is broken or unsatisfying in the protagonist's world.
8. **Theme seeded** — A subtle hint at the story's deeper questions exists.
9. **Internal conflict established** — Fear-versus-desire tension is present.

**Give Readers a Reason to Stay**
10. **Killer first sentence** — Opening line sparks curiosity and makes the reader ask a question.
11. **Curiosity sparked** — Unanswered questions or intriguing dialogue keep reader leaning forward.
12. **Dread established** — Coming challenges are foreshadowed.
13. **First domino knocked** — The initial event that sets the journey in motion occurs by chapter's end.

**Load-bearing items** (FAIL here = chapter needs revision before moving on): 4, 5, 9, 10, 13.

---

## Review Checklist — 28 Points + 1 sub-point

### Structure (5 points)
1. **Opening hook** — Does the first paragraph grab? Would you keep reading?
2. **Scene-sequel flow** — Does each scene have goal/conflict/outcome?
3. **Chapter arc** — Does something CHANGE from start to finish?
4. **Ending** — Does it compel the reader to turn the page?
5. **Pacing** — Does the chapter breathe? Action/reflection balance?

### Craft (5 points + 1 sub-point)
6. **Show don't tell** — Are emotions shown through action/body, not named?
7. **Sensory details** — Are multiple senses engaged (not just visual)?
8. **Specific details** — Concrete nouns and precise verbs, not generic descriptions?
9. **Dialog quality** — Subtext present? Characters sound different? Minimal tags?
10. **Conflict** — Is there tension in every scene? No filler?

**10b. Simile discipline (craft sub-point)** — Apply the two-question test from `simile-discipline.md` to every `like`, `as if`, `as [adj] as`, `the way [X]`, `moved/felt/sounded like`, and `the kind of [noun] that [clause]` construction. For each: does the vehicle literally resemble the tenor? Does it do work a concrete beat couldn't? Flag illogical or decorative similes, stacked similes (2+ per paragraph without each doing distinct work), and dead similes. Respect author-voice bias.

### Voice (5 points)
11. **Author consistency** — Does this sound like the defined author profile?
12. **Tone match** — Does the tone match the profile's descriptors?
13. **Vocabulary** — Any banned words used? Preferred words present?
14. **Sentence rhythm** — Varied length? Matches author's style?
15. **Dialog voice** — Each character distinguishable without tags?

### Continuity (5 points + 1 sub-point)

16. **Canon consistency** — Does the chapter contradict any fact in the Canon Log? Pay special attention to `CHANGED` facts.
17. **Timeline accuracy** — Do day/date references match `plot/timeline.md`?
18. **Travel consistency** — Do distances/travel times match the Travel Matrix?
19. **Stale references** — Does this chapter's slug appear in the `revision_impact` list of any `**CHANGED**` bullet in `plot/canon-log.md`? If so, verify the chapter uses the NEW version of every changed fact.
20. **Character facts** — Do character descriptions/behaviors match established facts?
20a. **POV knowledge boundary** — Does the narration attribute domain knowledge the POV character's profile says they don't have? Three remediation options: (a) move into dialog, (b) reframe as lay observation, (c) cut.

### Plot Logic (5 points)

Load `analyze_plot_logic(book_slug, scope="chapter", chapter_slug=...)` once before scoring this section. The returned `knowledge_index` provides facts, promises, and chapter story-days.

20b. **Information leak** — Does the POV character reference any fact established in a later chapter, or in an earlier chapter where the POV was absent? Severity: **high (FAIL)** if demonstrably absent; **WARN** otherwise.
20c. **Motivation chain** — Does each significant decision follow from the character's established wants and knowledge? Flag contradictions without on-page justification. Severity: **WARN**.
20d. **Causality direction** — Run static `causality_inversion` findings for this chapter. **FAIL** on any.
20e. **World rule consistency** — Does the chapter break any rule from the canon log "World / Setting Facts" or `world/rules.md`? Look for negation patterns that the prose violates without an exception clause. Severity: **high (FAIL)**.
20f. **Chapter promise** — If the chapter places a setup-element, is it logged in `## Promises`? Suggest missing promises; on approval call `register_chapter_promises`. Severity: **WARN**.

### Tonal Consistency (5 points) — only if `plot/tone.md` exists
21. **Dominant mode** — Does the chapter match the dominant mode for this chapter's position?
22. **Warning signs** — Does the chapter exhibit any warning-sign patterns for this stage?
23. **Non-negotiable rules** — Are ALL non-negotiable rules satisfied?
24. **Litmus test** — Answer every question from the Litmus Test section.
25. **Banned patterns** — Does the chapter use any book-specific banned prose patterns?

### Intra-Day Timeline (3 points)
26. **Time anchor** — Does the chapter establish when it starts? Consistent with previous chapter?
27. **Internal consistency** — Do relative time references match the Chapter Timeline in README.md?
28. **Cross-chapter consistency** — Do references to earlier events match the previous chapter's timeline?

### Anti-AI (5 points)
21. **AI vocabulary** — Any words from the banned list?
22. **Structural uniformity** — Paragraphs/sentences suspiciously uniform in length?
23. **Generic descriptions** — Any "bustling city", "warm smile", "piercing gaze" clichés?
24. **Emotional telling** — Any "he felt a wave of sadness" instead of showing?
25. **Neat resolution** — Does every scene wrap up too tidily?

## Output Format

**Report target: 800–1200 words total.** Critical findings first, then Recommended, Minor only if a pattern emerges (3+ instances). Skip empty sections — if there are zero AI-tells, the AI-Tell Report is one line ("Flagged words: none. Variance high. Generic descriptions: 0."), not a full table.

```markdown
## Chapter Review: {Chapter Title}

### First Chapter Report (only if Chapter 1)
| # | Requirement | Result | Notes |
|---|---|---|---|
| 1 | Orient the reader | PASS/WARN/FAIL | |
| 2 | Set the tone | PASS/WARN/FAIL | |
| 3 | Establish genre | PASS/WARN/FAIL | |
| 4 | Protagonist in element ⚠️ | PASS/WARN/FAIL | |
| 5 | Protagonist wants something ⚠️ | PASS/WARN/FAIL | |
| 6 | Normal world revealed | PASS/WARN/FAIL | |
| 7 | Problem illustrated | PASS/WARN/FAIL | |
| 8 | Theme seeded | PASS/WARN/FAIL | |
| 9 | Internal conflict ⚠️ | PASS/WARN/FAIL | |
| 10 | Killer first sentence ⚠️ | PASS/WARN/FAIL | |
| 11 | Curiosity sparked | PASS/WARN/FAIL | |
| 12 | Dread established | PASS/WARN/FAIL | |
| 13 | First domino knocked ⚠️ | PASS/WARN/FAIL | |

⚠️ = load-bearing, FAIL requires revision before proceeding.

---

### Score: [X]/25 (core) + [X]/5 (tonal, if tone.md exists) + [X]/3 (timeline)

### Strengths
- *What works well*
- *Specific quotes that shine*

### Issues

#### Critical (Must Fix)
- [Issue] — [Location] — [Suggested fix]

#### Recommended (Should Fix)
- [Issue] — [Location] — [Suggested fix]

#### Minor (Nice to Have)
- [Issue] — [Location] — [Suggested fix]

### Continuity Report
- Canon conflicts: [count] — [details]
- Timeline conflicts: [count] — [details]
- Travel Matrix conflicts: [count] — [details]
- Stale references (from revisions): [count] — [details]

### Plot Logic Report
- Information leaks (high): [count] — [details with evidence]
- Information leaks (warn): [count] — [details]
- Motivation breaks: [count] — [details]
- Causality inversions: [count] — [details]
- World-rule violations: [count] — [details]
- Promise log: [N placed, M logged, K missing]

### Tonal Report (if tone.md exists)
- Dominant mode match: [yes/no — expected: X, actual: Y]
- Warning signs triggered: [list or "none"]
- Non-negotiable rules: [PASS/FAIL per rule]
- Litmus test: [pass/fail per question]
- Banned patterns found: [list or "none"]

### Chapter Timeline Report
- Time anchor: [established / missing / inconsistent with previous chapter]
- Internal time conflicts: [count] — [details]
- Cross-chapter time conflicts: [count] — [details]

### AI-Tell Report
- Flagged words: [list]
- Sentence length variance: [high/medium/low]
- Generic descriptions found: [count]

### Simile Report
- Total simile markers found: [count]
- Illogical / decorative (cut or revise): [list with quote + location]
- Stacked (2+ per paragraph without distinct work): [list]
- Dead similes: [list]
- Passing similes: [count]
- Author-voice register applied: [sparse / simile-heavy / as documented in profile]

### Verdict
[PASS / NEEDS REVISION / MAJOR REVISION]

VERDICT: PASS | WARN | FAIL

### Suggested Next Step
[/storyforge:chapter-writer to revise | move to next chapter]
```

Verdict mapping:
- **PASS** ↔ no Critical issues, no AI-tell banlist hits, all load-bearing first-chapter rows clear.
- **WARN** ↔ Recommended issues exist but nothing blocks moving on after a single targeted pass.
- **FAIL** ↔ at least one Critical issue, any AI-tell banlist hit, or any load-bearing first-chapter row at FAIL.

## Rules
- Be BRUTALLY honest.
- Pair every critical finding with a specific strength — the report is signal, not just complaint.
- Quote specific lines when flagging issues.
- Suggest concrete rewrites, not just "make this better."
- The AI-tell check runs as a hard gate — if banned words appear, flag the chapter as NEEDS REVISION regardless of other scores.
- When the user flags an issue: VERIFY before accepting. Re-read the passage, check context from earlier chapters, and push back if the user misunderstood (especially English nuances).
