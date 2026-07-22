---
name: character-creator-memoir
description: |
  Memoir real-people handler. Captures real people with relationship,
  person_category, consent_status, and anonymization decisions.
  Produces people files at `people/{slug}.md` via MCP `create_person()`.
  Run after `/storyforge:plot-architect-memoir`, before `/storyforge:chapter-writer-memoir`.
  Use when: (1) `book_category == "memoir"` AND user says "Charakter",
  "character", "Figur", "Person", "real people",
  (2) After plot/structure is outlined, to populate the memoir's cast.
  Fiction books → use `/storyforge:character-creator` instead.
model: claude-opus-4-8
user-invocable: true
argument-hint: "<book-slug> [name]"
---

# Character Creator (Memoir)

**Position in workflow:** `plot-architect-memoir → character-creator-memoir → chapter-writer-memoir`

This skill is the memoir variant of character-creator, split out per Issue #177 so memoir-only sessions never load the fiction character-arc machinery (GMC, Fatal Flaw, The Ghost, Want vs. Need, arc design) and fiction-only sessions never load the memoir real-people handler.

Real people are not invented; they are **captured** with care for relationship, consent, and ethics. The fiction 14-step workflow does not apply here. This skill has six steps and produces a people file with the four-category ethics schema from `real-people-ethics.md`.

## Step 0 — Verify memoir mode

Before any other prerequisite load:

1. **Load book data** via MCP `get_book_full(slug)`.
2. Read `book_category`. If it is `fiction`, stop and tell the user:
   > *This book's `book_category` is `fiction`. Use `/storyforge:character-creator` for fiction character work — the real-people handler (consent_status, anonymization, person_category) is for memoir books only. (To work on this as a memoir, set `book_category: memoir` in the README frontmatter first.)*

   If `book_category` is missing entirely (legacy book, field never set), treat it the same as `fiction` — stop with the equivalent message, don't say "is fiction" when it's actually unset:
   > *This book has no `book_category` set, so it defaults to fiction. Use `/storyforge:character-creator` for fiction character work — the real-people handler (consent_status, anonymization, person_category) is for memoir books only. (To work on this as a memoir, set `book_category: memoir` in the README frontmatter first.)*

   Either way: stop and redirect. Do not ask the user which mode they meant just because they invoked this memoir-specific command — the command name is not authoritative over the book's own `book_category` field.
3. Otherwise surface a one-line note: *"Working in memoir mode — capturing a real person, not inventing a character. The questions and the saved schema are different."*

## Prerequisites — MANDATORY LOADS

- **Memoir craft** from `book_categories/memoir/craft/` (resolve via MCP `get_book_category_dir("memoir")`):
  - `real-people-ethics.md` — **Why:** the four-category model and the consent decisions are the schema this skill writes. Read this before asking the user anything.
  - `emotional-truth.md` — **Why:** keeps the "Memory anchors" prompt grounded in specific moments rather than reflective summary.
  - `memoir-anti-ai-patterns.md` — **Why:** prevents the description from drifting into "looking back I realize" platitudes.
