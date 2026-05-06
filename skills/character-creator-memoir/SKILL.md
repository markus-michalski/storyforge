---
name: character-creator-memoir
description: |
  Memoir real-people handler. Captures real people with relationship,
  person_category, consent_status, and anonymization decisions.
  Produces people files at `people/{slug}.md` via MCP `create_person()`.
  Use when: (1) `book_category == "memoir"` AND user says "Charakter",
  "character", "Figur", "Person", "real people",
  (2) After plot/structure is outlined, to populate the memoir's cast.
  Fiction books → use `/storyforge:character-creator` instead.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> [name]"
---

# Character Creator (Memoir)

This skill is the memoir variant of character-creator, split out per Issue #177 so memoir-only sessions never load the fiction character-arc machinery (GMC, Fatal Flaw, The Ghost, Want vs. Need, arc design) and fiction-only sessions never load the memoir real-people handler.

Real people are not invented; they are **captured** with care for relationship, consent, and ethics. The fiction 14-step workflow does not apply here. This skill has six steps and produces a people file with the four-category ethics schema from `real-people-ethics.md`.

## Step 0 — Verify memoir mode

Before any other prerequisite load:

1. **Load book data** via MCP `get_book_full(slug)`.
2. Read `book_category`. If it is `fiction` (or missing), stop and tell the user:
   > *This book's `book_category` is `fiction`. Use `/storyforge:character-creator` for fiction character work — the real-people handler (consent_status, anonymization, person_category) is for memoir books only. (To work on this as a memoir, set `book_category: memoir` in the README frontmatter first.)*
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
- Resolve `book_category` in Step 0 before any prerequisite load.
- Fiction books belong in `/storyforge:character-creator`. Do not blend the two flows.

### Memoir
- Real people are captured, not invented. Imposing GMC / want-need / fatal-flaw frames on a real person produces fictionalization — which is the failure mode memoir avoids.
- Every named living person needs a `consent_status` decision before they appear in any scene. `pending` is acceptable during drafting; `unknown` is not.
- Anonymization that does not actually anonymize is worse than no anonymization — it provides legal exposure with the appearance of safety. Apply the "would someone who knew them identify them" test.
- The `real_name` field stays in frontmatter only. Never render it into prose. Downstream skills (chapter-writer in memoir mode, #57) read the on-page `name`, not `real_name`.
- Composites must be disclosed in the export's author's note (#64). Don't composite to obscure identity — that's anonymizing badly. Composite for narrative economy only.
- For your own children, anonymize aggressively or wait until they can consent — see `real-people-ethics.md` "Special cases".
