---
name: world-builder
description: |
  Build settings, magic systems, societies, and history for the story world.
  Use when: (1) User says "Welt", "world", "Setting", "Magic System",
  (2) For fantasy, sci-fi, supernatural, or historical genres.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug>"
---

# World Builder

## Step 0 — Resolve Book Category

Read `book_category` from MCP `get_book_full(book_slug)`. Treat missing as `fiction`.

- `fiction` → standard world-building workflow below
- `memoir` → **Setting Notes Mode** (see end of this skill) — memoir uses real places, not invented worlds

## Iceberg Principle (Fiction Core Operating Mode)

**Show ~10% of the world in-story. Keep the other 90% in `{project}/world/` for consistency checks.** The world files are the author's reference, not the reader's experience. Avoid info-dumps in prose — exposition disguised as world-building is the most common AI-tell in fantasy/sci-fi drafts. Every world fact you generate here either pays off in conflict, character, or atmosphere — or it stays below the surface as continuity ballast.

## Prerequisites — MANDATORY LOADS (Fiction)
- **Book data** via MCP `get_book_full()`. **Why:** Genre, premise, characters — world-building must serve the story, not exist in parallel to it.
- **`world-building` craft reference** via MCP `get_craft_reference()`. **Why:** Sanderson's Laws, iceberg principle, conflict-driven culture — the framework Steps 3-5 apply.
- **Genre README(s)**. **Why:** Fantasy needs full world rules, contemporary needs almost none — depth scales with genre.
- Read existing world files: `{project}/world/`.

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
- Include only what's relevant to the story. Encyclopedia mode produces dead world-building.
- How the past explains present tensions

Target: ~500-1000 Wörter total für die History-Sektion, als Richtwert. Wenn die Story eine 5000-jährige Imperien-Geschichte braucht, darf es mehr werden — aber dann mit klarer Verbindung zu Plot-Konflikten.

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

## Rules (Fiction)
- ICEBERG PRINCIPLE: Know 100%, show ~10% in-story. The reader discovers through scene; the author keeps the rest as reference.
- World-building lands through STORY — character action, dialogue, sensory detail. Exposition chapters break the spell.
- Every rule you create is a promise — keep it. Magic systems that bend mid-book signal authorial cheating.
- Consistency > realism. A consistent fantasy world feels more real than an inconsistent realistic one.
- If you can't explain how a cultural element creates conflict, cut it from the story (keep it in setting.md only if it's load-bearing for continuity).

---

## Memoir Mode — Setting Notes

Memoir does not invent worlds — it recovers real places. The world-builder skill in memoir mode serves a different purpose: **sensory anchoring and period accuracy**, so that remembered environments can be rendered with specificity rather than generic reconstruction.

Memoir books typically have no `world/` directory — settings live in `research/sources.md` and within chapter prose. This skill creates or enriches `research/notes/setting-{location-slug}.md` files for each significant place.

### Prerequisites (Memoir)
- **Book data** via MCP `get_book_full()`.
- **Memoir craft** — Read `book_categories/memoir/craft/scene-vs-summary.md` via `get_book_category_dir("memoir")`. **Why:** Setting in memoir is dramatized through scene, not described in exposition. The notes here feed scene-writing, not an info-dump.
- Read existing `research/sources.md` and any existing setting notes.

### Workflow (Memoir)

#### Step 1: Identify Significant Places
Ask the user: "Which locations in your memoir are emotionally or narratively significant? List them — even briefly."

For each location, assess whether it deserves a setting note:
- Places where key events happen (ALWAYS document)
- Places the memoirist returned to repeatedly (document)
- Places that shaped the author's inner life (document)
- Background/transit locations (skip — a paragraph in prose is enough)

#### Step 2: For Each Significant Place — Four Questions
Work through the four questions that unlock sensory specificity:

1. **What is the physical truth of this place?** (Layout, size, material, light — what would a photograph show?)
2. **What does it sound and smell like?** (The non-visual senses that photograph can't capture — what will readers hold onto?)
3. **How does it feel to be there?** (Temperature, texture, emotional register — what does it do to a person's body to be in this space?)
4. **What has changed?** (If the author revisits this place as an adult, what is different? What is gone? What remained? The gap between then and now is often more powerful than the place itself.)

If the memoirist doesn't remember — say so in the notes with `[unverified]`. Do not invent. Gaps can be used explicitly in prose ("I no longer remember whether the kitchen smelled of...").

#### Step 3: Period Research (Optional)
If a place existed in a specific historical period and factual accuracy matters:
- Research the era via WebSearch (architecture, signage, businesses, transport of the time)
- Note period-accurate sensory details that the memoirist may not remember consciously but that were physically true
- Mark as `[researched]` to distinguish from direct memory

#### Step 4: Write Setting Notes
Save to `{project}/research/notes/setting-{location-slug}.md`:

```markdown
---
location: "{Name}"
period: "{Years/decade covered}"
status: direct-memory | researched | unverified
---

# Setting Notes: {Name}

## Physical Truth
[What the place looks like — layout, materials, light]

## Sensory Palette
[Sound, smell, texture, temperature]

## Felt Sense
[What it does to a person to be there]

## Period Accuracy
[Notes from research on era-specific details — tagged [researched]]

## The Gap (Then vs. Now)
[What changed, what remained — only if relevant to the memoir]

## Unverified / Gaps
[What the author doesn't remember — to be handled explicitly in prose]
```

#### Step 5: Connect to Sources
Add real-world sources to `{project}/research/sources.md` — photographs, maps, local histories, newspaper archives that informed the notes.

### Rules (Memoir Setting Notes)
- **Never invent.** If a sensory detail is not remembered and not researched, leave a gap. A memoirist who fills gaps with plausible fiction is writing unreliable memoir — and readers can tell.
- **Distinguish memory from research.** Use `[remembered]` and `[researched]` tags when mixing sources — especially for places the author hasn't seen in decades.
- **Settings serve scenes.** These notes exist to make scenes vivid and verifiable, not to be read by the reader. The prose is the output; the notes are the scaffold.
- **No Travel Matrix.** Memoir does not need a Travel Matrix — real-world geography is not invented. If transit times matter, note real-world facts (the drive from X to Y takes N hours by car circa 1980s).
