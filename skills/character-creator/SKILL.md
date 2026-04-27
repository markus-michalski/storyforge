---
name: character-creator
description: |
  Fiction: develop deep, three-dimensional characters with arcs, voice, motivation.
  Memoir: capture real people with relationship, consent status, and anonymization decisions.
  Use when: (1) User says "Charakter", "character", "Figur", "Person", "real people",
  (2) After plot/structure is outlined, to populate the story.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> [name]"
---

# Character Creator

This skill branches on `book_category` (Path E #97 Phase 2 #59). Fiction runs the historical 14-step character workflow producing files at `characters/{slug}.md`. Memoir runs the **real-people handler** flow producing files at `people/{slug}.md` with the four-category ethics schema from `book_categories/memoir/craft/real-people-ethics.md`.

## Step 0 — Resolve book category

Before any other prerequisite load:

1. **Load book data** via MCP `get_book_full(slug)`.
2. Read `book_category` from the result. Treat missing as `fiction`.
3. Branch the entire workflow on `book_category`. **Never** mix the two flows — a memoir book gets the people handler, period.

If `book_category == "memoir"`, surface a one-line note: *"Working in memoir mode — capturing a real person, not inventing a character. The questions and the saved schema are different."*

## Prerequisites — MANDATORY LOADS

### Fiction mode (`book_category == "fiction"`)
- **Craft references** via MCP `get_craft_reference()`:
  - `character-creation` — **Why:** GMC, archetypes, wants vs. needs, flaws, motivation chains — the depth-test framework Step 5 enforces.
  - `character-arcs` — **Why:** Positive/negative/flat arc patterns — Step 12 maps the character to one of them.
  - `dialog-craft` — **Why:** Voice differentiation — Step 11's "cover the name" test depends on the principles in this reference.
- **Genre README(s)** for genre-specific character expectations. **Why:** Romance protagonists ≠ horror protagonists ≠ literary protagonists — genre dictates expected archetypes and arc patterns.
- Read `{project}/plot/outline.md` and `{project}/plot/arcs.md` for story context.

### Memoir mode (`book_category == "memoir"`)
- **Memoir craft** from `book_categories/memoir/craft/` (resolve via MCP `get_book_category_dir("memoir")`):
  - `real-people-ethics.md` — **Why:** the four-category model and the consent decisions are the schema this skill writes. Read this before asking the user anything.
  - `emotional-truth.md` — **Why:** keeps the "Memory anchors" prompt grounded in specific moments rather than reflective summary.
  - `memoir-anti-ai-patterns.md` — **Why:** prevents the description from drifting into "looking back I realize" platitudes.
- Read `{project}/plot/outline.md` and `{project}/plot/structure.md` for which people the chosen narrative arc actually needs on the page.
- Read `{project}/README.md` `## Scope` section (created by `book-conceptualizer` in memoir mode, #60). **Why:** Phase 3 of the conceptualizer already identified the structural cast and consent posture per person — this skill operationalizes those decisions, not re-decides them.

## Workflow — Fiction (14 steps)

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

**Always ask "why?" twice.** Surface motivations alone fail the depth test. The third layer connects to survival, love, worth, or meaning — if you stop at layer two, the character reads as a thin archetype. Push the user past "she wants to prove herself": prove herself to whom? Why does that matter? What would happen if she didn't?

**Wait for user confirmation that the deepest layer is the right one before moving to Step 6.** Step 6 (The Ghost) builds directly on this — a wrong layer-three answer cascades.

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

## Workflow — Memoir (real-people handler)

The fiction workflow does not apply. Real people are not invented; they are **captured** with care for relationship, consent, and ethics. Skip GMC, want/need, fatal flaw, ghost, and arc — those concepts belong to invented characters. The memoir-mode flow has six steps and produces a people file with the schema from `real-people-ethics.md`.

### Step M1: Identification

Ask the user (use AskUserQuestion when the answers branch downstream choices):

- **Name on the page**: How does this person appear in the manuscript? (Their real name, or a pseudonym?)
- **Real name**: If a pseudonym, what is the real name? (Stored privately in frontmatter; never rendered into prose.)
- **Relationship to the memoirist**: Free-text. *"My sister. My third-grade teacher. The neighbor who watched me on Saturdays. The doctor who gave me the diagnosis."* Specificity here drives every other decision.

### Step M2: Person category

Reference `real-people-ethics.md` four-category model. Pick one:

| Category | Defines |
|----------|---------|
| `public-figure` | Politician, celebrity, named author of a public work — public conduct is fair game; private life is not |
| `private-living-person` | Anyone not a public figure — highest legal exposure (defamation + privacy) |
| `deceased` | Person no longer living — defamation typically does not survive death |
| `anonymized-or-composite` | Identity actively obscured or merged across multiple real people |

If the user is unsure between `private-living-person` and `anonymized-or-composite`, that is itself a flag — push them to commit before continuing. A person whose category is undecided cannot be ethically rendered.

### Step M3: Consent decision

Pick one of five consent statuses:

| Status | When to choose |
|--------|----------------|
| `confirmed-consent` | You have asked and they have said yes — ideally in writing for sensitive portrayals |
| `pending` | You intend to ask before publication; not yet asked |
| `not-required` | Public figure on public conduct, deceased, or fully anonymized in a way that even people who know them well could not identify |
| `refused` | You asked, they said no — see `real-people-ethics.md` "When consent is refused" |
| `not-asking` | Deliberate choice not to ask (estranged, abuser, ongoing harm) — document the reasoning |

If `refused` or `not-asking`, ask the user the follow-up: *"What is the path forward — cut, anonymize, or re-frame?"* Capture the answer in the people file's "Consent and ethics notes" section.

### Step M4: Anonymization decision

Pick one:

| Level | Meaning |
|-------|---------|
| `none` | The person appears as themselves under their real name |
| `partial` | Name changed; some identifying details preserved (occupation, location, age range) |
| `pseudonym` | Name changed plus 2–3 identifying details changed; person not identifiable to people who know them well |
| `composite` | This entry merges two or more real people into one; disclose in author's note |

If anonymization is not `none`, surface the test from `real-people-ethics.md`: *would someone who knew the real person still identify them from the rendered details?* If yes, the anonymization is too thin — push the user to change another identifier or move to `composite`.

### Step M5: Memory anchors

The memoir-specific replacement for fiction's Voice + Quirks + Human Texture. Ask:

- *"What is one specific moment with this person you remember in detail — sensory, gestural, dialogue-fragments-level detail?"*
- *"What is something about how they spoke, moved, or reacted that was uniquely them — not a generalization, an anchor?"*
- *"What is a contradiction in them that you noticed? Real people contain multitudes."*

Capture these as the seed material for scenes that involve this person. Reference `emotional-truth.md` and `scene-vs-summary.md` — the goal is anchors that earn dramatization, not summaries that pretend to be character development.

### Step M6: Write people file

Call MCP `create_person()` with:

- `book_slug`, `name`, `relationship`
- `person_category` (one of the four)
- `consent_status` (one of the five)
- `anonymization` (one of `none` / `partial` / `pseudonym` / `composite`)
- `real_name` (only if anonymization != none)
- `description` (one-line summary)

The MCP tool validates each enum value and refuses to write the file on unknown values — surfacing what the four allowed sets are. If validation fails, fix and retry; do not work around by writing the file directly.

After creation, expand the file body with the Memory anchors from Step M5. Update `{project}/people/INDEX.md` to list the new person under their relationship category (Family / Friends & relationships / Public figures / Pseudonymized / composite).

After all structural-cast people are captured, update book status to "Characters Created" (the status label is shared with fiction; the meaning shifts per `book_categories/memoir/status-model.md`).

## Rules

### Universal
- Resolve `book_category` in Step 0 before any prerequisite load. Never default silently to fiction.
- The fiction and memoir flows are non-overlapping — don't blend them. A memoir person does not need a Fatal Flaw; a fiction character does not need a `consent_status`.

### Fiction
- Build characters with flaws — flaws drive stories. A "perfect" character has no engine.
- Antagonists must believe they're RIGHT — no mustache-twirling villains.
- Every character needs their own voice — run the "cover the name" test on Step 11 sample dialogue.
- Backstory informs behavior. Keep it below the surface — exposition kills mystery.
- Physical appearance should be SPECIFIC ("a scar running through his left eyebrow"), not generic ("tall, dark, handsome").
- If you can describe the character in one word, dig further — the character is not deep enough yet.
- The Ghost must connect to the Lie, which must connect to the Flaw — if the chain breaks, the character psychology is not coherent.
- Contradictions are not inconsistencies — they are the mark of a real human being.

### Memoir
- Real people are captured, not invented. Imposing GMC / want-need / fatal-flaw frames on a real person produces fictionalization — which is the failure mode memoir avoids.
- Every named living person needs a `consent_status` decision before they appear in any scene. `pending` is acceptable during drafting; `unknown` is not.
- Anonymization that does not actually anonymize is worse than no anonymization — it provides legal exposure with the appearance of safety. Apply the "would someone who knew them identify them" test.
- The `real_name` field stays in frontmatter only. Never render it into prose. Downstream skills (chapter-writer in memoir mode, #57) read the on-page `name`, not `real_name`.
- Composites must be disclosed in the export's author's note (#64). Don't composite to obscure identity — that's anonymizing badly. Composite for narrative economy only.
- For your own children, anonymize aggressively or wait until they can consent — see `real-people-ethics.md` "Special cases".
