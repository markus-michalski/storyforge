---
name: brainstorm
description: |
  Brainstorm book ideas interactively — fiction (What if?) or memoir (What happened?).
  Use ONLY for book/novel/memoir concepts — NOT for software, code, video, or dev project ideas.
  Use when: (1) User says "Buch-Idee", "Story-Idee", "Roman-Idee", "Memoir-Idee", "brainstorm a story/book/novel/memoir",
  "was könnte ich schreiben", "neue Geschichte", (2) User explicitly invokes `/storyforge:brainstorm`,
  (3) Context is clearly a book (genre mentions, character/plot/world, memoir/life-writing, reading material).
  Do NOT trigger on bare "Idee" / "brainstorm" without book context — defer to a more specific plugin.
model: claude-opus-4-7
user-invocable: true
argument-hint: "[idea-slug]"
---

# Brainstorm

## Step 0 — Detect Book Category

Ask: *"Is this a fiction idea or a memoir / life-writing idea?"* (or detect from context if clear).

Branch the entire workflow on the answer.

---

## Fiction Mode

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
Save via MCP `create_idea` with `title`, `genres`, `logline`, `concept`, and `book_category: fiction`.

**Server discipline:** ALWAYS use the `storyforge-mcp` server's `create_idea`. NEVER call `create_idea` from any other MCP server — those write to different stores and corrupt the storyforge ideas directory.

The idea gets status `raw` by default. If fully developed (logline + themes + comps), call `update_idea(slug, "status", "explored")` immediately.

Tell the user the slug. Ask: "Ready to turn this into a project? → `/storyforge:new-book --from-idea {slug}`"

---

## Memoir Mode

Memoir brainstorming is fundamentally different from fiction. There is no "what if?" — only "what happened, and why does it matter to tell now?" The work here is not invention but *excavation and framing.*

### Phase 1: Seed
Ask open-ended questions to locate the material:
- "What period of your life keeps pulling at you?"
- "Is there a story you've told people at dinner a hundred times — but never written down?"
- "What happened to you that you don't fully understand yet?"
- "Who in your life made you who you are — for better or worse?"
- "What's the thing you survived that others might need to read about?"

Do NOT suggest topics. Wait for the user. Memoir ideas must come from the writer's own life — suggesting premises for memoir is inappropriate.

### Phase 2: The Three Questions
Once the user identifies the material, press on the three memoir foundation questions:

1. **"Why this story?"** — What makes this particular experience worth a book-length treatment? Not "it was important to me" — that's true of everything. What's the specific gift this story could give a reader?

2. **"Why you?"** — What gives this author the unique access to tell it? (They lived it is necessary but not sufficient — what did they *see* that others didn't?)

3. **"Why now?"** — What has changed — in the author, in the world, or in their understanding — that makes this the right moment to write it?

If the user can answer all three strongly, the memoir has a foundation. If they can't yet, help them discover the answers — don't let them proceed with a vague impulse.

### Phase 3: Develop
Once the three questions are answered:
- **One-sentence premise:** What this memoir is about, in terms of the author's transformation or reckoning — not a plot summary
- **Time window:** What period does it cover? (A year, a decade, a single event and its aftermath?)
- **Scope tags:** What kind of memoir? (memoir-of-illness, memoir-of-family, memoir-of-place, memoir-of-addiction, memoir-of-reckoning, etc.)
- **Structural instinct:** How does it want to be told? (Chronological? Thematic? Braided with a present-day frame?)
- **The reader it's for:** Who needs to read this? "For anyone who has ever..." — complete that sentence.
- **Comparable memoirs:** Real memoir comps, not fiction. (e.g., "Readers of *Educated* and *The Glass Castle* will recognize this.")

### Phase 4: Save
Save via MCP `create_idea` with `title`, `genres` (use scope tags as thematic anchors), `logline`, `concept`, and `book_category: memoir`.

The idea gets status `raw`. If three questions are fully answered and scope is clear, call `update_idea(slug, "status", "explored")`.

Tell the user the slug. Ask: "Ready to turn this into a memoir project? → `/storyforge:new-book --from-idea {slug}` (choose memoir when prompted)"

---

## Shared Phase 5: Resuming an idea (optional)
If the user returns to an existing idea:
1. Load via MCP `get_idea(slug)`
2. Check `book_category` in the idea frontmatter and continue in the correct mode
3. Update fields via `update_idea()` as the concept grows

## Rules
- **Fiction:** Be provocative and unexpected. Don't offer safe, generic ideas. Push toward specificity.
- **Memoir:** Never invent or suggest material. The writer's life is the only valid source. Your job is to help them locate and frame what's already there.
- Mix genres freely in fiction. In memoir, scope tags are anchors, not genre labels.
- Always save ideas — even ones the user is uncertain about might clarify later.
- Always resolve to a logline (fiction) or a one-sentence premise (memoir) before saving — a vague idea without a premise is hard to revisit.
- **Never conflate fiction and memoir modes.** A memoir idea handled with "What if?" framing is being treated as fiction. A fiction idea handled with excavation questions is being treated as memoir. Hold the distinction.