- Read `{project}/plot/outline.md` and `{project}/plot/structure.md` for which people the chosen narrative arc actually needs on the page.
- Read `{project}/README.md` `## Scope` section (created by `book-conceptualizer` in memoir mode, #60). **Why:** Phase 3 of the conceptualizer already identified the structural cast and consent posture per person — this skill operationalizes those decisions, not re-decides them.

## Workflow — Real-People Handler (6 steps)

### Step M1: Identification

Before asking anything below, the Prerequisites loads must actually have happened — `real-people-ethics.md` in particular, since its four-category model and consent framework is what the rest of this workflow assumes. Do not open Step M1 on a cold read of just this skill file. Say so briefly to the user, don't just load it silently — e.g. *"Working from real-people-ethics.md's four-category model (public figure / private living person / deceased / anonymized-or-composite) and the consent framework — here's who we're capturing first."* A silent load the user never sees is not distinguishable from no load at all.

If the Scope section (`README.md`) already names a structural cast, start from that list rather than asking the user to invent a cast from nothing — e.g. *"Scope names your mother, your brother, and the hospice nurse as the structural cast. Want to start with your mother?"*

Ask the user (use AskUserQuestion when the answers branch downstream choices):

- **Name on the page**: How does this person appear in the manuscript? (Their real name, or a pseudonym?)
- **Real name**: If a pseudonym, what is the real name? (Stored privately in frontmatter; never rendered into prose.)
- **Relationship to the memoirist**: Free-text. *"My sister. My third-grade teacher. The neighbor who watched me on Saturdays. The doctor who gave me the diagnosis."* Specificity here drives every other decision.

Once the relationship answer comes in: if it reveals this is the memoirist's own minor child, flag it immediately — per the Rules section's "For your own children" special case, anonymize aggressively or wait until they can consent. Carry this forward into Step M4's anonymization discussion so it doesn't default to light treatment.

**Wait for user to confirm name, real name (if any), and relationship before proceeding to Step M2 — even if the user's initial answer already contained all three pieces, restate them and get an explicit go-ahead before opening Step M2 in the same turn.**

### Step M2: Person category

Reference `real-people-ethics.md` four-category model. Pick one:

| Category | Defines |
|----------|---------|
| `public-figure` | Politician, celebrity, named author of a public work — public conduct is fair game; private life is not |
| `private-living-person` | Anyone not a public figure — highest legal exposure (defamation + privacy) |
| `deceased` | Person no longer living — defamation typically does not survive death |
| `anonymized-or-composite` | Identity actively obscured or merged across multiple real people |

If the user is unsure between `private-living-person` and `anonymized-or-composite`, that is itself a flag — push them to commit before continuing. A person whose category is undecided cannot be ethically rendered.

**Wait for user to confirm the chosen `person_category` before proceeding to Step M3.**

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

"Unknown", "not sure yet", "haven't decided" is not a valid `consent_status` — none of the five values above means "undecided." If the user hasn't decided, walk through the five options and land on the honest one; that is usually `pending` (intend to ask before publication) per the Rules section. Do not record `consent_status: unknown` and do not leave it unset.

**Wait for user to confirm `consent_status` before proceeding to Step M4.**

### Step M4: Anonymization decision

Pick one:

| Level | Meaning |
|-------|---------|
| `none` | The person appears as themselves under their real name |
| `partial` | Name changed; some identifying details preserved (occupation, location, age range) |
| `pseudonym` | Name changed plus 2–3 identifying details changed; person not identifiable to people who know them well |
| `composite` | This entry merges two or more real people into one; disclose in author's note |

If anonymization is not `none`, surface the test from `real-people-ethics.md`: *would someone who knew the real person still identify them from the rendered details?* If yes, the anonymization is too thin — push the user to change another identifier or move to `composite`.

`composite` is for narrative economy only (several minor people who collectively played one role), never as a way to obscure one specific person's identity — that is thin anonymization wearing composite's cover story. Never merge people of meaningfully different moral weight (e.g. a difficult-but-decent ex with an abusive one) into a single composite — the merged character inherits weight neither individual carried. If the user proposes either, push back and point at `pseudonym` (real anonymization of each person) instead.

**Wait for user to confirm anonymization level before proceeding to Step M5.**

### Step M5: Memory anchors

The memoir-specific replacement for fiction's Voice + Quirks + Human Texture. Ask:

- *"What is one specific moment with this person you remember in detail — sensory, gestural, dialogue-fragments-level detail?"*
- *"What is something about how they spoke, moved, or reacted that was uniquely them — not a generalization, an anchor?"*
- *"What is a contradiction in them that you noticed? Real people contain multitudes."*

If the user asks for a fatal flaw, a GMC (Goal/Motivation/Conflict) breakdown, or a want-vs-need frame for this person, decline — those are fiction-craft tools; applying them to a real person produces fictionalization, the exact failure mode memoir avoids (see Rules). Redirect to these three questions instead.

If an answer is a generalized summary rather than a specific moment ("she was always caring", "he never gave up") — reject it as a memory anchor. Ask for the one scene: what were they doing, what did they say, what did it look/sound/feel like. A trait description is not an anchor; an anchor earns the trait through a specific, dramatized moment. Do not write a generalized summary into the file as if it were a memory anchor — push back at least once before accepting.

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

After creation, expand the file body with the Memory anchors from Step M5. Update `{project}/people/INDEX.md` to list the new person under one category. Relationship is the primary axis and wins by default — file under `Family`, `Friends & relationships`, or `Public figures` (matching `person_category: public-figure`) based on who this person actually is to the memoirist, even when `anonymization` is `partial` or `pseudonym`; a pseudonym changes how the person is *rendered*, not who they *are*, so a lightly-to-moderately anonymized mother still belongs under `Family`. Reserve `Pseudonymized` / `composite` for entries that don't cleanly map to one relationship bucket in the first place — a `composite` entry merging several minor people, or an entry where the relationship itself is being withheld as part of the anonymization strategy.

Before updating book status: compare the people now captured (`people/INDEX.md`) against the structural cast named in the README `## Scope` section. Only once every named structural-cast person has a people file does Step M6 finish — update book status to "Characters Created" (the status label is shared with fiction; the meaning shifts per `book_categories/memoir/status-model.md`) and ask the closing question below. If cast members remain uncaptured, say which ones and offer to continue with the next one instead of updating status or asking "Ready to write?" yet.

Ask: *"Ready to write? → `/storyforge:chapter-writer-memoir`"*

## Rules

### Universal
- Resolve `book_category` in Step 0 before any prerequisite load.
- Fiction books belong in `/storyforge:character-creator`. This skill handles only memoir real-people work — the two flows are separate by design.

### Memoir
- Real people are captured, not invented. Use only what the author observed and remembers. GMC / want-need / fatal-flaw frames belong in fiction; applying them to a real person produces fictionalization — which is the failure mode memoir avoids.
- Every named living person needs a `consent_status` decision before they appear in any scene. `pending` is acceptable during drafting; `unknown` is not.
- Anonymization that does not actually anonymize is worse than no anonymization — it provides legal exposure with the appearance of safety. Apply the "would someone who knew them identify them" test.
- The `real_name` field stays in frontmatter only — prose always uses the on-page `name`. Downstream skills (chapter-writer in memoir mode, #57) read `name`, not `real_name`.
- Composites must be disclosed in the export's author's note (#64). Composite only for narrative economy; identity-obscuring composites that still point to one real person are thin anonymization and carry the same legal exposure.
- For your own children, anonymize aggressively or wait until they can consent — see `real-people-ethics.md` "Special cases".
