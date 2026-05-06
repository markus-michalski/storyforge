---
name: chapter-reviewer-memoir
description: |
  Review and critique a memoir chapter for craft quality, voice consistency,
  consent obligations, and memoir-specific AI-tells.
  Use when: (1) `book_category == "memoir"` AND user says "Kapitel reviewen",
  "review chapter". Fiction books → use `/storyforge:chapter-reviewer` instead.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Chapter Reviewer (Memoir)

This skill is the memoir variant of `chapter-reviewer`, split out per Issue #176 so memoir sessions load the memoir prerequisite set (people-log, consent gate, memoir anti-AI patterns, real-world plausibility) instead of the fiction set. Memoir uses real settings, real chronology, and real people with consent obligations and factual-truth standards fiction does not carry.

## Step 0 — Verify memoir mode

Read `book_category` from the review brief (Step 1).

If `book_category` is `fiction` or missing → stop and tell the user:
> *This book's `book_category` is `fiction`. Use `/storyforge:chapter-reviewer` for fiction work.*

Otherwise surface a one-line note: *"Working in memoir mode — loading memoir anti-AI patterns, checking consent status for named people, skipping Travel Matrix and world-rule checks."*

## Prerequisites — MANDATORY LOADS

### Step 1 — Load the review brief

Call MCP `get_review_brief(book_slug, chapter_slug)`. This returns:

- `book_category` — must be `memoir`; if `fiction` → see Step 0
- `chapter_timeline` — intra-day time grid for this chapter
- `previous_chapter_timeline` — same for the preceding chapter
- `canonical_timeline_entries` — parsed `plot/timeline.md` events (real chronology — errors here are factual errors, not just continuity problems)
- `travel_matrix` — empty for memoir; do not use
- `canon_log_facts` — empty for memoir; use `people-log` instead
- `consent_status_warnings` — people with non-approved consent status
- `tonal_rules` — non-negotiable rules, litmus test, banned patterns from `plot/tone.md`
- `active_rules` — book CLAUDE.md ## Rules with severity
- `active_callbacks` — book CLAUDE.md ## Callback Register items
- `errors` — non-empty means some files missing; degrade gracefully, do not invent

Also directly read `{project}/plot/people-log.md` if it exists — this is the memoir equivalent of canon-log.

### Step 1b — Consent Gate

Before reviewing a single line of prose, check `consent_status_warnings` from the brief.

- If any person appears with `consent_status: refused` — flag as **CRITICAL**. The scene should not be published. Route the user to `/storyforge:memoir-ethics-checker` for the cut/anonymize/re-frame decision.
- If `consent_status: missing` or `pending` — flag as **WARNING**. Surface the name and note that consent needs to be resolved before export.

This is a review flag, not a halt — the review continues, but consent issues must appear prominently at the top of the report.

### Step 2 — Load author and craft context

- **Author profile** via MCP `get_author()`. **Why:** Voice consistency check needs the documented baseline. `writing_discoveries.recurring_tics` lists cross-book tics — flag any hit as Major findings. `style_principles` and `donts` feed the same review pass.
- **Author vocabulary** from `~/.storyforge/authors/{slug}/vocabulary.md`. **Why:** Banned-word scan and preferred-word check both run against this list.
- **Craft references** via MCP `get_craft_reference()`:
  - `dos-and-donts` — general craft baseline for the Craft section.
  - `anti-ai-patterns` — universal AI-tell catalog.
  - `chapter-construction` — hook/scene-sequel/ending criteria.
  - `dialog-craft` — subtext, voice differentiation, tag discipline.
  - `show-dont-tell` — show/tell balance check.
  - `simile-discipline` — two-question test for simile discipline.
- **Memoir-specific** via `get_book_category_dir("memoir")`:
  - `memoir-anti-ai-patterns.md` — memoir-specific AI-tells the universal catalog misses (reflective platitudes, "looking back" hinges, tidy lesson endings, hedging-as-humility, therapeutic reframe, explanation-after-image).
- **Detect if Chapter 1:** Check chapter slug (starts with `01-` or `001-`) or frontmatter chapter number. If Chapter 1: also load `openings-and-endings` craft reference.

### Step 3 — Read the prose

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
5. **Protagonist wants something** — A concrete desire or longing exists before the main narrative hits.
6. **Normal world revealed** — Everyday life before disruption is visible.
7. **Problem illustrated** — Something is broken or unsatisfying in the protagonist's world.
8. **Theme seeded** — A subtle hint at the story's deeper questions exists.
9. **Internal conflict established** — Fear-versus-desire tension is present.

