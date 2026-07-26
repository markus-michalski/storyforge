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
model: claude-opus-5
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
      "anonymization": "none" | "partial" | "pseudonym" | "composite",
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

`real_name` is only populated when `anonymization != "none"`; otherwise it's
`""`. Match against both `name` and `real_name` in Step 4.

The `gate.status` mirrors `overall` and conforms to the uniform contract in
`reference/gate-contract.md`. Both fields are **consent-only** — the tool
never factors the Step 4 defamation scan into either one (see Step 6).
Aggregators (e.g. the export-engineer pre-flight or `run_quality_gates`)
read `gate.status` rather than `overall`, but that doesn't change what it
covers.

### 4. Defamation-risk prose scan

Load `real-people-ethics.md` now if not already loaded (see Prerequisites) —
this load happens on every run, including one that turns out to be a clean
PASS with zero findings; do not skip it because a clean check "won't need
it". The D1–D4 pattern definitions below are drawn from that doc.

Consent status is not a defamation waiver — a person who gave
`confirmed-consent` to appear in the memoir has not thereby waived their
right not to be falsely accused of a crime (D4) or have fabricated dialogue
attributed to them (D2). So this scan covers **every profiled person,
regardless of verdict** — PASS, WARN, and FAIL alike — not only the WARN/FAIL
people from Step 3.

`list_chapters` returns only `slug`/`number`/`title`/`status`/`words` — no
prose — so which chapters "mention a profiled person" can only be answered
by reading them, never by filtering on the list_chapters output first. Read
every chapter that has a draft, then apply the name/`real_name` filter
*after* reading:

1. Call MCP `list_chapters(book_slug)`. Keep only chapters whose `status` is
   past `Outline` (`Draft`, `Revision`, `Polished`, `Final`, or an alias
   thereof) — an `Outline`-status chapter has no `draft.md` yet.
