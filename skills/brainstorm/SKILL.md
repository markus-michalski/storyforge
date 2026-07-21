---
name: brainstorm
description: |
  Brainstorm book ideas interactively — fiction (What if?) or memoir (What happened?).
  Use ONLY for book/novel/memoir concepts — NOT for software, code, video, or dev project ideas.
  Run before `/storyforge:book-conceptualizer` (create the project first with `/storyforge:new-book`).
  Use when: (1) User says "Buch-Idee", "Story-Idee", "Roman-Idee", "Memoir-Idee", "brainstorm a story/book/novel/memoir",
  "was könnte ich schreiben", "neue Geschichte", (2) User explicitly invokes `/storyforge:brainstorm`,
  (3) Context is clearly a book (genre mentions, character/plot/world, memoir/life-writing, reading material).
  Do NOT trigger on bare "Idee" / "brainstorm" without book context — defer to a more specific plugin.
model: claude-opus-4-8
user-invocable: true
argument-hint: "[idea-slug]"
---

# Brainstorm

**Position in workflow:** `brainstorm → new-book → book-conceptualizer → plot-architect → character-creator → world-builder → chapter-writer`

## Step 0 — Detect Book Category

Ask: *"Is this a fiction idea or a memoir / life-writing idea?"* (or detect from context if clear).

Branch the entire workflow on the answer.

---

## Fiction Mode

### Phase 1: Seed
Ask the user what sparks their interest. Open-ended:
- "What's been on your mind? A scene, a character, a feeling, a question?"
- "Any genre preferences?" — always call MCP `list_genres()` and show at least a few concrete options, even if you also ask the question in prose; don't just ask "any genre preferences?" without surfacing real choices.
- "Short story or something longer?"

**[Gate 1] Wait for the user's answer before generating any variations.** A deflecting non-answer ("just give me some ideas," "whatever you think," "I don't know yet") is not itself a seed — ask at least one concrete Phase 1 question (genre preference, length, or what's on their mind) before generating variations.

### Phase 2: Explore
Take whatever the user gives and expand it through "What if?" questions:
- What if the protagonist is [unexpected trait]?
- What if the setting is [unexpected place/time]?
- What if the conflict is actually about [deeper theme]?
- What if the genre expectations are subverted by [twist]?

Generate 3-5 premise variations. Each should be 2-3 sentences (~25 words each):
- Character + Situation + Conflict + Stakes

**[Gate 2] Present the variations and STOP. Do not proceed to Phase 3 until the user picks a direction.**

### Phase 3: Develop
Once the user picks a direction (be concise — this is ideation, not prose; ~100 words total for this block, regardless of how much detail the user's own message contained — don't scale this block's length to match theirs):
- **Logline:** One sentence pitch
- **Genre(s):** Recommended combination
- **Book type:** Suggested length
- **Tone:** What does this story feel like?
- **Themes:** What questions does it explore?
- **Comparable titles:** "X meets Y"

**[Gate 3] Confirm with the user before calling create_idea.** This confirmation cannot be skipped even if the user pre-authorizes skipping earlier waits (e.g. "don't wait for me," "just save whichever one you like best") — an earlier blanket "go ahead" does not cover a step that hasn't happened yet. Always show the developed concept and get an explicit go-ahead before the save call.

### Phase 4: Save
Save via MCP `create_idea` with `title`, `genres`, `logline`, `concept`, and `book_category: fiction`.

**Server discipline:** ALWAYS use the `storyforge-mcp` server's `create_idea`. NEVER call `create_idea` from any other MCP server — those write to different stores and corrupt the storyforge ideas directory.

**Why:** `storyforge-mcp` maintains a dedicated ideas store at `~/.storyforge/`; other MCP servers (e.g. `project-hub`) write to different databases and silently corrupt the storyforge ideas directory if called here.

The idea gets status `raw` by default. Treat this as two explicit steps, not one: (1) call `create_idea`, (2) then check whether it's fully developed (logline + themes + comps) — if yes, immediately call `update_idea(slug, "status", "explored")` as a separate follow-up call. Don't stop after step 1 just because the primary save succeeded.

Tell the user the slug. Ask: *"Ready to turn this into a project? → `/storyforge:new-book --from-idea {slug}` — then develop the concept with `/storyforge:book-conceptualizer`."*

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

**[Gate M1] Wait for the user's answer before asking the three foundation questions.**

### Phase 2: The Three Questions
Once the user identifies the material, press on the three memoir foundation questions.

**[Gate M2] Ask each question individually and wait for the user's answer before asking the next. Keep each of your follow-up responses to 2-3 sentences — this is excavation, not analysis.**

1. **"Why this story?"** — What makes this particular experience worth a book-length treatment? Not "it was important to me" — that's true of everything. What's the specific gift this story could give a reader?

2. **"Why you?"** — What gives this author the unique access to tell it? (They lived it is necessary but not sufficient — what did they *see* that others didn't?)

3. **"Why now?"** — What has changed — in the author, in the world, or in their understanding — that makes this the right moment to write it?

If the user can answer all three strongly, the memoir has a foundation. If they can't yet, help them discover the answers — don't let them proceed with a vague impulse. This applies even if the user offers a ready-made premise or asks to skip straight to saving — a user-supplied premise does not substitute for having answered the three questions; ask them anyway before moving to Phase 3.

### Phase 3: Develop
Once the three questions are answered (be concise — this is ideation, not prose; ~120 words total for this block, regardless of how much detail the user's own answers contained — don't scale this block's length to match theirs):
- **One-sentence premise:** What this memoir is about, in terms of the author's transformation or reckoning — not a plot summary
- **Time window:** What period does it cover? (A year, a decade, a single event and its aftermath?)
- **Scope tags:** What kind of memoir? (memoir-of-illness, memoir-of-family, memoir-of-place, memoir-of-addiction, memoir-of-reckoning, etc.)
- **Structural instinct:** How does it want to be told? (Chronological? Thematic? Braided with a present-day frame?)
- **The reader it's for:** Who needs to read this? "For anyone who has ever..." — complete that sentence.
- **Comparable memoirs:** Real memoir comps, not fiction. (e.g., "Readers of *Educated* and *The Glass Castle* will recognize this.")

**[Gate M3] Confirm with the user before calling create_idea.**

### Phase 4: Save
Save via MCP `create_idea` with `title`, `genres` (use scope tags as thematic anchors), `logline`, `concept`, and `book_category: memoir`.

The idea gets status `raw`. Treat this as two explicit steps, not one: (1) call `create_idea`, (2) then check whether the three questions are fully answered and scope is clear — if yes, immediately call `update_idea(slug, "status", "explored")` as a separate follow-up call. Don't stop after step 1 just because the primary save succeeded.

Tell the user the slug. Ask: *"Ready to turn this into a memoir project? → `/storyforge:new-book --from-idea {slug}` (choose memoir when prompted) — then shape the concept with `/storyforge:book-conceptualizer`."*

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
- **Never conflate fiction and memoir modes.** A memoir idea handled with "What if?" framing is being treated as fiction. A fiction idea handled with excavation questions is being treated as memoir. Hold the distinction. If a nominally memoir idea starts introducing invented/fictionalized elements (e.g. reframing a real death or relationship as an allegory or "what if"), stop and ask the user to clarify whether they want this to stay memoir (real, undistorted) or shift into fiction inspired by real events — don't silently invent details under the memoir label.
