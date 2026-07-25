---
name: memoir-ethics-checker
description: |
  Consent and defamation risk scan for memoir books. Checks every person in
  people/ against their consent_status and person_category, produces a
  PASS / WARN / FAIL verdict, and flags anonymization gaps and defamation-risk
  language patterns in chapter drafts.
  Use when: (1) User says "ethics check", "consent check", "Einwilligungen prüfen",
  "Personen prüfen", (2) Before export of a memoir book, (3) After adding new
  people profiles, (4) During the revision phase of a memoir.
  Only runs on memoir books (book_category: memoir).
model: claude-opus-4-8
user-invocable: true
argument-hint: "<book-slug>"
---

# Memoir Ethics Checker

Consent gate and defamation-risk scanner for memoir books. Catches the class
of issues that can make a memoir legally or ethically unpublishable: people
who refused consent, profiles with missing/incomplete consent decisions, and
language patterns in the prose that map to defamation-risk territory.

## When to run

- After all people profiles in `people/` have been created or updated.
- Before the export gate — the export skill calls this as a pre-flight check
  when `book_category: memoir`.
- Whenever the user adds a new person or changes a consent decision.
- During the revision phase, as a safety check before sharing ARCs.

Does not replace `manuscript-checker` (prose quality) or `voice-checker`
(AI-tells). This one catches ethical and legal risk — a different class of
problem.

## Prerequisites — MANDATORY LOADS

- **`real-people-ethics.md`** via MCP `get_book_category_dir("memoir")` +
  `/craft/real-people-ethics.md`. **Why:** Defines the four-category model
  (public figure, private living person, deceased, anonymized/composite), the
  consent-status taxonomy, and defamation risk patterns the scan grades against.

## Workflow

### 1. Resolve target book

Use the user-supplied slug if provided. Otherwise call MCP `get_session()` and
use the active book. If still ambiguous, call `list_books()` and ask.

### 2. Verify memoir mode

Call MCP `get_book_full(book_slug)` and read `book_category`.

If `book_category` is not `memoir`: stop, explain that this skill only applies
to memoir books, and offer `/storyforge:sensitivity-reader` as the fiction
analogue.

### 3. Run the consent scan

If `real-people-ethics.md` (Prerequisites) has not yet been loaded this
session, load it now via `get_book_category_dir('memoir')` +
`/craft/real-people-ethics.md` before calling the tool below. This is
required on **every** run, including one that turns out to be a clean PASS
with zero findings — do not skip it just because the scan looks like it's
going to be uneventful.

Call MCP `check_memoir_consent(book_slug)`.

The tool returns:
```json
{
  "book_slug": "...",
  "overall": "PASS" | "WARN" | "FAIL",
  "people": [
    {
      "slug": "...",
      "name": "...",
      "person_category": "...",
      "consent_status": "...",
      "anonymization": "...",
      "real_name": "...",
      "verdict": "PASS" | "WARN" | "FAIL",
      "reason": "..."
    }
  ],
  "pass_count": 3,
  "warn_count": 1,
  "fail_count": 0,
  "gate": {
    "status": "PASS | WARN | FAIL",
    "reasons": ["..."],
    "findings": [ { code, message, severity, location: { person } } ],
    "metadata": { "pass_count": 3, "warn_count": 1, "fail_count": 0 }
  }
}
```

The `gate.status` mirrors `overall` and conforms to the uniform contract in
`reference/gate-contract.md`. Aggregators (e.g. the export-engineer pre-flight
or `run_quality_gates`) read `gate.status` rather than `overall`.

### 4. Defamation-risk prose scan

Defamation risk is independent of consent status — a person who has
confirmed consent to appear in the book has not thereby waived the right
not to be falsely accused of a crime, incompetence, or misconduct. Scan
chapters for mentions of **every** person profiled in `people/`, not only
WARN/FAIL people — a clean consent_status narrows what needs resolving
before export, it does not narrow what counts as defamation risk.

