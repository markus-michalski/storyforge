---
name: chapter-proofreader
description: |
  Check a chapter for spelling, grammar, and punctuation errors in the book's writing language.
  Explanations are delivered in the author's native language.
  Use when: (1) User says "Kapitel proofreaden", "proofread chapter", "Korrekturlesen",
  (2) After chapter-reviewer craft fixes are applied, before manuscript-checker.
  Works for both fiction and memoir books.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Chapter Proofreader

Checks language correctness — spelling, grammar, punctuation — on prose that is already
craft-stable (after chapter-reviewer). Does NOT check craft, voice, or cross-chapter patterns.

## Step 1 — Resolve Languages

Call MCP `get_author(slug)` to read the author profile.

**Writing language** (what rules to apply):
```
book_language (from book frontmatter)
  → preferred_writing_language (from author profile)
  → "en" (global fallback)
```

**Explanation language** (what language to write findings in):
```
native_language (from author profile)
  → "en" (fallback)
```

If `writing_language == native_language`: skip the explanation — just give the fix. Explanations
are for non-native writers who need context, not for native speakers who already know the rule.

## Step 2 — Load Book and Chapter

Call MCP `get_book_full(book_slug)` to read:
- `book_language` — authoritative per-book writing language
- Author slug (to cross-reference profile from Step 1)

Read the chapter draft directly:
- `{project}/chapters/{chapter_slug}/draft.md`

## Step 3 — Load Author Profile Context

From the author profile (already loaded in Step 1), extract:
- `avoid` list — intentional stylistic choices that are NOT errors (e.g. sentence fragments as voice)
- `sentence_style` — if "short-punchy", intentional fragments are expected, do not flag
- `vocabulary_level` — informs whether archaic or unusual words are intentional

**Rule:** If a pattern appears in the author's `avoid` list or is consistent with their documented
style, it is intentional — do not flag it.

## Step 4 — Run Proofreading Pass

### Spelling

- Typos and misspellings
- Wrong word forms (e.g. "affect" vs "effect", "lay" vs "lie")
- Homophone confusion (their/there/they're, your/you're, its/it's)
- Consistency: proper nouns spelled the same way as in earlier chapters (use canon from Step 2)

### Grammar

- Subject-verb agreement ("she don't" → "she doesn't")
- Tense consistency within a scene — unintentional tense shifts only; intentional mixed tense
  (e.g. present for reflection, past for events) must be honored
- Dangling and misplaced modifiers
- Pronoun-antecedent agreement
- Double negatives (unless stylistic/dialect)
- Run-on sentences and comma splices (two independent clauses joined only by a comma)
- Sentence fragments — flag ONLY if NOT consistent with `sentence_style: short-punchy` or
  the author's documented voice

### Punctuation

**English (`writing_language: en`):**
- Em dash (—) vs en dash (–) vs hyphen (-): em dash for interruption/parenthetical, en dash for
  ranges, hyphen for compound words
- Oxford comma: flag if inconsistently applied within the chapter (pick one style, keep it)
- Dialogue punctuation: comma before closing quote when followed by dialogue tag
  ("Hello," she said — not "Hello." she said); period inside closing quote (US English)
- Ellipsis: three dots only (…), not two or four, no space before
- Apostrophe errors: it's/its, possessives, contractions

**German (`writing_language: de`):**
- Comma rules (Nebensätze, Infinitivgruppen)
- Quotation marks: „..." not "..."
- Compound words written together vs apart
- Capitalization of nouns
- Comma before "und/oder" in compound sentences (not mandatory, but flag inconsistency)

**Other languages:** Apply the standard punctuation conventions of that language.

### Non-Native Writer Patterns (only when `writing_language != native_language`)

These patterns are common for non-native writers and worth flagging when `writing_language` is
not the author's mother tongue:

- Article misuse (a/an/the for non-native English writers)
- Preposition errors ("interested on" → "interested in", "depend of" → "depend on")
- False friends (words that look similar across languages but mean different things)
- Calque constructions (literal translations of idioms from the native language that don't work
  in the writing language)
- Modal verb misuse ("can" vs "may", "must" vs "have to", "will" vs "would")

## Step 5 — Output Report

**Report target: concise.** Only flag real errors. Do not pad the report with minor stylistic
observations that belong in chapter-reviewer. If a chapter is clean, say so in one line.

```markdown
## Proofreading Report: {Chapter Title}

**Writing language:** {en/de/...}
**Explanations in:** {de/fr/en/...}
**Non-native patterns checked:** {yes / no — native speaker}

---

### Spelling ({count} issues)

**[~Line/paragraph reference]** "{quoted phrase with error}"
→ Fix: "{corrected version}"
→ {Explanation in native_language — only for non-obvious rules}

### Grammar ({count} issues)

**[~Line/paragraph reference]** "{quoted phrase with error}"
→ Fix: "{corrected version}"
→ {Explanation in native_language}

### Punctuation ({count} issues)

**[~Line/paragraph reference]** "{quoted phrase with error}"
→ Fix: "{corrected version}"
→ {Explanation in native_language}

### Non-Native Patterns ({count} issues / "not checked — native speaker")

**[~Line/paragraph reference]** "{quoted phrase}"
→ Fix: "{corrected version}"
→ {Explanation in native_language — explain the rule and why the native pattern causes it}

---

### Summary

| Category | Issues |
|---|---|
| Spelling | {n} |
| Grammar | {n} |
| Punctuation | {n} |
| Non-native patterns | {n} |
| **Total** | **{n}** |

**Verdict:** CLEAN | ISSUES FOUND

**Suggested next step:**
- CLEAN → `/storyforge:manuscript-checker` (full-book pass)
- ISSUES FOUND → Fix listed items, then `/storyforge:manuscript-checker`
```

## Rules

- Flag errors, not style. If unsure whether something is intentional, check the author profile
  before flagging.
- Quote the actual text when flagging — never describe it vaguely.
- Explanations go in the author's `native_language`. If writing_language == native_language,
  skip explanations entirely — just give the fix.
- Do not flag craft issues (pacing, show-don't-tell, AI-tells) — those belong in chapter-reviewer.
- Do not flag cross-chapter repetitions — those belong in manuscript-checker.
- A clean chapter gets one line: "No issues found. Verdict: CLEAN."
