---
name: genre-creator
description: |
  Create new genre definitions or genre-mix combinations.
  Use when: (1) User says "neues Genre", "genre-mix", "genre creator",
  (2) User needs a genre combination that doesn't exist yet (e.g., "lgbtq-supernatural").
model: claude-opus-4-7
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

### Step 2: Research
For new genres or mixes:
- Use WebSearch to research conventions, key authors, example works
- Load parent genre README(s) via MCP `get_genre()` if this is a mix
- Load corresponding genre-craft reference via MCP `get_craft_reference()` if available

### Step 3: Create README
Write `{plugin_root}/genres/{genre-name}/README.md` following the standard genre template:

```markdown
# {Genre Name}

## Overview
## Characteristics (table)
## Key Conventions
## Common Tropes (Use Wisely)
## Anti-Patterns (Avoid)
## Recommended Story Structures
## Subgenres (table)
## Example Authors & Works (table)
## Genre-Mixing Notes
```

### Step 4: For Mix Genres — Special Handling
When creating a genre mix (e.g., "lgbtq-supernatural"):
1. Load BOTH parent genres
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
- Anti-patterns are CRUCIAL — they prevent genre clichés
