---
name: rolling-planner
description: |
  Scene-by-scene planning for discovery writers and plantsers.
  Use when: (1) User says "rolling planner", "next scene", "was kommt als nächstes",
  (2) author_writing_mode is "discovery" and user is about to write a chapter,
  (3) Plantser needs to plan the next 3-5 scenes before chapter-writer runs.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "[book-slug]"
---

# Rolling Planner

Purpose: Replace full upfront outlining with a lightweight, just-in-time scene recipe
written *before* `chapter-writer` runs. Discovery writers and plantsers use this
instead of `plot-architect`.

## Prerequisites
- Load book via MCP `get_book_full(book_slug)`
- Load author profile via MCP `get_author(author_slug)`
- Load existing chapter summaries to understand story so far

## Workflow

### Step 1: Orient — What Has Happened
Read chapter READMEs (in order) via MCP to build a quick "story so far" summary:
- Who is where, and what do they want right now?
- What was the last thing that happened (last chapter's consequence)?
- What loose threads are active (unresolved conflicts, open questions)?

Present a 3-sentence "previously on" to the user and ask: *"Does this match your sense of where we are?"*

### Step 2: Define What Needs to Happen Next
Ask the user (use AskUserQuestion or conversational flow):
- **What does the protagonist want in the next scene?** (concrete goal, not theme)
- **What stands in their way?** (person, situation, internal resistance)
- **What should change by the end of this scene?** (something must shift — status, knowledge, relationship, plan)

If the user doesn't know the answer to any of these, that's fine — help them discover it:
- "What would feel wrong if it *didn't* happen soon?"
- "What does the antagonist/situation need from this moment?"
- "What would surprise you as a reader?"

### Step 3: Write the Scene Recipe
Compose a 3-part scene recipe (one line each):

```
Goal:        [What the POV character is trying to achieve]
Conflict:    [What blocks or complicates that goal]
Consequence: [What changes — resolution or disaster that opens the next scene]
```

Ask the user to confirm or adjust. This is the contract the chapter-writer will fulfill.

### Step 4: Optional — 3-Sentence Scene Outline
For scenes with higher complexity (multiple characters, reveals, action), offer a brief
expansion:
1. Opening beat — how the scene starts, who is present
2. Complication — the moment the goal gets harder or changes
3. Exit beat — how the scene ends and what it leaves unresolved

This is optional. Skip for straightforward scenes.

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
