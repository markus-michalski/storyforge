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
model: claude-opus-4-7
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

After reading the consent report, read each chapter draft that mentions a
WARN or FAIL person by name (or by their `real_name` if anonymized). Scan for
the four defamation-risk patterns from `real-people-ethics.md`:

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
(`"I felt that"`, `"It seemed to me"`, `"my impression was"`).

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
  [one line per hit: chapter, person, pattern code, fix direction]
```

### 6. Verdict and next step

**PASS (no FAILs, no WARNs, no defamation hits):**
Tell the user the ethics check is clean. They may proceed to export.

**WARN only (no FAILs, no defamation hits):**
Tell the user: these are resolvable before publication. For each WARN person,
propose the smallest concrete fix:
- `pending` → ask the person; if refused, re-profile.
- `not-asking` → confirm the decision is deliberate and documented.
- Missing `person_category` → fill in the four-category field.
- Missing/unknown `consent_status` → fill in a valid value.

**FAIL (any refused consent):**
Hard stop. Export is blocked. Tell the user:

> **Export blocked** — {name} has refused consent. Options:
> 1. Anonymize fully (must pass the "identifiable by close acquaintance" test —
>    see `real-people-ethics.md`). Re-profile as `anonymized-or-composite`,
>    consent_status `not-required`.
> 2. Remove the person from the narrative.
> 3. Obtain consent (unlikely if already refused — but if the situation has
>    changed, update the profile and re-run).

**Defamation-risk hits:**
Offer rewrites. Prioritize D4 (per-se-defamatory) > D2 (reconstructed
dialogue) > D3 (unframed mind-reading) > D1 (compressed-time).

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

## Rules

- This skill is **memoir-only**. Do not run it on fiction books.
- A `refused` consent status is a **hard export block** — not a suggestion.
  The book cannot go to readers (even beta readers) in a form that identifies
  the refusing person. Anonymization is the only path forward short of removal.
- `not-asking` is a deliberate posture, not a bug. Present it as WARN so the
  author consciously confirms the decision before publication, but do not
  pressure them to ask. The `real-people-ethics.md` doc covers why someone
  might not ask (estranged relationship, abuser, deceased-but-survivors-hostile).
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
  flag from a false alarm.
