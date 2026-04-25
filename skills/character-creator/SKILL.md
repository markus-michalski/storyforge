---
name: character-creator
description: |
  Develop deep, three-dimensional characters with arcs, voice, and motivation.
  Use when: (1) User says "Charakter", "character", "Figur",
  (2) After plot is outlined, to populate the story.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> [character-name]"
---

# Character Creator

## Prerequisites
- Load book data via MCP `get_book_full()`
- Load craft references via MCP `get_craft_reference()`:
  - `character-creation` (GMC, archetypes, wants vs. needs, flaws, motivation chains)
  - `character-arcs` (positive, negative, flat arcs)
  - `dialog-craft` (character voice differentiation)
- Load genre README(s) for genre-specific character expectations
- Read `{project}/plot/outline.md` and `{project}/plot/arcs.md` for story context

## Workflow

### Step 1: Character Role
Ask the user:
- Who is this character? (name, role: protagonist / antagonist / supporting / minor)
- What's their function in the story? (drives plot, mirrors theme, provides contrast, comic relief)

Create file via MCP `create_character()`.

### Step 2: Archetype — Starting Point
Identify the primary archetype as a starting point, then immediately look for the subversion:
- Which archetype do they resemble at first glance? (Hero, Mentor, Shadow, Trickster, Ally, Herald, Shapeshifter, Threshold Guardian)
- **More important:** How do they *break* the archetype? A Mentor with an addiction. A Hero who is physically weak. A Trickster who is genuinely wise.
- The subversion is what makes them specific. The archetype is what makes them recognizable.

### Step 3: The Core Triangle (GMC)
Work through Goal / Motivation / Conflict:
- **Goal (external):** What do they want? (concrete, visible, achievable or not by story's end)
- **Motivation:** WHY do they want it? (emotional, rooted in backstory — not "because it's important" but a specific wound or desire)
- **Conflict:** What stops them? (both external obstacles and internal resistance)

### Step 4: Want vs. Need
The most important character mechanic:
- **Want:** What they consciously pursue (external goal)
- **Need:** What they actually need to grow or change (internal truth they're avoiding)
- **The Lie:** The false belief that prevents them from getting what they need

Example: Want = revenge. Need = forgiveness. Lie = "Justice requires punishment."

### Step 5: The Motivation Chain — Dig Three Layers Deep
Surface motivations are rarely the true ones. Work with the user to find all three layers:
- **Surface:** What the character says they want (what they'd tell a stranger)
- **Deeper:** Why that actually matters (the emotional engine — ask "why does that matter to them?")
- **Deepest:** The core wound-driven need (ask "why?" again — this is what the story is really about for this character)

*Don't accept "she wants to prove herself" as the deepest layer. Keep digging: prove herself to whom? Why does that matter? What would happen if she didn't? The deepest layer is usually about survival, love, worth, or meaning.*

### Step 6: The Ghost — The Wound That Made Them
This is the most important backstory step. Ask the user:

*"What happened to this character BEFORE the story that made them who they are?"*

Guide the conversation:
- What single event (or sustained condition) changed them permanently?
- What did they lose, witness, survive, or fail at that they never fully recovered from?
- What false lesson did they draw from it? (This becomes The Lie in Step 4)
- The Ghost explains the Fatal Flaw. If you can't connect the wound to the flaw, dig deeper.

Apply the Iceberg Principle: know 100%, show 10%. The Ghost rarely appears on the page directly — it shapes behavior from below the surface.

Then map the broader backstory:
- **Upbringing:** Setting, income level, family dynamics, cultural background, core values instilled
- **Family Relationships:** Which were formative and how? What did they teach about love, trust, worth?
- **Friendships:** Most significant friendships — who shaped them, who was lost?
- **Adversaries:** Who looms in their memory as betrayer, nemesis, or threat?

### Step 7: Psychology
Work through the internal landscape:
- **The Lie:** What broken conclusion did they draw from The Ghost?
- **Fear (rational):** What do they consciously dread?
- **Phobias (irrational):** What makes them flinch in ways they can't fully explain?
- **Insecurities:** What are they secretly ashamed of? What would they never admit?
- **Value System:** What moral framework do they navigate by — even if it's flawed? Religious, philosophical, cultural, personal code?
- **Handling Emotions:** How do they process feelings? Suppress, explode, intellectualize, deflect, go silent? What does it look like at their emotional limit?

### Step 8: Fatal Flaw
Not just a weakness — a flaw that:
- **Actively causes problems** in the story (not just limits the character)
- **Connects to the theme** of the book
- **Has roots in The Ghost** — the flaw is usually an overcorrection to the wound
- **Must be overcome** (positive arc) or **embraced** (negative arc)

*Weakness vs. flaw: "She is shy" is a weakness. "She is so afraid of rejection that she sabotages every relationship before it can end on someone else's terms" is a flaw.*

### Step 9: Human Texture
The details that make them feel lived-in. These don't drive the plot — they make the character feel real:
- **Quirks:** Distinctive habits or mannerisms that feel uniquely them
- **Contradictions:** Opposing traits that coexist (the hard-boiled detective who cries at romantic comedies)
- **Habits:** Recurring behaviors, especially under pressure or stress
- **Pet Peeves:** What irritates them disproportionately?

*Tip: Contradictions are the most powerful of these. Real people are not unified. They contain multitudes.*

### Step 10: Life Context
Practical details that anchor them in the world:
- Job / Occupation (and how they feel about it — it's rarely neutral)
- Hobbies (what do they do when no one's watching?)
- Location (where do they live, and what does that say about them?)

### Step 11: Voice
Make this character sound DIFFERENT from every other character:
- **Vocabulary level:** (educated, street-smart, formal, casual, profession-specific jargon)
- **Sentence patterns:** (short and blunt, rambling, precise, avoidant)
- **Verbal tics:** (filler words, catchphrases, speech patterns)
- **What they DON'T say:** (topics they avoid, emotions they suppress)
- **Voice under stress:** How does their speech change when they're afraid, angry, or cornered?

Write a sample dialogue snippet (5–6 lines) that could only be this character. Do the "cover the name" test: could any other character in the book say this?

### Step 12: Arc Design
Based on `character-arcs.md`:
- **Arc type:** Positive (Lie → Truth), Negative (Truth → Lie), Flat (changes world, not self)
- **Arc beats** aligned to plot beats:
  1. Lie established, reinforced by backstory
  2. Lie challenged by story events
  3. Moment of truth (midpoint — glimpse of what they need)
  4. All Is Lost (the Lie or the Truth must win)
  5. Final choice (transformation complete or refused)

### Step 13: Key Relationships
Map relationships to other characters:
- What does this character want FROM each other character?
- What conflict exists between them?
- How do relationships change through the story?

### Step 14: Write Character File
Update the character file with all developed details via MCP `update_character()` or direct Write.
Update `{project}/characters/INDEX.md` with the new character.

After all major characters are created, update book status to "Characters Created".

## Rules
- NEVER create a "perfect" character — flaws drive stories
- Antagonists must believe they're RIGHT — no mustache-twirling villains
- Every character needs their own voice — do the "cover the name" test
- Backstory informs behavior but is NOT exposition — it lives below the surface
- Physical appearance should be SPECIFIC ("a scar running through his left eyebrow"), not generic ("tall, dark, handsome")
- If you can describe the character in one word, they're not deep enough
- The Ghost must connect to the Lie, which must connect to the Flaw — if the chain breaks, the character psychology is not coherent
- Contradictions are not inconsistencies — they are the mark of a real human being
