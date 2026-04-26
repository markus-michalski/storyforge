---
name: brainstorm
description: |
  Brainstorm FICTION/BOOK/STORY ideas interactively. Develop premises, explore genres, ask "what if?" questions.
  Use ONLY for fiction/book/novel/story concepts — NOT for software, code, video, or dev project ideas.
  Use when: (1) User says "Buch-Idee", "Story-Idee", "Roman-Idee", "Fiction-Idee", "brainstorm a story/book/novel",
  "was könnte ich schreiben", "neue Geschichte", (2) User explicitly invokes `/storyforge:brainstorm`,
  (3) Context is clearly fiction (genre mentions, character/plot/world, reading material).
  Do NOT trigger on bare "Idee" / "brainstorm" without fiction context — defer to a more specific plugin.
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
Save the idea via the storyforge MCP server: call `mcp__plugin_storyforge_storyforge-mcp__create_idea`
with `title`, `genres`, `logline`, and `concept` body.

**Server discipline:** ALWAYS use the `storyforge-mcp` server's `create_idea` (writes to
`{content_root}/ideas/{slug}.md` as Markdown + YAML frontmatter). NEVER call `create_idea` from any
other MCP server (e.g. `vidcraft-mcp.create_idea`, `mm-dev-toolkit-mcp.tool_create_idea`) —
those write to different stores and corrupt the storyforge ideas directory.

The idea gets status `raw` by default. If the user has fully developed it (logline + themes + comps),
call `mcp__plugin_storyforge_storyforge-mcp__update_idea(slug, "status", "explored")` immediately after saving.

Tell the user the slug so they can reference it later: "Saved as `{slug}`."

Ask: "Ready to turn this into a project? → `/storyforge:new-book --from-idea {slug}`"
Or: "Want to let it marinate? Check your ideas with `/storyforge:ideas`."

### Phase 5: Resuming an idea (optional)
If the user returns to an existing idea (e.g. "continue the clockmaker idea"):
1. Load it via `mcp__plugin_storyforge_storyforge-mcp__get_idea(slug)`
2. Continue development from where it left off
3. Update fields via `mcp__plugin_storyforge_storyforge-mcp__update_idea()` as the concept grows

## Rules
- Be provocative and unexpected. Don't offer safe, generic ideas.
- Push the user toward specificity — "a vampire story" is not enough. WHOSE vampire story? What makes it THEIRS?
- Mix genres freely. The best ideas live at intersections.
- Always save ideas — even rejected ones might resurface later.
- Always fill in the logline before saving — a vague idea without a logline is hard to revisit.
