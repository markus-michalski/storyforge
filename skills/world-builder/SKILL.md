---
name: world-builder
description: |
  Build settings, magic systems, societies, and history for the story world.
  For fantasy/sci-fi/supernatural/historical: run after `/storyforge:character-creator`, before `/storyforge:chapter-writer`. Optional for contemporary, romance, mystery, drama, literary.
  Use when: (1) User says "Welt", "world", "Setting", "Magic System",
  (2) For fantasy, sci-fi, supernatural, or historical genres.
model: claude-opus-4-8
user-invocable: true
argument-hint: "<book-slug>"
---

# World Builder

**Position in workflow:** Optional. For fantasy/sci-fi/supernatural/historical: `character-creator → world-builder → chapter-writer`. Skip for contemporary, romance, mystery, drama, literary.

## Step 0 — Resolve Book Category

Read `book_category` from MCP `get_book_full(book_slug)`. Treat missing as `fiction`.

- `fiction` → standard world-building workflow below
- `memoir` → **Setting Notes Mode** (see end of this skill) — memoir uses real places, not invented worlds

## Iceberg Principle (Fiction Core Operating Mode)

**Show ~10% of the world in-story. Keep the other 90% in `{project}/world/` for consistency checks.** The world files are the author's reference, not the reader's experience. Avoid info-dumps in prose — exposition disguised as world-building is the most common AI-tell in fantasy/sci-fi drafts. Every world fact you generate here either pays off in conflict, character, or atmosphere — or it stays below the surface as continuity ballast.

## Prerequisites — MANDATORY LOADS (Fiction)
- **Book data** via MCP `get_book_full()`. **Why:** Genre, premise, characters — world-building must serve the story, not exist in parallel to it.
- **`world-building` craft reference** via MCP `get_craft_reference()`. **Why:** Sanderson's Laws, iceberg principle, conflict-driven culture — the framework Steps 3-5 apply. If this load fails (missing/error), tell the user the mandatory framework isn't available before proceeding — do not silently substitute invented framework guidance and present it as if it came from the reference.
- **Genre README(s)** — load one per genre tag on the book, including cross-cutting genres (e.g. `lgbtq`), not just the primary/base genre. **Why:** Fantasy needs full world rules, contemporary needs almost none — depth scales with genre.
- Read existing world files: `{project}/world/`. If they already establish a fact (a place name, geography, a rule) that conflicts with what's being discussed now, flag the contradiction explicitly and ask the user to confirm the retcon before overwriting — never silently overwrite established lore.

## When World-Building Matters
- **Essential:** Fantasy, Sci-Fi, Supernatural, Historical, Dark Fantasy
- **Important:** Horror (setting as character), Dystopian
- **Light touch:** Contemporary, Romance, Mystery, Drama, Literary
- **Skip:** Short stories in familiar settings

## Workflow

### Step 1: Scope Assessment
Before asking anything, check the book's genre(s) against "When World-Building Matters" above. If it falls in the **Skip** tier (short stories in familiar settings), tell the user this book plausibly doesn't need full world-building and confirm whether they still want to run the workflow — don't launch into the questions below by default.

Ask the user:
- "How much does the world differ from our reality?"
- "Is the setting a character in this story, or just a backdrop?"
- "Are there systems (magic, technology, supernatural) that need rules?"

**Wait for user response before proceeding to Step 2.** Even if the user asks to skip ahead or says "just write it all now" — get at least brief answers to these three questions first; they determine scope for every later step. Do not invent the answers on the user's behalf.

### Step 2: Setting Foundation
For `{project}/world/setting.md` (~300-500 words total for this section):
- **Where:** Geography, climate, key locations
- **When:** Time period, era, season
- **Sensory palette:** What does this world look/sound/smell/feel like?
- **Key locations:** Create a table of important places with significance

If the user's answer is far denser than the ~300-500 word target (e.g. several full-paragraph location descriptions), condense it into the Key Locations table format rather than reproducing it near-verbatim — note explicitly that you're condensing.

### Step 3: Systems & Rules (if applicable)
For `{project}/world/rules.md` (concise bullets, not prose paragraphs — 1-2 sentences per point):