**Give Readers a Reason to Stay**
10. **Killer first sentence** — Opening line sparks curiosity.
11. **Curiosity sparked** — Unanswered questions or intriguing framing keep the reader leaning forward.
12. **Dread established** — Coming challenges are foreshadowed.
13. **First domino knocked** — The initial event that sets the narrative in motion occurs by chapter's end.

**Load-bearing items** (FAIL here = chapter needs revision before moving on): 4, 5, 9, 10, 13.

---

## Review Checklist — 28 Points + 1 sub-point

### Structure (5 points)
1. **Opening hook** — Does the first paragraph grab?
2. **Scene-sequel flow** — Does each scene have goal/conflict/outcome?
3. **Chapter arc** — Does something CHANGE from start to finish?
4. **Ending** — Does it compel the reader to continue?
5. **Pacing** — Does the chapter breathe? Action/reflection balance?

### Craft (5 points + 1 sub-point)
6. **Show don't tell** — Are emotions shown through action/body, not named?
7. **Sensory details** — Are multiple senses engaged (not just visual)?
8. **Specific details** — Concrete nouns and precise verbs, not generic descriptions?
9. **Dialog quality** — Subtext present? Characters sound different? Minimal tags?
10. **Conflict** — Is there tension in every scene? No filler?

**10b. Simile discipline** — Apply the two-question test from `simile-discipline.md` to every `like`, `as if`, `as [adj] as`, `the way [X]`, `moved/felt/sounded like`, and `the kind of [noun] that [clause]` construction. Flag illogical or decorative similes, stacked similes, and dead similes. Respect author-voice bias.

### Voice (5 points)
11. **Author consistency** — Does this sound like the defined author profile?
12. **Tone match** — Does the tone match the profile's descriptors?
13. **Vocabulary** — Any banned words used? Preferred words present?
14. **Sentence rhythm** — Varied length? Matches author's style?
15. **Dialog voice** — Each person distinguishable without tags?

### Continuity (5 points + 1 sub-point) — memoir mode

16. **People-Log consistency** — Does the chapter contradict any established fact in `plot/people-log.md`? Pay special attention to descriptions, relationships, or events recorded in earlier chapters.
17. **Timeline accuracy** — Do date/year references match `plot/timeline.md`? In memoir this is real chronology — an error is not just a continuity problem, it's a factual error.
18. **Real-world plausibility** — Do stated distances or travel times match real-world geography? (No Travel Matrix — use common sense. Flag implausible claims as WARNING.)
19. **Stale references** — Does this chapter's slug appear in the `revision_impact` list of any `**CHANGED**` bullet in `plot/people-log.md`? Verify the chapter uses the updated version of every changed fact.
20. **Person facts** — Do descriptions and behaviors of named people match what was established in earlier chapters and the people-log?
20a. **Dialog reconstruction honesty** — Is reconstructed dialog presented with appropriate epistemic humility? Does the chapter claim verbatim precision for conversations that happened years or decades ago? Flag any dialog rendered as if perfectly remembered without qualifying framing.

### Plot Logic (5 points)

Load `analyze_plot_logic(book_slug, scope="chapter", chapter_slug=...)` once before scoring this section.

20b. **Information leak** — Does the POV reference any fact established in a later chapter, or in an earlier chapter where the POV was absent? Severity: **high (FAIL)** if demonstrably absent; **WARN** otherwise.
20c. **Motivation chain** — Does each significant decision follow from the person's established wants and knowledge? Flag contradictions without on-page justification. Severity: **WARN**.
20d. **Causality direction** — Run static `causality_inversion` findings for this chapter. **FAIL** on any.
20e. *(Skip — world-rule consistency is fiction-only.)*
20f. **Chapter promise** — If the chapter places a setup-element, is it logged in this chapter's `## Promises` section? Suggest missing promises; on approval call `register_chapter_promises`. Severity: **WARN**.

### Tonal Consistency (5 points) — only if `plot/tone.md` exists
21. **Dominant mode** — Does the chapter match the dominant mode in the Tonal Arc?
22. **Warning signs** — Does the chapter exhibit warning-sign patterns for this stage?
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

### Memoir Anti-AI (6 points)

Load `memoir-anti-ai-patterns.md` (loaded in Step 2). Grade each:

