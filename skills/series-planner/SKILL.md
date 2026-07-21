---
name: series-planner
description: |
  Plan a book series: overarching arc, book connections, canon management.
  Use when: (1) User says "Serie planen", "series", "book series",
  (2) User wants to write multiple connected books.
model: claude-opus-4-8
user-invocable: true
argument-hint: "<series-name>"
---

# Series Planner

## Session Start

Before asking questions, check whether the user is resuming work on an existing series:
- If a series slug is provided or deducible, call `list_series_trackers_for_book(series_slug, "B1")` to surface existing trackers.
- Report how many trackers exist and which characters are already tracked — this prevents duplicates and gives the user immediate orientation.
- Skip the check when the series doesn't exist yet (Step 2 will create it).

## Workflow

### Step 1: Series Concept
Ask the user:
- Series title
- How many books planned?
- Genre(s) — consistent across series
- What type of series?
  - **Sequential:** Same protagonist, ongoing plot (Harry Potter)
  - **Standalone-connected:** Same world, different protagonists per book (Discworld)
  - **Duology/Trilogy:** Tight arc across 2-3 books
  - **Episodic:** Same characters, standalone plots per book (mystery series)

**Wait for user input on all four points before proceeding to Step 2.** Series type changes everything downstream — guessing here forces a rewrite at Step 3.

### Step 2: Create Series
Use MCP `create_series()` with collected info.

`create_series()` scaffolds the directory and creates placeholder files including `series-arc.md`, `timeline.md`, `world/canon.md`, and `README.md`. Confirm the path from the response before proceeding to Step 3.

### Step 3: Series Arc
For sequential/trilogy series — plan the OVERARCHING arc with the user:
- **Big Question**: What is the central dramatic question that spans ALL books?
- **Per-Book Answers**: How does each book answer one piece of it (without resolving the whole)?
- **Escalation Map**: What raises the stakes between each book?
- **Protagonist Growth Arc**: How does the main character change across the entire series?

Present each arc element as a **concise proposal (1–2 sentences each)**. Do not elaborate further until the user reacts — avoid walls of text during the planning phase. This still applies when the user front-loads full arc detail unprompted in one message — restate it back as the four concise elements and wait for explicit approval before writing; a fully-detailed answer is not itself approval.

Once agreed, use the Write tool to populate `series-arc.md` at the path returned by `create_series()`. Structure the file as:

```markdown
# {Title} — Series Arc

## The Big Question
{The central dramatic question spanning all books}

## Per-Book Arc
- **Book 1 ({title}):** {What this book answers / contributes}
- **Book 2 ({title}):** {What this book answers / contributes}
...

## Escalation Between Books
{What raises the stakes from book to book — stakes, scope, personal cost}

## Protagonist Growth Arc
{How the protagonist changes across the full series — wound → growth → resolution}
```

**Wait for user approval of the series arc before proceeding to Step 4.** Per-book planning depends on a locked overarching arc.

### Step 4: Book Planning
For each planned book:
- Working title
- Focus/theme of this installment
- Where it sits in the overarching arc
- New characters introduced
- Plot threads carried from previous books

Present each book plan as a **~50-word summary**. Do not elaborate further until the user reacts. List all planned books before asking for confirmation.

**Wait for user approval of the book plan before proceeding to Step 5 (Canon Management).** Canon facts are derived from book plans — building canon before plans exist creates orphan facts.

### Step 5: Canon Management
Set up `{series}/world/canon.md`:
- Established facts that CANNOT be contradicted
- Character details (appearances, ages, abilities)
- World rules (magic systems, technology, geography)
- Timeline of events across books

Set up series character trackers for every recurring character:

For each recurring character, call MCP `create_character_tracker()`:

```
create_character_tracker(
  series_slug="{series-slug}",
  name="{Full Character Name}",
  slug="{tracker-slug}",           # kebab-case; use role-prefix if needed (e.g. "king-caelan")
  role="{protagonist|antagonist|supporting|love-interest|mentor|minor}",
  recurs_in=["{B1}", "{B2}", ...],  # all books this character appears in
  species="{species}",              # optional
  tracker_type="thin",              # "full" only for characters with no single home book
  book_slug="{book-level-slug}",    # set ONLY when tracker slug differs from book-level file name
                                    # e.g. tracker "king-caelan" ↔ book file "caelan.md"
)
```

`book_slug:` mapping rule (Issue #194): When the tracker slug differs from the book-level character file stem, set `book_slug` explicitly. When they match (e.g. tracker `kael` ↔ book file `kael.md`), omit it — the resolver falls back to the tracker slug automatically.

`tracker_type: thin` is correct for characters whose full profile lives in their home book. Use `full` only for characters that span books equally without a "home" book — this is rare.

**STOP after presenting the proposed tracker data for each character. Do NOT call `create_character_tracker()` until the user explicitly confirms the `recurs_in` list.** This applies even when the user supplies the character's fields in a single directive message (e.g. "also add General Voss, antagonist, recurs in B1 and B2") — restate the proposed fields back and get an explicit yes before calling the tool; providing the data is not the same as confirming it. The `recurs_in` list is load-bearing for bootstrap, harvest, and brief-source tooling — wrong values cascade into broken series continuity tools. Do not proceed to the next character until the current tracker is confirmed.

### Step 6: Link Books
As books are created, link them via MCP `add_book_to_series(series_slug, book_slug, number)`.

After each `add_book_to_series()` call, verify the link with `get_book_full(book_slug)`:
- Check `book["series"]` matches the series slug
- Check `book["series_number"]` is the expected number
- Report status and any warnings to the user before continuing

## Rules
- Canon.md is sacred — once established, treat it as permanent. Changes require a series-level revision pass. This holds even when the change is framed as minor or casual ("no big deal") mid-conversation — do not edit canon.md inline to accommodate the request; name it explicitly as needing a dedicated revision pass instead.
- Each book must work as a standalone reading experience (even in a trilogy).
- Series-level foreshadowing needs a PLANT & PAYOFF map across books.
- Track what each character KNOWS at each point in the series — info inconsistencies are the most common series-level failure.
