---
name: world-builder
description: |
  Build settings, magic systems, societies, and history for the story world.
  Use when: (1) User says "Welt", "world", "Setting", "Magic System",
  (2) For fantasy, sci-fi, supernatural, or historical genres.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<book-slug>"
---

# World Builder

## Prerequisites
- Load book data via MCP `get_book_full()`
- Load craft reference `world-building` via MCP `get_craft_reference()`
- Load genre README(s) — world-building depth varies by genre
- Read existing world files: `{project}/world/`

## When World-Building Matters
- **Essential:** Fantasy, Sci-Fi, Supernatural, Historical, Dark Fantasy
- **Important:** Horror (setting as character), Dystopian
- **Light touch:** Contemporary, Romance, Mystery, Drama, Literary
- **Skip:** Short stories in familiar settings

## Workflow

### Step 1: Scope Assessment
Ask the user:
- "How much does the world differ from our reality?"
- "Is the setting a character in this story, or just a backdrop?"
- "Are there systems (magic, technology, supernatural) that need rules?"

### Step 2: Setting Foundation
For `{project}/world/setting.md`:
- **Where:** Geography, climate, key locations
- **When:** Time period, era, season
- **Sensory palette:** What does this world look/sound/smell/feel like?
- **Key locations:** Create a table of important places with significance

### Step 3: Systems & Rules (if applicable)
For `{project}/world/rules.md`:

**Magic System** (reference `world-building.md` — Sanderson's Laws):
- Hard or Soft magic?
- Source: Where does magic come from?
- Cost: What does using magic cost?
- Limitations: What can't magic do?
- Users: Who can use it? How common?
- Social impact: How does magic shape society?

**Technology** (for sci-fi):
- What exists? What doesn't?
- Social consequences of the technology
- One big "what if" — everything else follows logically

**Supernatural Rules** (for supernatural/horror):
- What are the creatures' powers and weaknesses?
- Are the rules consistent? (No cherry-picking mythology)
- What do mortals know vs. not know?

### Step 4: Society & Culture
For `{project}/world/setting.md`:
- Social structure, class system, power dynamics
- Government/politics — who holds power and why?
- Religion/beliefs — how they shape behavior
- Economy — what's valuable, how people survive
- Cultural norms — what's acceptable, what's taboo

**Key principle:** Every cultural element should create CONFLICT, not just decoration.

### Step 5: History
For `{project}/world/history.md`:
- Key events that shaped the current world
- Wars, revolutions, discoveries, disasters
- ONLY what's relevant to the story — resist the urge to write an encyclopedia
- How the past explains present tensions

### Step 6: Glossary
For `{project}/world/glossary.md`:
- Terms unique to this world
- Place names with pronunciations if unusual
- Cultural concepts that need definition

### Step 7: Consistency Check
Create a consistency checklist in `{project}/world/rules.md`:
- [ ] Travel times between locations are realistic
- [ ] Technology level is consistent across the world
- [ ] Magic rules don't contradict each other
- [ ] Economy makes sense (who produces what?)
- [ ] Characters can't know things they shouldn't

Update book status to "World Built" via MCP `update_field()`.

## Rules
- ICEBERG PRINCIPLE: Know 100%, show 10%. The reader discovers; the author doesn't lecture.
- World-building through STORY, not through exposition chapters
- Every rule you create is a promise — you must keep it
- Consistency > realism. A consistent fantasy world feels more real than an inconsistent realistic one.
- If you can't explain how a cultural element creates conflict, cut it
