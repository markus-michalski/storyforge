---
name: help
description: |
  Show available StoryForge skills, workflow overview, and quick-start guide.
  Use when: (1) User says "help", "Hilfe", "was kann das Plugin?"
model: claude-haiku-4-5-20251001
user-invocable: true
---

# StoryForge Help

Show the user this overview:

## Quick Start
1. `/storyforge:setup` — First-time setup
2. `/storyforge:create-author` — Create your writing persona
3. `/storyforge:new-book` — Start a new book project
4. `/storyforge:plot-architect` — Structure your plot
5. `/storyforge:chapter-writer` — Write chapter by chapter

## Available Skills

### Getting Started
| Command | What it does |
|---------|-------------|
| `/storyforge:setup` | First-time setup (venv, config, Pandoc check) |
| `/storyforge:configure` | Edit configuration interactively |
| `/storyforge:help` | This help screen |

### Project Management
| Command | What it does |
|---------|-------------|
| `/storyforge:new-book` | Create a new book project |
| `/storyforge:resume <name>` | Continue working on a book |
| `/storyforge:next-step` | Suggest what to do next |
| `/storyforge:book-dashboard` | Show progress overview |
| `/storyforge:brainstorm` | Develop a story idea |
| `/storyforge:series-planner` | Plan a book series |

### Author & Style
| Command | What it does |
|---------|-------------|
| `/storyforge:create-author` | Create a writing persona |
| `/storyforge:study-author` | Analyze PDFs to extract writing style |
| `/storyforge:voice-checker` | Check if text sounds AI-generated |

### Creative Writing
| Command | What it does |
|---------|-------------|
| `/storyforge:book-conceptualizer` | Develop a book concept |
| `/storyforge:plot-architect` | Structure plot with acts and beats |
| `/storyforge:character-creator` | Build deep characters |
| `/storyforge:world-builder` | Create settings and world rules |
| `/storyforge:chapter-writer` | Write a chapter in author's voice |
| `/storyforge:chapter-reviewer` | Review and critique a chapter |

### Research & Sensitivity
| Command | What it does |
|---------|-------------|
| `/storyforge:researcher` | Research topics for authenticity |
| `/storyforge:sensitivity-reader` | Check for problematic content |

### Production
| Command | What it does |
|---------|-------------|
| `/storyforge:export-engineer` | Generate EPUB/PDF/MOBI |
| `/storyforge:translator` | Translate chapter by chapter |
| `/storyforge:cover-artist` | Generate cover art prompts |
| `/storyforge:genre-creator` | Create new genre definitions |

## Workflow
```
Author → Book → Concept → Plot → Characters → World → Chapters → Review → Export
```
