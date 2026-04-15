---
name: ideas
description: |
  List, filter, and manage book ideas. Shows ideas by status and genre.
  Use when: (1) User says "meine Ideen", "ideas", "was habe ich gespeichert",
  (2) User wants to pick up a parked idea, (3) User asks what ideas are ready.
model: claude-haiku-4-5-20251001
user-invocable: true
argument-hint: "[status] [genre]"
---

# Ideas Dashboard

## Workflow

### 1. Load ideas
Call MCP `list_ideas()` with optional filters:
- If user provided a status argument (e.g. "ready", "explored"), pass it as `status`
- If user mentioned a genre, pass it as `genre`
- Default: load all ideas (no filters)

### 2. Display

If no ideas exist:
```
No ideas saved yet. Start with `/storyforge:brainstorm` to capture your first one.
```

Otherwise, group by status in this order:
`ready` → `developed` → `explored` → `raw` → `shelved` → `promoted`

For each idea, show:
```
**{title}** (`{slug}`) — {status}
Genres: {genres}
{logline}
```

Show counts per group. Example:
```
## Ready (1)
## Explored (3)
## Raw (5)
```

### 3. Offer actions

After listing, offer contextual follow-ups:
- If any `ready` ideas exist: "Turn an idea into a book: `/storyforge:new-book --from-idea {slug}`"
- If any `raw` ideas exist: "Develop a raw idea further: `/storyforge:brainstorm` (mention the slug)"
- Always: "Filter by status: `/storyforge:ideas ready`"

### 4. Single idea view

If user asks about a specific idea (e.g. "show me the clockmaker idea"):
1. Call `get_idea(slug)` or find the matching slug from the list
2. Show full details including body content
3. Offer: update status, continue brainstorming, or promote to book

### 5. Status update (inline)

If user says "mark X as developed" or "shelve the clockmaker idea":
1. Call `update_idea(slug, "status", new_status)`
2. Confirm the change

## Rules
- This is a read-mostly skill — be fast, don't over-explain
- `promoted` ideas should be greyed out / shown last — they're done
- `shelved` ideas: show them but make clear they're parked, not abandoned
- Never delete ideas — only shelve them
