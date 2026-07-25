---
name: sensitivity-reader
description: |
  Check for problematic representations, stereotypes, and harmful tropes.
  Use when: (1) User says "sensitivity", "sensitivity read", "problematisch?",
  "Stereotype", "Klischee", "Repräsentation", "harmful tropes", "beleidigend",
  "heikle Themen", "content warning", "Trigger-Warnung",
  (2) Story involves marginalized groups, trauma, or controversial themes.
model: claude-opus-4-8
user-invocable: true
argument-hint: "<book-slug> [chapter-slug]"
---

# Sensitivity Reader

## Prerequisites — MANDATORY LOADS (execute in this order)

0. **Resolve book, scope, and category.** If `book-slug` wasn't given, call MCP `list_books()` and ask the user to pick one — never guess or assume a recently discussed project. Call MCP `get_book_full(book_slug)` and read `book_category` — keep this result, steps 1-2 read from it too. If `chapter-slug` wasn't given, the check runs at whole-book scope: every slug in the result's `chapters_data` dict where `has_draft` is true (not just chapter 1) — say so in the response rather than silently narrowing scope. `chapters_data` is a slug → metadata dict; it carries no file paths (see step 3).

1. **Character/people context** — from the `get_book_full` result already fetched in step 0: fiction books expose `characters` (slug → `{name, role, status, age, gender, description}` — a frontmatter index, not the files themselves); memoir books expose `people` (slug → `{name, relationship, person_category, consent_status, anonymization, real_name, status, description}` — no `role` or arc fields, memoir people aren't positioned as protagonist/antagonist). **Why:** Category 1/2 findings need backstory and arc detail this index alone doesn't carry. For any character/person a finding will actually name, call `resolve_path(book_slug, "characters")` (or `"people"` for memoir) and `Read` that individual `.md` file before writing the finding.

   For memoir books: Category 2's tropes ("Bury Your Gays", "Fridging", predatory bisexual, etc.) are fiction-shaped constructs built on `role`/arc positioning that the `people` schema doesn't have — reframe around `relationship` instead (e.g. is this real person's on-page death or suffering framed only to serve someone *else's* arc, independent of what actually happened). Real-people consent, defamation, and anonymization concerns are a different skill's job — route those to `/storyforge:memoir-ethics-checker` and say so in the report rather than silently absorbing or skipping them.

   "Identity present ≠ trope triggered" applies to every bullet in Category 2, not just "Bury Your Gays" — check the specific causal/framing pattern each trope names, not the mere presence of the identity.

2. **`lgbtq-craft` reference** via MCP `get_craft_reference('lgbtq-craft')` — load it if the step-0 `get_book_full` result's `genres` list contains `lgbtq`, OR if any character/person file read in step 1 establishes an on-page LGBTQ+ identity. **Why:** Identity-representation evaluation framework — distinguishes authentic representation from token/trope patterns. Without it, the LGBTQ+ section of the report is generic. Do not gate this on the character index's `gender` field — it carries no orientation/identity vocabulary and will false-negative on exactly the books that need the reference most.

3. **Relevant chapter drafts.** For a given `chapter-slug`: call MCP `resolve_path(book_slug, "chapters", "{chapter}/draft.md")` and `Read` it. For whole-book scope: for every drafted-chapter slug identified in step 0, call `resolve_path(book_slug, "chapters", "{slug}/draft.md")` and `Read` each in turn — `get_book_full` itself never returns a path, only `resolve_path` does. **Why:** Sensitivity findings must be grounded in specific passages with line references — abstract concerns are not actionable.

## Check Categories

### 1. Representation
- Are marginalized characters three-dimensional, not tokens?
- Do they have agency, goals, arcs — or exist only to serve the protagonist?
- Is their identity their ONLY trait, or one aspect of a full character?

### 2. Harmful Tropes
- "Bury Your Gays" — LGBTQ+ characters killed for straight character development
- "Magical Negro" / "Wise Native" — minorities existing only to help white protagonist
- "Fridging" — women killed/harmed only to motivate a male character
- Redemption through suffering — marginalized characters must suffer to "earn" happiness
- Predatory bisexual, tragic queer, sexless ace stereotypes

### 3. Cultural Accuracy
- Are cultural practices depicted accurately?
- Are stereotypes perpetuated or subverted?
- Is the author's perspective acknowledged?

### 4. Trauma Handling
- Is trauma depicted with appropriate weight?
- Is it gratuitous or does it serve the narrative?
- Are content warnings appropriate?

### 5. Power Dynamics
- Are power imbalances (age, status, supernatural) acknowledged?
- Is consent clear in intimate scenes?
- Are toxic dynamics romanticized or examined?

## Output

**Single-chapter scope: max ~800 Wörter total, 3-5 bullets per category as cap.** If a category has zero findings, state it in one line and move on. Severity stratification is the signal. If a category's real findings exceed the cap, keep the most severe / most clearly-evidenced ones and say more exist rather than truncating silently.

**Whole-book scope is a triage pass, not an exhaustive per-instance list.** Budget: max ~1500 Wörter total, 3-5 bullets per category — but each bullet now names a *pattern or cluster* (e.g. "the Fridging setup in ch. 4 recurs in ch. 11 and ch. 19") rather than one bullet per isolated instance, and explicitly names which chapters need a dedicated single-chapter run (`/storyforge:sensitivity-reader <book-slug> <chapter-slug>`) for a full-detail pass. Do not silently compress a 40-chapter manuscript's worth of findings into 25 bullets without saying that's what happened.

Report findings as: CONCERN (discuss) / FLAG (reconsider) / ISSUE (revise). Calibrate by evidence strength and harm: ISSUE = the pattern is clear and reader-facing harm is real — the mitigating context present, if any, does not neutralize it (e.g. a textbook Fridging case is still ISSUE even with an aftermath scene, if the aftermath centers the male character's grief rather than the victim); FLAG = a real pattern that's more isolated, debatable, or meaningfully softened by framing/context; CONCERN = a minor, single-instance, or easily-fixed detail worth a conversation rather than a block. Do not require the *total absence* of mitigating context for ISSUE — that standard is met by almost no authored fiction and would make FAIL practically unreachable.
Always pair every finding with a concrete alternative — "this is problematic" without an alternative is not actionable.

### Final verdict line

End the report with a single uppercase line that an aggregator can parse. The verdict is scoped to what was actually checked — one line for a single-chapter run, one line for the whole book on a whole-book run (not per-chapter) — say which scope it covers if that isn't already obvious from the report header:

```
VERDICT: PASS | WARN | FAIL
```

Mapping (per the gate contract — see `reference/gate-contract.md`):

- **PASS** — no CONCERN/FLAG/ISSUE items.
- **WARN** — CONCERN or FLAG items only — discuss before publication, but no hard block.
- **FAIL** — at least one ISSUE — revise before publication.

## Rules
- This is advisory, not censorship. The author makes the final call — on what to DO with a finding, not on whether it gets reported. Report genuine findings honestly even if the user frames the content as fine or asks not to flag something; advisory means the author decides the response, not that the check suppresses itself on request.
- Sensitivity ≠ sanitizing. Dark themes are valid when handled with care.
- Flag genuine concerns; calibrate severity rather than overcorrecting on every edge case.
