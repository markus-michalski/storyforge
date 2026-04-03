---
name: character-creator
description: |
  Develop deep, three-dimensional characters with arcs, voice, and motivation.
  Use when: (1) User says "Charakter", "character", "Figur",
  (2) After plot is outlined, to populate the story.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<book-slug> [character-name]"
---

# Character Creator

## Prerequisites
- Load book data via MCP `get_book_full()`
- Load craft references via MCP `get_craft_reference()`:
  - `character-creation` (GMC, archetypes, wants vs. needs, flaws)
  - `character-arcs` (positive, negative, flat arcs)
  - `dialog-craft` (character voice differentiation)
- Load genre README(s) for genre-specific character expectations
- Read `{project}/plot/outline.md` and `{project}/plot/arcs.md` for story context

## Workflow

### Step 1: Character Role
Ask the user:
- Who is this character? (name, role: protagonist/antagonist/supporting/minor)
- What's their function in the story? (drives plot, mirrors theme, provides contrast)

Create file via MCP `create_character()`.

### Step 2: The Core Triangle (GMC)
Work through Goal/Motivation/Conflict:
- **Goal (external):** What do they want? (concrete, visible, achievable)
- **Motivation:** WHY do they want it? (emotional, rooted in backstory)
- **Conflict:** What stops them? (both external obstacles and internal resistance)

### Step 3: Want vs. Need
The most important character mechanic:
- **Want:** What they consciously pursue (external goal)
- **Need:** What they actually need to grow/change (internal truth)
- **The Lie:** The false belief that prevents them from getting what they need

Example: Want = revenge. Need = forgiveness. Lie = "Justice requires punishment."

### Step 4: Fatal Flaw
Not just a weakness — a flaw that:
- Actively causes problems in the story
- Connects to the theme
- Has roots in the backstory/wound
- Must be overcome (positive arc) or embraced (negative arc)

### Step 5: Backstory — The Wound
Ask: "What happened to this character BEFORE the story that made them who they are?"
- Apply the Iceberg Principle: know 100%, show 10%
- The wound should explain the Lie they believe
- Don't info-dump backstory — reveal through behavior and reactions

### Step 6: Voice
Make this character sound DIFFERENT from every other character:
- **Vocabulary level:** (educated, street-smart, formal, casual)
- **Sentence patterns:** (short and blunt, rambling, precise)
- **Verbal tics:** (filler words, catchphrases, speech avoidance)
- **What they DON'T say:** (topics they avoid, emotions they suppress)

Write a sample dialog snippet (5-6 lines) demonstrating their voice.

### Step 7: Arc Design
Based on `character-arcs.md`:
- **Arc type:** Positive (Lie → Truth), Negative (Truth → Lie), Flat (changes world)
- **Arc beats** aligned to plot beats:
  1. Lie established
  2. Lie challenged
  3. Moment of truth (midpoint)
  4. All is lost (crisis)
  5. Final choice (climax)

### Step 8: Relationships
Map relationships to other characters:
- What does this character want FROM each other character?
- What conflict exists between them?
- How do relationships change through the story?

### Step 9: Write Character File
Update the character file with all developed details.
Update `{project}/characters/INDEX.md` with the new character.

After all major characters are created, update book status to "Characters Created".

## Rules
- NEVER create a "perfect" character — flaws drive stories
- Antagonists must believe they're RIGHT — no mustache-twirling villains
- Every character needs their own voice — do the "cover the name" test
- Backstory informs behavior but is NOT exposition
- Physical appearance should be SPECIFIC, not generic ("tall, dark, handsome" = lazy)
- If you can describe the character in one word, they're not deep enough
