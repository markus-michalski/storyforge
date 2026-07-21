---
name: genre-creator
description: |
  Create new genre definitions or genre-mix combinations.
  Use when: (1) User says "neues Genre", "genre-mix", "genre creator",
  (2) User needs a genre combination that doesn't exist yet (e.g., "lgbtq-supernatural").
model: claude-opus-4-8
user-invocable: true
argument-hint: "<genre-name>"
---

# Genre Creator

## Workflow

### Step 1: Identify Genre Type
Is this a:
- **New base genre** — A standalone genre not yet covered
- **New mix genre** — A combination of existing genres (e.g., lgbtq-supernatural)
- **New subgenre** — A variant of an existing genre

**Wait:** Confirm genre type with user before proceeding to research. This gate applies even if the
user asks to skip it directly — explain briefly why the check stays, then continue.

### Step 1.5: Validate Before Proceeding
Before researching or writing anything:
- Call MCP `list_genres()` and check whether the target genre name/slug already exists. If it does,
  stop and ask the user: pick a different name, or confirm they actually want a subgenre/variant of
  the existing genre (→ Step 1a) instead of overwriting it. Never silently overwrite an existing
  genre's README.
- For mix genres, call MCP `get_genre()` on each parent now. If either call returns a not-found
  error, stop and tell the user which parent doesn't exist yet — offer to create it as a base genre
  first, or reconsider the mix. Don't proceed to research or writing with a fabricated stand-in for
  a parent that doesn't actually exist.
- Match the user's own phrasing of a parent genre against the real slugs returned by `list_genres()`
  before calling `get_genre()` — don't guess a slugification (e.g. the real slug is `sci-fi`, not a
  guessed `scifi` or `science-fiction`).

### Step 1a: For Subgenres — Special Handling
A subgenre is a variant of ONE existing parent genre. Every genre's own template already has a
`## Subgenres` table for exactly this (see e.g. `genres/thriller/README.md`'s Legal/Domestic/etc.
rows) — so by default, add a row to the PARENT genre's existing Subgenres table
(`genres/{parent}/README.md`), not a new standalone `genres/{slug}/README.md`. Only create a full
standalone README if the user explicitly confirms the subgenre is substantial enough to need its own
template — ask before doing that, don't assume it.

### Step 2: Research
For new genres or mixes:
- Use WebSearch to research conventions, key authors, example works
- Load parent genre README(s) via MCP `get_genre()` if this is a mix (already done in Step 1.5 —
  don't re-fetch)
- Load corresponding genre-craft reference via MCP `get_craft_reference()` if available

**Wait:** Show research summary (key conventions, tensions, 3-5 example works found) and ask user to
confirm direction before writing README. This gate applies even if the user asks to skip it directly
— explain briefly why the check stays, then continue.

### Step 3: Create README
Write `{plugin_root}/genres/{genre-name}/README.md` following the standard genre template:

```markdown
# {Genre Name}

## Overview (~100 words)
## Characteristics (table, 5-8 rows)
## Key Conventions (~150 words)
## Common Tropes (Use Wisely) (3-5 entries, 1-2 sentences each)
## Anti-Patterns (Avoid) (3-5 entries, 1-2 sentences each)
## Recommended Story Structures (~100 words, max 3 structures)
## Subgenres (table, min 3 rows)
## Example Authors & Works (table, min 5 rows)
## Genre-Mixing Notes (~100 words)
```

### Step 4: For Mix Genres — Special Handling
When creating a genre mix (e.g., "lgbtq-supernatural"):
1. Both parent genres are already loaded from Step 1.5 — don't re-fetch
2. Identify **synergies** (what works well together)
3. Identify **tensions** (conventions that might conflict)
4. Define **mix-specific conventions** (e.g., power-dynamic consent for paranormal-romance)
5. Add **Example Works** that demonstrate the combination
6. Add **Parent Genre** field in characteristics table

### Step 5: Report
- Show the new genre README to the user
- Confirm it's saved
- It's now available for new book projects

## Rules
- Genre READMEs follow a STRICT template — consistency across all genres
- Mix genres must reference their parent genres explicitly
- At least 5 example authors/works per genre
- Anti-patterns are CRUCIAL and MANDATORY — always include 3-5 entries, even if the user asks to
  omit them; briefly explain why before continuing
- Never create a genre whose name/slug already exists (Step 1.5) — flag the collision instead
- Never write a mix genre using a parent that doesn't actually exist (Step 1.5) — flag it instead
