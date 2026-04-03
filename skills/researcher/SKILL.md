---
name: researcher
description: |
  Research topics for story authenticity via web search.
  Use when: (1) User says "Recherche", "research", "find out about",
  (2) Story requires factual accuracy (historical periods, locations, professions, etc.).
model: claude-opus-4-6
user-invocable: true
argument-hint: "<topic> [book-slug]"
---

# Researcher

## Workflow

1. **Identify research needs** — What does the story require?
   - Historical accuracy (dates, events, culture)
   - Location authenticity (geography, architecture, atmosphere)
   - Professional knowledge (how a job/skill works)
   - Scientific plausibility (for sci-fi, medical thrillers)
   - Cultural authenticity (customs, language, social norms)
   - Mythology/lore (for supernatural, fantasy)

2. **Research** — Use WebSearch to find authoritative sources
   - Academic sources over blog posts
   - Primary sources when possible
   - Multiple perspectives on controversial topics
   - Date-check: ensure information is current

3. **Synthesize** — Write findings to `{project}/research/notes/{topic-slug}.md`
   - Key facts relevant to the story
   - Sensory details that can be woven into prose (sights, sounds, smells)
   - Common misconceptions to avoid
   - Source citations

4. **Update sources** — Add to `{project}/research/sources.md`

5. **Connect to story** — How does this research serve the narrative?

## Rules
- Research serves the STORY, not the encyclopedia
- Capture sensory details — those make fiction authentic
- Flag anything that might need sensitivity review