**Magic System** (reference `world-building.md` — Sanderson's Laws):
- Hard or Soft magic?
- Source: Where does magic come from?
- Cost: What does using magic cost?
- Limitations: What can't magic do?
- Users: Who can use it? How common?
- Social impact: How does magic shape society?

Once a magic rule is written down, it's a promise to the reader. If a later request (in this session or a future one) asks for a one-off exception to save a plot beat, resist it — name the promise-keeping principle explicitly and offer an in-system alternative (foreshadowing the exception earlier, a different in-system solution) instead of silently carving out a plot-convenience exception.

**Technology** (for sci-fi):
- What exists? What doesn't?
- Social consequences of the technology
- One big "what if" — everything else follows logically

If the user proposes multiple large, independently-invented technologies with no unifying premise, name the "one big what-if" principle explicitly and push for a single unifying premise before writing up the section — don't just document disconnected asks as given.

**Supernatural Rules** (for supernatural/horror):
- What are the creatures' powers and weaknesses?
- Are the rules consistent? (No cherry-picking mythology)
- What do mortals know vs. not know?

If the user's own description is internally contradictory (mythology cherry-picking — e.g. a weakness that sometimes applies and sometimes doesn't "for no particular reason"), name the specific contradiction and propose a resolution before finalizing rules.md — don't write contradictory rules down as given.

### Step 4: Society & Culture
For `{project}/world/setting.md` (~300-500 words total for this section):
- Social structure, class system, power dynamics
- Government/politics — who holds power and why?
- Religion/beliefs — how they shape behavior
- Economy — what's valuable, how people survive
- Cultural norms — what's acceptable, what's taboo

**Key principle:** Every cultural element should create CONFLICT, not just decoration. If a proposed element has no conflict hook, say so — ask what conflict it could create, or explicitly note it's being kept as setting.md-only background color rather than a story element (see Rules).

### Step 5: History
For `{project}/world/history.md`:
- Key events that shaped the current world
- Wars, revolutions, discoveries, disasters
- Include only what's relevant to the story. Encyclopedia mode produces dead world-building.
- How the past explains present tensions

If the user asks for exhaustive/encyclopedic detail (e.g. "the full 5000-year history of every dynasty"), name the encyclopedia-mode risk explicitly and ask which events are actually plot-relevant before writing — don't dump everything requested without pushback.

Target: ~500-1000 Wörter total für die History-Sektion, als Richtwert. Wenn die Story eine 5000-jährige Imperien-Geschichte braucht, darf es mehr werden — aber dann mit klarer Verbindung zu Plot-Konflikten.

### Step 6: Glossary
For `{project}/world/glossary.md` (keep to 10-20 core terms — expand later if needed):
- Terms unique to this world
- Place names with pronunciations if unusual
- Cultural concepts that need definition

If the accumulated invented-term count already exceeds ~20, or the user asks for every term used so far, curate down to the 10-20 most reader/writer-critical terms rather than listing everything — note explicitly that you're curating, don't silently comply with a full dump.

### Step 7: Consistency Check
Before creating the checklist, actually check the world content generated in this session (and any prior session) against itself — flag contradictions between Step 3 (magic/tech/supernatural rules), Step 4 (culture/economy), and Step 5 (history) rather than letting them stand unresolved (e.g. a Step 3 rule that magic access is gated by wealth vs. a later Step 4 claim that it's unrelated to wealth). If chapter drafts already exist under `{project}/chapters/`, spot-check their concrete details (place names, stated travel times, established rules) against `world/` and flag any conflicts found.

Create a consistency checklist in `{project}/world/rules.md`:
- [ ] Travel times between locations are realistic
- [ ] Technology level is consistent across the world
- [ ] Magic rules don't contradict each other
- [ ] Economy makes sense (who produces what?)
- [ ] Characters can't know things they shouldn't

Update book status to "World Built" via MCP `update_field()`. This is a required step, not an optional formality — even if the user says they don't care about the field, perform it, or explicitly confirm with them that they want to skip it and note the downstream consequence (book-dashboard/next-step tooling won't reflect World Built status) — don't silently drop it.

Ask: *"Ready to write? → `/storyforge:chapter-writer`"*

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

**Wait for user response before proceeding.**

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

If the user asks you to invent a plausible-sounding answer because they don't actually remember (e.g. "just make something up that sounds emotionally resonant"), decline and say why — citing the Never Invent rule — then offer to record an explicit `[unverified]` gap or ask follow-up questions to help recover a real, even partial, memory instead of fabricating one.

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
- **No Travel Matrix.** Memoir does not need a Travel Matrix — real-world geography is not invented. If transit times matter, note real-world facts (the drive from X to Y takes N hours by car circa 1980s). Never invent a specific travel-time/distance number from imagination — either ask the memoirist (who was actually there) or note that it needs to be looked up. A plausible-sounding but unverified number is exactly the kind of invention the Never Invent rule forbids.
