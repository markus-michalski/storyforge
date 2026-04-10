---
name: next-step
description: |
  Suggest the next step based on current book status and workflow.
  Use when: (1) User asks "was steht an?", "next step", "was als nächstes?"
model: claude-sonnet-4-6
user-invocable: true
---

# Next Step

## Workflow

1. **Load session** — Use MCP `get_session()` to find active book
   - If no active book: list all books via `list_books()` and ask which one

2. **Load book progress** — Use MCP `get_book_progress()` for the active book

3. **Determine next action** based on book status:

   | Current Status | Next Action | Why |
   |----------------|------------|-----|
   | Idea | `/storyforge:book-conceptualizer` | Develop the concept before plotting |
   | Concept | `/storyforge:plot-architect` | Structure the story |
   | Research | Continue research or move to plot | Depends on genre needs |
   | Plot Outlined | `/storyforge:character-creator` | Populate the story with people |
   | Characters Created | `/storyforge:world-builder` | Build the world (if fantasy/sci-fi/supernatural) or skip to Drafting |
   | World Built | `/storyforge:chapter-writer` ch.1 | Start writing! |
   | Drafting | `/storyforge:chapter-writer` next unwritten chapter | Keep writing |
   | Drafting → Revision (all chapters drafted) | `/storyforge:repetition-checker` | Catch cross-chapter prose tics before per-chapter revision |
   | Revision | `/storyforge:chapter-reviewer` on first unreviewed chapter | Review and polish |
   | Editing | `/storyforge:voice-checker` | Final authenticity check |
   | Proofread | `/storyforge:export-engineer` | Generate the book file |
   | Export Ready | `/storyforge:translator` or publish | Translate or distribute |

4. **Check for incomplete work**
   - Any chapters in "Draft" that need review? → Suggest `chapter-reviewer`
   - Characters still in "Concept"? → Suggest `character-creator`
   - Missing plot outline? → Suggest `plot-architect`
   - All chapters drafted but `research/repetition-report.md` missing? → Suggest `repetition-checker` before per-chapter revisions begin

5. **Present recommendation** with clear reasoning
