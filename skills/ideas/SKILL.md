---
name: ideas
description: |
  List, filter, and manage book ideas. Shows ideas by status and genre.
  Use when: (1) User says "meine Ideen", "ideas", "was habe ich gespeichert",
  (2) User wants to pick up a parked idea, (3) User asks what ideas are ready.
model: claude-haiku-4-5
user-invocable: true
argument-hint: "[status] [genre]"
---

# Ideas Dashboard

## Workflow

### 1. Load ideas
Call MCP `list_ideas()` with optional filters:
- If user provided a status argument (e.g. "ready", "explored"), pass it as `status`
- If user mentioned a genre, normalize it to the genre system's lowercase slug (e.g. "Fantasy" /
  "Fantasy-Ideen" → `fantasy`) and pass it as `genre`
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

Show counts per group. Only show a heading for a status that has at least one idea — skip
empty groups entirely, don't render e.g. `## Developed (0)`. Example (Developed/Shelved/Promoted
omitted here because none exist):
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
3. Offer exactly these three next actions, nothing else: update status, continue brainstorming,
   or promote to book

### 5. Status update (inline)

If user says "mark X as developed" or "shelve the clockmaker idea":
1. Call `update_idea(slug, "status", new_status)`
2. Confirm the change

### 6. Deletion requests

If user asks to delete an idea (any phrasing — "delete", "remove", "get rid of", "I'll never use it"):
1. Do NOT delete it — there is no delete tool, and ideas are never deleted per the Rules below.
2. Say so explicitly: ideas are only shelved, never deleted.
3. Offer to shelve it instead, and call `update_idea(slug, "status", "shelved")` if the user agrees.

## Rules
- This is a read-mostly skill — be fast, don't over-explain
- `promoted` ideas should be greyed out / shown last — they're done. Concretely: append
  "(already a book — see the project)" after the status, and don't include them in any
  Step 3 develop/promote offer.
- `shelved` ideas: show them but make clear they're parked, not abandoned. Concretely: append
  "(parked, not abandoned)" after the status, and use "parked"/"on hold" wording (never
  "abandoned"/"discarded") in any status-update confirmation for a shelve action too.
- Never delete ideas — only shelve them
