---
name: author-check
description: |
  Verify positive style compliance after chapter drafting.
  Checks presence of style_principles Writing Discoveries and quantitative prose targets.
  Use when: (1) User says "author check", "style check", "positive check",
  (2) After chapter-writer to verify positive style markers are present,
  (3) When chapter-reviewer finds many violations — catches the flip side,
  (4) Suspicion that banter, sarcasm, or other documented voice traits are missing.
  Counterpart to manuscript-checker (which only catches negatives).
model: claude-opus-4-8
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Author Check — Positive Style Compliance Gate

The constraint system in StoryForge is structurally biased toward negatives.
`manuscript-checker` and `chapter-reviewer` flag what should NOT be there.
Nothing verifies what SHOULD be there.

This skill is that verification.

It checks the draft against:
1. **Style Principles** from the author's Writing Discoveries — positive patterns the author has trained into the profile
2. **Quantitative prose targets** derived from studied works (dialog ratio, fragment rate, etc.)
3. **Balance** — too many violations + zero positive hits signals generic-AI drift

---

## Phase 1 — Load Context

### 1a. Resolve book and author

Call MCP `get_book_full(book_slug)`. From the result, extract `author_slug` — to load the author profile.

Call MCP `resolve_path(book_slug, "chapters", chapter_slug)` to get the chapter's directory — `get_book_full()` does not return a `project_path` field. Store the result as `chapter_dir`; if `exists: false`, the chapter directory itself doesn't exist yet (distinct from the chapter existing but its `draft.md` missing — see 1c).

If `book_slug` is missing, call MCP `list_books()` and ask the user to pick one.

### 1b. Load author profile

Call MCP `get_author(author_slug)`. From the result, extract:

- **Writing Discoveries → Style Principles** (`writing_discoveries.style_principles`) — the list of positive patterns extracted from studied works. This is what chapter-writer is instructed to "lean into." This skill verifies that leaning actually happened.
- **Writing Discoveries → Recurring Tics** (`writing_discoveries.recurring_tics`) — constraint list; not checked here but used for balance warning.
- **Quantitative targets** — look for fields set by `study-author`:
  - `dialog_ratio_target` (format: "45–55%")
  - `fragment_ratio_target` (format: "12–18%")
  - `single_line_paragraph_ratio_target` (format: "15–25%")
  - `avg_sentence_length_target` (format: "11–15 words")
  - If these fields are absent or empty, fall back to defaults (see Phase 3).
