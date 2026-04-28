---
name: rolling-planner
description: |
  Scene-by-scene planning for discovery writers and plantsers.
  Use when: (1) User says "rolling planner", "next scene", "was kommt als nächstes",
  (2) author_writing_mode is "discovery" and user is about to write a chapter,
  (3) Plantser needs to plan the next 3-5 scenes before chapter-writer runs.
  Works for both fiction and memoir books.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug]"
---

# Rolling Planner

Purpose: Replace full upfront outlining with a lightweight, just-in-time scene recipe
written *before* `chapter-writer` runs. Discovery writers and plantsers use this
instead of `plot-architect`.

## Step 0 — Resolve book category

Read `book_category` from `get_book_full(book_slug)`. Treat missing as `fiction`.

If `book_category == "memoir"`, surface a one-line note: *"Working in memoir mode — questions will focus on lived stakes and memory, not invented plot."*

## Prerequisites
- Load book via MCP `get_book_full(book_slug)`
- Load author profile via MCP `get_author(author_slug)`
- Load existing chapter summaries to understand story so far

## Workflow

### Step 1: Orient — What Has Happened

Read chapter READMEs (in order) via MCP to build a quick summary. Branch by `book_category`:

**Fiction:** "Story so far" — who is where, what do they want, what loose threads are active (unresolved conflicts, open questions)?

**Memoir:** "Life so far in this section" — where in the author's life are we, what has just been revealed or confronted, which emotional threads are still unresolved?

Present a 3-sentence orient to the user and ask: *"Does this match your sense of where we are?"*

### Step 2: Define What Needs to Happen Next

Ask the user (use AskUserQuestion or conversational flow). Branch by `book_category`:

**Fiction:**
- **What does the protagonist want in the next scene?** (concrete goal, not theme)
- **What stands in their way?** (person, situation, internal resistance)
- **What should change by the end of this scene?** (something must shift — status, knowledge, relationship, plan)

If the user doesn't know, help them discover it:
- "What would feel wrong if it *didn't* happen soon?"
- "What does the antagonist/situation need from this moment?"
- "What would surprise you as a reader?"

**Memoir:**
- **What did you need or want in this moment of your life?** (concrete — safety, acknowledgment, escape, connection)
- **What blocked you, constrained you, or surprised you?** (person, circumstance, your own avoidance)
- **What shifts by the end of this scene?** (in you, in a relationship, in your understanding of what happened)

If the user doesn't know, help them discover it:
- "What do you remember about this moment that you haven't written down yet?"
- "What are you hesitating to put on the page — and why?"
- "If this scene ended right now, what would feel unfinished?"

### Step 3: Write the Scene Recipe

Compose a 3-part scene recipe (one line each). The structure is identical for both modes:

```
Goal:        [What the POV character / memoir-self is trying to achieve or reach]
Conflict:    [What blocks or complicates that]
Consequence: [What changes — resolution or new complication that opens the next scene]
```

Ask the user to confirm or adjust. This is the contract the chapter-writer will fulfill.

### Step 4: Optional — 3-Sentence Scene Outline
For scenes with higher complexity (multiple characters, reveals, action), offer a brief
expansion:
1. Opening beat — how the scene starts, who is present
2. Complication — the moment the goal gets harder or changes
3. Exit beat — how the scene ends and what it leaves unresolved

This is optional. Skip for straightforward scenes.

### Step 4b: Tactical Sanity Check (fiction combat/travel scenes only)
**Skip entirely for memoir** — tactical formation checks don't apply to lived experience.

For fiction: if the scene recipe involves combat OR group movement through dangerous space (keywords like `walk`, `hike`, `drive`, `attack`, `mission`, `enter the building`, `approach` with multiple characters), call MCP `verify_tactical_setup(book_slug, scene_outline_text, characters_present)` before saving the recipe. Resolve every warn-severity warning by adjusting the scene plan — do not defer to the chapter-writer to fix walking-order or formation problems in prose. Capture the answers to the returned `questions_for_writer` directly in the recipe.

Skip this step for kitchen-table dialogue, internal monologue, or any scene without group movement.

### Step 5: Save to Chapter README
Write the scene recipe (and optional outline) to the next chapter's README via
MCP `update_field(chapter_readme_path, "scene_recipe", value)`.

If the chapter directory doesn't exist yet, create it via MCP `create_chapter(book_slug, number, title)`.

### Step 6: Look Ahead (Optional)
Ask: *"Want to sketch the next 2-3 scenes as well, or start writing now?"*

If yes: repeat Steps 2-4 for each additional scene, writing them to their chapter READMEs.
This builds a rolling 3-5 scene buffer — enough to write without planning the whole book.

## Rules
- Scene recipes are planning tools, not outlines — they can and should change during drafting
- NEVER ask the user to plan more than 5 scenes ahead; that defeats the purpose
- If the user already knows what happens, skip Steps 1-2 and go straight to writing the recipe
- After saving the recipe, always suggest: "Ready to write? → `/storyforge:chapter-writer`"
- Plantser users: this skill complements the minimal outline from `plot-architect` — it adds
  scene-level detail only when needed, not upfront
- **Memoir:** questions about "what happens next" translate to "what do you remember next / what are you ready to write." Never invent or suggest fictional resolutions to memoir material.
