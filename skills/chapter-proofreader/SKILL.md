---
name: chapter-proofreader
description: |
  Check a chapter for spelling, grammar, and punctuation errors in the book's writing language.
  Explanations are delivered in the author's native language.
  Use when: (1) User says "Kapitel proofreaden", "proofread chapter", "Korrekturlesen",
  (2) After chapter-humanizer AI-tell pass, before manuscript-checker.
  Works for both fiction and memoir books.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Chapter Proofreader

Checks language correctness — spelling, grammar, punctuation — on prose that is already
craft-stable (after chapter-reviewer + chapter-humanizer). Does NOT check craft, voice, or cross-chapter patterns.

## Step 1 — Load Book and Chapter

Call MCP `get_book_full(book_slug)` to read:
- `language` — authoritative per-book writing language (the tool's JSON field is `language`, not
  `book_language`). It always returns a value: the server defaults it to `"en"` when the book's
  README has no `language:` key, so this field is never `""` or absent — see Step 2 for what that
  means for the writing-language fallback chain.
- `author` — the author slug, needed to load the author profile in Step 2.
- **Character/people roster (names)** — the canonical spelling source for the Step 4 proper-noun
  consistency check ("use canon from Step 1" refers to this roster). Extract every name from the
  response's `characters` key (fiction books) or `people` key (memoir books) and treat those
  spellings as authoritative when checking the current chapter. For memoir books, the canonical
  spelling is each person's anonymized/published name — never `real_name`, which exists in the
  data but must never appear in a proofreading report.

Read the chapter draft directly. Do not assume `{content_root}/projects/{book_slug}/` — series
books resolve under a different `content_root` subtree entirely. Call MCP
`resolve_path(book_slug, "chapters", "{chapter_slug}/draft.md")`, which returns
`{"path": ..., "exists": bool}` (or `{"error": ...}` for an invalid or content_root-escaping
path). If `exists: false`, stop and report that the chapter draft is missing rather than guessing
at a path. Otherwise `Read` the returned `path`.

## Step 2 — Resolve Languages

Call MCP `get_author(author_slug)` — the slug from Step 1 — to read the author profile.

**Writing language** (what rules to apply):
```
language (from Step 1's get_book_full() response)
  → preferred_writing_language (from author profile)
  → "en" (global fallback)
```

**Explanation language** (what language to write findings in):
```
native_language (from author profile)
  → "en" (fallback)
```

`language` from Step 1 always has a value — it defaults to `"en"` server-side when the book's
README omits `language:`, so a missing key is indistinguishable from an explicit `en`. In
practice this means the `preferred_writing_language` tier only fires when the README carries a
genuinely non-`en` `language:` value; there is currently no way to tell "language was never set"
apart from "language is English." The author-profile fields are different: `get_author()` defaults
both `native_language` and `preferred_writing_language` to `""` for an author who never set them —
check those two for falsy/empty.

If `writing_language == native_language`: skip the explanation — just give the fix. Explanations
are for non-native writers who need context, not for native speakers who already know the rule.

## Step 3 — Load Author Profile Context

From the author profile (already loaded in Step 2), extract:
- `avoid` list — patterns the author has explicitly banned from their own prose (e.g.
  `purple-prose`, `info-dumps`, `deus-ex-machina`). This is a ban-list, not a whitelist of
  intentional choices: a pattern's presence on `avoid` is a STRONGER reason to flag an instance of
  it, never a reason to skip flagging it.
- `sentence_style` — if "short-punchy", intentional fragments are expected, do not flag
- `vocabulary_level` — informs whether archaic or unusual words are intentional

**Rule:** If a pattern is consistent with the author's documented style (`sentence_style`,
`vocabulary_level`, or a character's documented voice — see Step 4's double-negative exemption),
it is intentional — do not flag it. Never treat membership in the `avoid` list as a reason NOT to
flag something; that inverts what the field means.

## Step 4 — Run Proofreading Pass

### Spelling

- Typos and misspellings
- Wrong word forms (e.g. "affect" vs "effect", "lay" vs "lie")
- Homophone confusion (their/there/they're, your/you're, its/it's)
- Consistency: proper nouns spelled the same way as in earlier chapters. Character/people names —
  use the canonical roster from Step 1. Other proper nouns (place names, invented terms, glossary
  entries) are out of scope for cross-chapter canon-checking in this skill, but still flag if the
  SAME term is spelled two different ways within this chapter's own draft.

### Grammar

- Subject-verb agreement ("she don't" → "she doesn't")
- Tense consistency within a scene — unintentional tense shifts only; intentional mixed tense
  (e.g. present for reflection, past for events) must be honored
- Dangling and misplaced modifiers
- Pronoun-antecedent agreement
- Double negatives — flag them, UNLESS the specific instance matches a character's documented
  dialect or speech pattern (the character file's `## Voice` section, or the author profile's
  `dialog_style` field) or is otherwise consistent with the author's documented voice. Never treat
  membership in the author's `avoid` list as an exemption — `avoid` is what the author has banned,
  so a double negative there is a stronger reason to flag it, not a weaker one. A dialect exemption
  for one character's dialogue does not extend to narration or to other characters not named in
  that exemption.
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

**If the chapter has no spelling, grammar, or punctuation issues at all, skip the full template
below and output just:**
```
No issues found. Verdict: CLEAN.
Writing language: {en/de/...} | Explanations in: {de/fr/en/...} | Non-native patterns checked: {yes/no}

Suggested next step: `/storyforge:manuscript-checker` (full-book pass)
```

**Report target: concise.** Only flag real errors. Do not pad the report with minor stylistic
observations that belong in chapter-reviewer. If a chapter is clean, say so in the block above.

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
- A clean chapter gets the short CLEAN block from Step 5 — verdict line + language header +
  next-step pointer — not the full template.