2. For each kept chapter, call MCP `resolve_path(book_slug, "chapters",
   "{chapter_slug}/draft.md")` — matching the convention every other skill
   in this plugin uses (e.g. `chapter-reviewer`, `chapter-humanizer`). If
   the response has `exists: false`, skip that chapter and note it (in the
   summary's chapter count, not as a defamation finding) rather than
   treating the gap as either an error or a clean scan.
3. Read the chapter at the returned `path`, then search the actual prose
   for each profiled person's `name` and (if anonymized) `real_name` before
   applying the D1–D4 patterns below to any matching passage.
4. Do not guess a chapter's path and do not fabricate "scanned, nothing
   found" without having actually read real content.

Scan for the four defamation-risk patterns from `real-people-ethics.md`:

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
Converse: an already-framed statement like `"I felt that she hated me"` is
**not** a D3 hit — the perception framing is exactly what the pattern requires.

**D4. Per-se-defamatory imputation** — imputing crime, professional incompetence,
or sexual misconduct without verification or protective framing.
Signal: direct or near-direct assertions of these categories about identifiable
real people.

For each hit: quote the passage, name the pattern (D1–D4), give a one-sentence
fix direction.

### 5. Present the report

**Chat summary target: max ~250 words.** Full detail in the sections below
if needed.

If zero people are profiled yet (`{N}` = 0): frame this explicitly as "no
people profiled yet — nothing has been reviewed" rather than presenting the
resulting vacuous PASS as equivalent to a genuine "N people cleared" PASS.
Also tell the user the consequence, not just the framing: `check_memoir_consent`
with zero people still returns `overall: PASS`/`gate.status: PASS`, so
`/storyforge:export-engineer`'s Step 0 gate will clear automatically on this
vacuous PASS — profiles must be created via `character-creator-memoir`
first, or the export gate is not actually checking anything.

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

`Overall` here is this skill's own composite verdict (see Step 6) — never
paste `check_memoir_consent`'s raw consent-only `overall` field in directly,
it does not account for defamation-risk findings.

### 6. Verdict and next step

**Compute this skill's own Overall verdict — do not just copy
`check_memoir_consent`'s `overall`/`gate.status`.** That field is
consent-only (Step 3) and never reflects the Step 4 defamation scan, so a
D4 hit on an otherwise consent-PASS book still comes back as
`overall: PASS` from the tool. This skill reports its own composite instead:

- **FAIL** — any person's consent verdict is FAIL, OR any D4 defamation hit
  exists.
- **WARN** — no FAIL condition above, but any person's consent verdict is
  WARN, OR any D1–D3 defamation hit exists.
- **PASS** — no consent WARN/FAIL anywhere and zero defamation hits of any
  pattern.

Use this composite for both the chat summary's `Overall:` line and the
Output Format's `### Overall Verdict` line. Map it to the `### Verdict`
line the same way: FAIL → **EXPORT BLOCKED**, WARN → **RESOLVE BEFORE
EXPORT**, PASS → **EXPORT CLEAR**.

`/storyforge:export-engineer`'s Step 0 gate calls `check_memoir_consent`
directly and reads only its consent-only `overall` — it never sees the
Step 4 defamation scan. So whenever this skill's composite differs from
the tool's raw `overall` (i.e. whenever any defamation hit exists on an
otherwise consent-PASS or consent-WARN-only book), tell the user
explicitly: the **BLOCKED**/**FAIL** label here is this report's own
finding, not an automatic export gate — running `/storyforge:export-engineer`
will not stop on a D4 hit by itself. The hit must be resolved (rewrite,
removal, or the author's explicit informed acceptance of the risk) before
export, and nothing enforces that except this report and the user's own
follow-through.

Every non-PASS person gets their own fix presented individually in the
report, regardless of what the overall verdict is — a FAIL driven by one
person does not excuse skipping a WARN person's bullet elsewhere in the same
report.

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
dialogue) > D3 (unframed mind-reading) > D1 (compressed-time). D4 hits are
labeled **BLOCKED** in the report (see Output Format) — D1–D3 stay
risk-flags-with-a-rewrite, not blocked prose.

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

Append ` — BLOCKED` to the pattern line for D4 hits only (D1–D3 stay
unmarked). See Step 6 for how D4 hits fold into the `### Overall Verdict`
and `### Verdict` lines above, and for the limits of that label.

## Rules

- This skill is **memoir-only**. Do not run it on fiction books.
- A `refused` consent status is a **hard export block** — not a suggestion.
  The book cannot go to readers (even beta readers) in a form that identifies
  the refusing person. Anonymization is the only path forward short of removal.
- `not-asking` is a deliberate posture, not a bug. Present it as WARN so the
  author consciously confirms the decision before publication, but do not
  pressure them to ask. The `real-people-ethics.md` doc covers why someone
  might not ask (estranged relationship, abuser, deceased-but-survivors-hostile).
  This guard also holds if the user directly asks for your opinion ("should I
  ask him anyway? what do you think?") — reflect the WARN framing back (the
  documented reasoning is theirs to weigh) rather than opining for or against
  asking.
- Missing `person_category` always produces WARN even when consent is clean —
  an unclassified person is an unreviewed risk.
- Defamation patterns D1–D4 are risk flags, not verdicts. Most instances are
  fixable with a single-sentence reframe. Only D4 (per-se-defamatory imputation)
  warrants treating the passage as blocked prose (labeled **BLOCKED** in the
  report).
- Do not re-run the consent check automatically after a profile update — tell
  the user to run `/storyforge:memoir-ethics-checker` again once they have
  made the change.
- Load `real-people-ethics.md` before presenting any finding. The nuance in
  that document (public figure vs. private, "per se" defamation categories,
  anonymization patterns that work vs. don't) is what separates a useful risk
  flag from a false alarm. **Why:** the four-category model and D1–D4 definitions
  in that doc are required to grade findings accurately — without it, category
  misclassification produces misleading verdicts.