- **Style notes** (`style_notes`) — Voice tables, Tone Profile, Signature Moves from `profile.md` (Issue #294). Read if non-empty; use as qualitative context for the tone and positive-marker checks. Empty → skip silently.

- **Tone descriptors** (`tone`) — e.g. "sarcastic, playful, warm". Used as a soft lens for qualitative checks.

### 1c. Load the chapter draft

Read `{chapter_dir}/draft.md`.

If the file is missing, stop. Report: "Draft not found at expected path — run chapter-writer first or check the chapter slug."

### 1d. Check for existing reviewer output (optional)

Look for `{chapter_dir}/review.md`. If it exists, extract constraint violation count from its summary section (look for "Major findings: N" or similar). Store as `constraint_violations` (default: unknown).

---

## Phase 2 — Parse Style Principles

From `writing_discoveries.style_principles`, build a checklist. **Genre filter first:** skip any entry whose `genres` list has no overlap with this book's genres. Entries without a `genres` field are universal and always included. Entries with `universal: true` are always included regardless of `genres`.

Each style principle is one of:
- **Quantitative** — contains a specific number, minimum, ratio, or frequency target. Examples:
  - "Mindestens 2 Banter-Exchanges pro Kapitel"
  - "Dialog ratio: 45–55%"
  - "Fragment ratio: 12–18%"
- **Qualitative** — documents a pattern or technique without a hard number. Examples:
  - "Sarcasm as default register in tense scenes"
  - "Vulnerability reveals follow banter, not during it"
  - "Humor-as-armor: characters deflect with wit before breaking open"

Separate the two lists. Quantitative entries get numeric verification. Qualitative entries get prose-scanning verification.

If Writing Discoveries → Style Principles is empty, report: "No style_principles Writing Discoveries found for this author. Run `/storyforge:study-author` on at least one book to populate positive targets. Skipping compliance checks."

---

## Phase 3 — Quantitative Metrics

Run these counts on the raw draft text. Present actual values vs. targets.

### 3a. Dialog ratio
Count characters inside opening and closing quotation marks (`"…"`) as dialog.
Ratio = dialog characters / total non-whitespace characters.

**Default target:** 45–55% (override with `dialog_ratio_target` from profile if set).

### 3b. Fragment ratio
Count sentences of 5 words or fewer as fragments. (Split on sentence-ending punctuation: `.` `!` `?` — exclude dialog fragments inside quotes.)
Ratio = fragment sentences / total sentences.

**Default target:** 12–18% (override with `fragment_ratio_target` from profile if set).

### 3c. Single-line paragraph ratio
Count paragraphs that consist of a single sentence (or ≤75 characters).
Ratio = single-line paragraphs / total paragraphs.

**Default target:** 15–25% (override with `single_line_paragraph_ratio_target` from profile if set).

### 3d. Average sentence length
Total words (excluding dialog punctuation markup) / total sentence count.

**Default target:** 11–15 words (override with `avg_sentence_length_target` from profile if set).

> **Note on targets:** These defaults represent a readable contemporary fiction average.
> Author-specific targets from `study-author` always take precedence.
> If the author's profile shows a studied-work average of 18 words, that IS the target, not 11–15.

---

## Phase 4 — Qualitative Style Principles Check

For each **qualitative** style_principle entry, scan the chapter draft for evidence.

**Method:**
Read the draft carefully. For each principle:
1. Identify what evidence would look like in prose
2. Scan for 1–3 concrete examples (short quote + line context)
3. Classify as:
   - **FOUND** — clear evidence, can quote at least one instance
   - **PARTIAL** — something approximating the pattern, but weak or infrequent
   - **NOT FOUND** — no evidence detected after full read

Do not invent evidence. If you can't quote it, mark NOT FOUND.

**Quantitative style_principles** from Writing Discoveries that weren't already covered in Phase 3 get the same treatment here (count-based check).

---

## Phase 5 — Balance Warning

Compute:
- `positive_hits` = number of qualitative + quantitative checks with result FOUND or on-target
- `positive_total` = total checks run
- `constraint_violations` = from Phase 1d (or "unknown" if no reviewer output found)

**Trigger balance warning if:**
- `constraint_violations` is a known number AND > 5
- AND `positive_hits` < 1

**Warning text:**
> "This chapter has {N} constraint violations on record but no detectable positive style markers. The draft may be defaulting to generic AI register by omission — the author's documented voice traits are absent, not just suppressed."

Even without a known violation count, flag if `positive_hits == 0` and `positive_total > 0`:
> "No positive style markers detected. Constraint-free writing is not the same as voice-accurate writing. Check that the author's positive style_principles (banter, sarcasm, preferred structures) are actually present."

---

## Output Format

```markdown
## Author Check — {Book Title}, Chapter {N}: {Chapter Title}
**Author profile:** {author_slug} | **Checked:** {date}

---

### Quantitative Targets

| Metric | Actual | Target | Status |
|--------|--------|--------|--------|
| Dialog ratio | 38% | 45–55% | ⚠️ Below target |
| Fragment ratio | 15.2% | 12–18% | ✅ On target |
| Single-line paragraphs | 8% | 15–25% | ❌ Below target |
| Avg sentence length | 14.2 words | 11–15 words | ✅ On target |

---

### Style Principles Compliance

*(From Writing Discoveries → Style Principles)*

✅ **[Principle name]** — Found. Quote: "..."
⚠️  **[Principle name]** — Partial. Weak presence; only 1 instance in 4200 words. Quote: "..."
❌ **[Principle name]** — Not found. No evidence of this pattern in the draft.

*(Repeat for each style_principle entry)*

---

### Balance

| | Count |
|---|---|
| Positive markers found | 2 / 5 |
| Constraint violations on record | 7 |

⚠️ **Balance warning:** 7 constraint violations recorded, but only 2/5 positive style markers
present. The draft suppresses negatives but does not demonstrate the author's positive voice.

---

### Verdict

PASS | WARN | FAIL

**Verdict rationale:** [One sentence, max 20 words, naming the specific metric(s) or hit-rate that actually drove the verdict — not a generic restatement of the verdict itself.]

---

### Next Steps

[2–4 bullet points, one sentence each, ranked by impact. Example:]
- Dialog ratio (38%) is 7 points below target. Expand the {scene name} confrontation with actual back-and-forth rather than narrated summary.
- [Principle X] (NOT FOUND). This chapter has no banter. The protagonist and antagonist meet twice — both encounters are narrated at a remove. Add one direct exchange.
```

**Verdict thresholds:**

| Result | Condition |
|--------|-----------|
| PASS | ≥80% positive hits, all quantitative within target or at most 1 metric off by ≤5 points |
| WARN | 50–79% positive hits, OR 2 metrics off target, OR balance warning triggered |
| FAIL | <50% positive hits, OR 3+ metrics off target, OR balance warning with 0 positive hits |

---

## Rules

- This skill checks PRESENCE of positives, not absence of negatives. Constraint-checking is `chapter-reviewer`'s job. Don't cross-contaminate.
- If Writing Discoveries → Style Principles is empty: run only quantitative checks (Phase 3). Report the empty Discoveries as a finding — it means no positive extraction has been done yet.
- Quantitative metrics are approximations. Sentence and dialog boundary detection by text scan is not 100% accurate. Mark calculated values as "~" (approximately) if the draft uses unusual punctuation styles, and name the specific cause (e.g. "em-dash-led dialogue" or "no standard closing quotes") — a bare "~" tells the user a number is fuzzy but not why, which they can't act on.
- Quote concrete evidence for every FOUND verdict. An unquoted FOUND is unverifiable.
- When writing Next Steps, be specific: which scene, which character pair, what type of change. "Add more banter" is not actionable. "Add a back-and-forth exchange between X and Y in the {scene} — they currently argue via narrated summary" is.
- Do not suggest removing constraint violations here. That's the reviewer's domain. Focus only on what's missing from the positive side.
- If the user asks for something outside this skill's scope (a negative/constraint list, a generic non-actionable fix, cutting flagged content), don't just refuse — say in one sentence why, tied to the specific rule above. A silent or unexplained decline reads as unhelpful; a one-line reason lets the user redirect immediately.
- After report output: ask the user "Would you like me to pass this author-check result to chapter-reviewer as an additional section?" If yes, append a condensed version to the existing `review.md` (or note it for the next reviewer run).
