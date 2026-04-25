---
name: brainstorm
description: |
  Brainstorm book ideas interactively. Develop premises, explore genres, ask "what if?" questions.
  Use when: (1) User says "Idee", "brainstorm", "was könnte ich schreiben",
  (2) User wants to explore story concepts before committing.
model: claude-opus-4-7
user-invocable: true
---

# Brainstorm

## Workflow

### Phase 1: Seed
Ask the user what sparks their interest. Open-ended:
- "What's been on your mind? A scene, a character, a feeling, a question?"
- "Any genre preferences?" (show genres via MCP `list_genres()`)
- "Short story or something longer?"

### Phase 2: Explore
Take whatever the user gives and expand it through "What if?" questions:
- What if the protagonist is [unexpected trait]?
- What if the setting is [unexpected place/time]?
- What if the conflict is actually about [deeper theme]?
- What if the genre expectations are subverted by [twist]?

Generate 3-5 premise variations. Each should be 2-3 sentences:
- Character + Situation + Conflict + Stakes

### Phase 3: Develop
Once the user picks a direction:
- **Logline:** One sentence pitch
- **Genre(s):** Recommended combination
- **Book type:** Suggested length
- **Tone:** What does this story feel like?
- **Themes:** What questions does it explore?
- **Comparable titles:** "X meets Y"

### Phase 4: Save
Save the idea via MCP `create_idea()` with title, genres, logline, and concept body.

The idea gets status `raw` by default. If the user has fully developed it (logline + themes + comps),
call `update_idea(slug, "status", "explored")` immediately after saving.

Tell the user the slug so they can reference it later: "Saved as `{slug}`."

Ask: "Ready to turn this into a project? → `/storyforge:new-book --from-idea {slug}`"
Or: "Want to let it marinate? Check your ideas with `/storyforge:ideas`."

### Phase 5: Resuming an idea (optional)
If the user returns to an existing idea (e.g. "continue the clockmaker idea"):
1. Load it via MCP `get_idea(slug)`
2. Continue development from where it left off
3. Update fields via `update_idea()` as the concept grows

## Rules
- Be provocative and unexpected. Don't offer safe, generic ideas.
- Push the user toward specificity — "a vampire story" is not enough. WHOSE vampire story? What makes it THEIRS?
- Mix genres freely. The best ideas live at intersections.
- Always save ideas — even rejected ones might resurface later.
- Always fill in the logline before saving — a vague idea without a logline is hard to revisit.