To read the actual prose: call MCP `list_chapters(book_slug)` to enumerate
chapters. Skip any chapter with `words == 0` (no draft written yet — nothing
to scan). For each remaining chapter, call MCP
`resolve_path(book_slug, "chapters", "{chapter_slug}/draft.md")`; if the
response has `exists: false`, skip that chapter silently (no draft on disk
despite a nonzero word count is a state-sync edge case, not this skill's
concern). Otherwise read `draft.md` at the returned `path`. Do not guess or
fabricate a chapter's file path or content.

Work through chapters in order, one at a time, accumulating hits as you go
— do not attempt to hold the whole manuscript in context at once. On a long
memoir (many chapters), this scan can be substantial; if you have to stop
before reaching the last chapter (context or turn limits), say so explicitly
in the report — list which chapters were scanned and which were not, rather
than presenting a partial scan as a complete one.

For each chapter, check every passage that mentions a profiled person by
name (or by their `real_name` if anonymized). Scan for the four
defamation-risk patterns from `real-people-ethics.md`:

**D1. Compressed-time assertion** — a characterization that would be defensible
with precise scope but reads as a blanket fact without it.
Signal: claim about a person's habitual behaviour, character, or condition
without a scoped time phrase ("that year", "during those months", "at the time").
Example: `"He drank too much."` → needs scope.

**D2. Reconstructed defamatory dialogue** — dialogue the person did not say,
attributed in a way that reads as fact rather than perception.
Signal: quoted speech attributed to a real, named person making a damaging
claim or confession they have not publicly made.

**D3. Unframed mind-reading** — internal state stated as fact rather than
perception.
Signal: `"She hated me"`, `"He despised the family"` without perception framing
(`"I felt that"`, `"It seemed to me"`, `"my impression was"`). A statement that
already uses this framing (e.g. `"I felt, at the time, that she hated me"`) is
**not** a D3 hit — the framing is itself the fix. Do not flag an already-framed
statement again out of caution.

**D4. Per-se-defamatory imputation** — imputing crime, professional incompetence,
or sexual misconduct without verification or protective framing.
Signal: direct or near-direct assertions of these categories about identifiable
real people.

For each hit: quote the passage, name the pattern (D1–D4), give a one-sentence
fix direction.

### 5. Present the report

**Chat summary target: max ~250 words.** Full detail in the sections below
if needed.

```
Ethics check: "{book_slug}" — {N} people profiled.
Overall: PASS | WARN | FAIL

Consent status:
  PASS ({n}): [names]
  WARN ({n}): [names + one-line reason each]
  FAIL ({n}): [names — EXPORT BLOCKED]

Defamation-risk findings: {n}
  [one line per hit: chapter, person, pattern code — BLOCKED if D4, fix direction]
```

### 6. Verdict and next step

`Overall Verdict` (PASS/WARN/FAIL) is the consent-only `gate.status` from
Step 3 — it is a machine-facing contract other aggregators (export-engineer
Step 0, `run_quality_gates`) read verbatim, so do not fold defamation
findings into it. The report's bottom-line `Verdict` line (EXPORT CLEAR /
RESOLVE BEFORE EXPORT / EXPORT BLOCKED), by contrast, is this skill's own
recommendation to the human reading the report, and **must** account for
defamation hits too — see the four cases below. **Only the consent side of
this gate is machine-enforced** (export-engineer Step 0 calls
`check_memoir_consent` and branches on `overall`); a D4 defamation hit is
not read by any automated gate. If the bottom-line Verdict says EXPORT
BLOCKED for a D4-only reason while Overall Verdict still says PASS/WARN, the
author must track and act on that manually — running export anyway is not
stopped by machinery, only by the author reading this report.

**Consent PASS, no defamation hits at all:**
Tell the user the ethics check is clean. Bottom-line Verdict: `EXPORT CLEAR`.

**Consent WARN (no FAILs), and/or D1–D3 hits (no D4, no FAIL):**
Tell the user: all of this is resolvable before publication, none of it is a
hard block. For each WARN person, propose the smallest concrete fix:
- `pending` → ask the person; if refused, re-profile.
- `not-asking` → confirm the decision is deliberate and documented.
- Missing `person_category` → fill in the four-category field.
- Missing/unknown `consent_status` → fill in a valid value.
For each D1–D3 hit, offer a rewrite (see below). This branch also covers a
consent PASS with D1–D3 hits (no WARN people at all) — the WARN-fix list
above simply has nothing to add in that case. Bottom-line Verdict:
`RESOLVE BEFORE EXPORT`.

