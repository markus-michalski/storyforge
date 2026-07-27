---
name: researcher
description: |
  Research topics for story or memoir authenticity via web search.
  Use when: (1) User says "Recherche", "research", "find out about",
  (2) Story requires factual accuracy (historical periods, locations, professions, etc.),
  (3) Memoir author needs to verify dates, period details, or remembered facts.
model: claude-opus-5
user-invocable: true
argument-hint: "<topic> [book-slug]"
---

# Researcher

## Step 0 — Resolve book and book category

`book-slug` is optional (see `argument-hint`) — resolve it before anything else:

1. If the user provided a `book-slug`, use it directly.
2. Otherwise call MCP `get_session()` and use its active book, if set.
3. If there is still no book (no argument, no active session book), call MCP
   `list_books()` and ask the user which book this research is for. Do not
   guess or default silently — mirrors `next-step`'s "no active book" branch.

Once resolved, load `book_category` from MCP `get_book_full(book_slug)`. Treat missing as `fiction`.
Branch Step 1 on `book_category` — the research categories differ fundamentally.

## Workflow

### Step 1: Identify Research Needs

Branch by `book_category`:

**Fiction** — What does the story require?
- Historical accuracy (dates, events, culture)
- Location authenticity (geography, architecture, atmosphere)
- Professional knowledge (how a job/skill works)
- Scientific plausibility (for sci-fi, medical thrillers)
- Cultural authenticity (customs, language, social norms)
- Mythology/lore (for supernatural, fantasy)

**Memoir** — What does the memoirist need to verify or recover?
- **Memory verification** — Are dates, names, and events as you remember them? (Newspapers, diaries, public records)
- **Period detail** — What was the physical world actually like then? (Buildings, prices, technology, music, fashion)
- **Place recovery** — What does archive material show about a place you remember? (Old maps, photographs, local histories)
- **Timeline anchoring** — What publicly-documented events fix the chronology? (News events, school years, weather records)
- **People context** (with care) — Public facts about real people relevant to the story (only public records; never private investigation)
- **Cultural/historical context** — What was the social climate, political mood, or institutional reality at the time?

Note: Memoir research serves **verification and depth**, not world-building. The goal is to make remembered experience more accurate and more vivid — not to invent.

### Step 2: Research

Use WebSearch to find authoritative sources:
- Academic sources over blog posts
- Primary sources when possible (newspaper archives, official records, period photographs)
- Multiple perspectives on contested or politically sensitive topics
- Date-check: ensure information is current for contemporary memoir; period-accurate for historical memoir

**Memoir note:** For people-related research, limit to publicly available information. Do not compile private details about living individuals beyond what is directly relevant to verifiable shared events.

### Step 3: Synthesize

Call `resolve_path(book_slug, "research", "notes/{topic-slug}.md")` (MCP) before writing — `{project}` throughout this skill refers to the resolved book root and handles both standalone (`projects/{slug}/`) and series-nested (`series/<series-slug>/{slug}/`) layouts.

Write findings to the resolved `research/notes/{topic-slug}.md`.
**Scope: ~300–500 words per topic; bullet-point style; depth over length.**

**Fiction captures:**
- Key facts relevant to the story
- Sensory details that can be woven into prose (sights, sounds, smells)
- Common misconceptions to avoid
- Source citations

**Memoir captures:**
- Verified facts that confirm or correct memory
- Period sensory details (what did it actually smell/sound/look like in that era?)
- Documented timeline anchors (specific dates that fix when events happened)
- Gaps where verification failed — note what could not be confirmed so it can be handled appropriately in prose
- Source citations (for any factual claims in the finished memoir)

### Step 4: Update sources

Call `resolve_path(book_slug, "research", "sources.md")` (MCP) to locate the file, then add the sources used to the resolved `research/sources.md`. Let `resolve_path` build the path rather than hand-assembling `{project}/research/sources.md` yourself — the MCP tool resolves both standalone and series-nested layouts correctly, exactly as in Step 3.

### Step 5: Connect to story

How does this research serve the narrative?

**Fiction:** Does this detail create conflict, atmosphere, or authenticity? If it doesn't serve the story, it stays below the iceberg.

**Memoir:** Does this verified detail strengthen the narrative's factual grounding? Does it resolve a memory gap? Note if the verified version differs from what the memoirist remembers — that gap itself may be narratively meaningful.

## Rules
- Research serves the STORY (fiction) or the TRUTH (memoir), not the encyclopedia — this holds even when the user asks for "everything" or a comprehensive knowledge base. Scope the research to what the narrative actually uses and keep the rest below the iceberg, rather than producing an exhaustive survey.
- Capture sensory details — those make both fiction and memoir vivid
- Flag anything that might need sensitivity review — surface the flag to the user directly (and note it in the research note); never bury it in the file or silently drop it. Recommend `/storyforge:sensitivity-reader` when the topic warrants a closer pass.
- **Memoir:** if research surfaces information that contradicts the memoirist's memory, report honestly — do not quietly align findings with memory. The memoirist decides how to handle the discrepancy in prose.