26. **Reflective platitude** — Any generic wisdom claims ("family is complicated", "grief takes time", "I came to realize how much I'd grown")? Flag every instance.
27. **"Looking back" hinges** — Any "looking back now I can see", "in retrospect", "what I didn't know then was"? Occasional retrospective framing is valid; a pattern is evasion.
28. **Tidy lesson ending** — Does the chapter close with an explained moral? The best memoir closes on a scene or image, not a lesson.
29. **Hedging as humility** — Density of "perhaps", "in some way", "I think", "maybe"? Flag if density exceeds 2 per 500 words.
30. **Therapeutic reframe** — Any "I came to understand that my anger was actually grief" framing? Translates lived experience into therapy-speak.
31. **Explanation after image** — Does the chapter describe a scene and immediately explain what it meant? The image should land alone.

Report memoir AI-tells in their own labeled section, separate from universal Anti-AI findings.

## Output Format

**Report target: 800–1200 words total.** Critical findings first, then Recommended, Minor only if a pattern emerges (3+ instances). Skip empty sections.

```markdown
## Chapter Review: {Chapter Title}

### First Chapter Report (only if Chapter 1)
| # | Requirement | Result | Notes |
|---|---|---|---|
| 1 | Orient the reader | PASS/WARN/FAIL | |
...
| 13 | First domino knocked ⚠️ | PASS/WARN/FAIL | |

⚠️ = load-bearing, FAIL requires revision before proceeding.

---

### Score: [X]/25 (core) + [X]/5 (tonal) + [X]/3 (timeline) + [X]/6 (memoir AI-tells)

### Strengths
- *What works well*

### Issues

#### Critical (Must Fix)
- [Issue] — [Location] — [Suggested fix]

#### Recommended (Should Fix)
- [Issue] — [Location] — [Suggested fix]

#### Minor (Nice to Have)
- [Issue] — [Location] — [Suggested fix]

### Continuity Report
- People-Log conflicts: [count] — [details]
- Timeline conflicts: [count] — [details]
- Real-world plausibility issues: [count] — [details]
- Stale references: [count] — [details]
- Consent warnings: [list persons with non-approved consent_status, or "none"]

### Plot Logic Report
- Information leaks (high): [count] — [details]
- Information leaks (warn): [count] — [details]
- Motivation breaks: [count] — [details]
- Causality inversions: [count] — [details]
- Promise log: [N placed, M logged, K missing]

### Tonal Report (if tone.md exists)
- Dominant mode match: [yes/no]
- Warning signs triggered: [list or "none"]
- Non-negotiable rules: [PASS/FAIL per rule]
- Litmus test: [pass/fail per question]
- Banned patterns found: [list or "none"]

### Chapter Timeline Report
- Time anchor: [established / missing / inconsistent]
- Internal time conflicts: [count] — [details]
- Cross-chapter time conflicts: [count] — [details]

### AI-Tell Report
- Flagged words: [list]
- Sentence length variance: [high/medium/low]
- Generic descriptions found: [count]

### Memoir AI-Tell Report
- Reflective platitudes: [count] — [examples]
- "Looking back" hinges: [count] — [examples or "none"]
- Tidy lesson endings: [found / not found]
- Hedging density: [X per 500 words]
- Therapeutic reframes: [count] — [examples or "none"]
- Explanation-after-image: [count] — [examples or "none"]

### Simile Report
- Total simile markers found: [count]
- Illogical / decorative: [list]
- Stacked: [list]
- Dead similes: [list]
- Passing similes: [count]

### Verdict
[PASS / NEEDS REVISION / MAJOR REVISION]

VERDICT: PASS | WARN | FAIL

### Suggested Next Step
[/storyforge:chapter-writer-memoir to revise | move to next chapter]
```

Verdict mapping:
- **PASS** — no Critical issues, no AI-tell banlist hits, all load-bearing first-chapter rows clear.
- **WARN** — Recommended issues exist but nothing blocks moving on after a targeted pass.
- **FAIL** — at least one Critical issue, any AI-tell banlist hit, or any load-bearing first-chapter row at FAIL.

## Rules
- Be BRUTALLY honest.
- Pair every critical finding with a specific strength.
- Quote specific lines when flagging issues.
- Suggest concrete rewrites, not just "make this better."
- The AI-tell check runs as a hard gate — banned words → flag as NEEDS REVISION regardless of other scores.
- When the user flags an issue: VERIFY before accepting. Re-read the passage, check context, and push back if the user misunderstood.
- Run Dimension 26–31 (Memoir Anti-AI) and report in a separate labeled section. Do NOT fold memoir-specific tells into the universal Anti-AI section.
- Consent warnings from Step 1b must appear PROMINENTLY — as the first item in the Critical section if any person has `consent_status: refused`. This is a publication blocker, not a craft note.