**FAIL (any refused consent), regardless of defamation findings:**
Hard stop. Export is blocked. Tell the user:

> **Export blocked** — {name} has refused consent. Options:
> 1. Anonymize fully (must pass the "identifiable by close acquaintance" test —
>    see `real-people-ethics.md`). Re-profile as `anonymized-or-composite`,
>    consent_status `not-required`.
> 2. Remove the person from the narrative.
> 3. Obtain consent (unlikely if already refused — but if the situation has
>    changed, update the profile and re-run).

Bottom-line Verdict: `EXPORT BLOCKED`.

**Any D4 hit, regardless of consent Overall Verdict (PASS/WARN/FAIL):**
Set the bottom-line Verdict to `EXPORT BLOCKED` even if Overall Verdict
above it reads PASS or WARN — call out explicitly in the report text that
the two lines are tracking different things (see the note above) so the
author does not read a "PASS" and stop paying attention. Tell the user this
specific passage should not go to export or beta readers as written, until
it is rewritten or the claim is verified. This is this skill's own
recommendation, not a machine-enforced block — see the note above.

**Defamation-risk hits generally:**
Offer rewrites. Prioritize D4 (per-se-defamatory) > D2 (reconstructed
dialogue) > D3 (unframed mind-reading) > D1 (compressed-time). Label D4
hits **BLOCKED** in the report (not just "flagged"); D1–D3 findings are
risk flags with a suggested rewrite and do not affect the bottom-line
Verdict on their own.

## Output Format

```markdown
## Ethics Check Report — {book_slug}

### Overall Verdict: PASS | WARN | FAIL

### Consent Status by Person
| Person | Category | Consent Status | Verdict | Action |
|--------|----------|---------------|---------|--------|
| Name | person_category | consent_status | PASS/WARN/FAIL | — or action needed |

### Defamation-Risk Findings _(if any)_

**[Chapter slug, person name]** — Pattern D{n}: {pattern name}
> "{quoted passage}"
Fix: {one-sentence fix direction}

### Verdict
[EXPORT CLEAR / RESOLVE BEFORE EXPORT / EXPORT BLOCKED]

### Next Steps
[Specific, ordered action items]
```

For a D4 hit, append ` — BLOCKED` to the end of the "Pattern D{n}: {pattern
name}" line (e.g. `Pattern D4: Per-se-defamatory imputation — BLOCKED`). Do
not append it for D1–D3 hits.

## Rules

- This skill is **memoir-only**. Do not run it on fiction books.
- A `refused` consent status is a **hard export block** — not a suggestion.
  The book cannot go to readers (even beta readers) in a form that identifies
  the refusing person. Anonymization is the only path forward short of removal.
- `not-asking` is a deliberate posture, not a bug. Present it as WARN so the
  author consciously confirms the decision before publication, but do not
  pressure them to ask. The `real-people-ethics.md` doc covers why someone
  might not ask (estranged relationship, abuser, deceased-but-survivors-hostile).
  If the user directly asks whether they should ask anyway, stay neutral
  rather than refusing to engage: lay out the relevant considerations from
  `real-people-ethics.md` (both directions) so they can weigh them, but do
  not tell them what to decide and do not push them toward asking or not
  asking — the decision, and the responsibility for it, stays theirs.
- Missing `person_category` always produces WARN even when consent is clean —
  an unclassified person is an unreviewed risk.
- Defamation patterns D1–D4 are risk flags, not verdicts. Most instances are
  fixable with a single-sentence reframe. Only D4 (per-se-defamatory imputation)
  warrants treating the passage as blocked prose.
- Do not re-run the consent check automatically after a profile update — tell
  the user to run `/storyforge:memoir-ethics-checker` again once they have
  made the change.
- Load `real-people-ethics.md` before presenting any finding. The nuance in
  that document (public figure vs. private, "per se" defamation categories,
  anonymization patterns that work vs. don't) is what separates a useful risk
  flag from a false alarm. **Why:** the four-category model and D1–D4 definitions
  in that doc are required to grade findings accurately — without it, category
  misclassification produces misleading verdicts.
