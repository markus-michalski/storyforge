---
name: chapter-reviewer
description: |
  Review and critique a chapter for craft quality, voice consistency, and AI-tells.
  Use when: (1) User says "Kapitel reviewen", "review chapter",
  (2) After chapter-writer completes a draft.
model: claude-opus-4-6
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Chapter Reviewer

## Prerequisites
- Load author profile via MCP `get_author()`
- Load author vocabulary from `~/.storyforge/authors/{slug}/vocabulary.md`
- Load craft references: `dos-and-donts`, `anti-ai-patterns`, `chapter-construction`, `dialog-craft`, `show-dont-tell`
- Read the chapter draft: `{project}/chapters/{chapter}/draft.md`
- Read the chapter outline: `{project}/chapters/{chapter}/README.md`
- Read previous chapter draft for continuity

## Review Checklist — 20 Points

### Structure (5 points)
1. **Opening hook** — Does the first paragraph grab? Would you keep reading?
2. **Scene-sequel flow** — Does each scene have goal/conflict/outcome?
3. **Chapter arc** — Does something CHANGE from start to finish?
4. **Ending** — Does it compel the reader to turn the page?
5. **Pacing** — Does the chapter breathe? Action/reflection balance?

### Craft (5 points)
6. **Show don't tell** — Are emotions shown through action/body, not named?
7. **Sensory details** — Are multiple senses engaged (not just visual)?
8. **Specific details** — Concrete nouns and precise verbs, not generic descriptions?
9. **Dialog quality** — Subtext present? Characters sound different? Minimal tags?
10. **Conflict** — Is there tension in every scene? No filler?

### Voice (5 points)
11. **Author consistency** — Does this sound like the defined author profile?
12. **Tone match** — Does the tone match the profile's descriptors?
13. **Vocabulary** — Any banned words used? Preferred words present?
14. **Sentence rhythm** — Varied length? Matches author's style?
15. **Dialog voice** — Each character distinguishable without tags?

### Anti-AI (5 points)
16. **AI vocabulary** — Any words from the banned list? (delve, tapestry, nuanced, etc.)
17. **Structural uniformity** — Are paragraphs/sentences suspiciously uniform in length?
18. **Generic descriptions** — Any "bustling city", "warm smile", "piercing gaze" clichés?
19. **Emotional telling** — Any "he felt a wave of sadness" instead of showing?
20. **Neat resolution** — Does every scene wrap up too tidily?

## Output Format

```markdown
## Chapter Review: {Chapter Title}

### Score: [X]/20

### Strengths
- *What works well*
- *Specific quotes that shine*

### Issues

#### Critical (Must Fix)
- [Issue] — [Location] — [Suggested fix]

#### Recommended (Should Fix)
- [Issue] — [Location] — [Suggested fix]

#### Minor (Nice to Have)
- [Issue] — [Location] — [Suggested fix]

### AI-Tell Report
- Flagged words: [list]
- Sentence length variance: [high/medium/low]
- Generic descriptions found: [count]

### Verdict
[PASS / NEEDS REVISION / MAJOR REVISION]

### Suggested Next Step
[/storyforge:chapter-writer to revise | move to next chapter]
```

## Rules
- Be BRUTALLY honest. The user asked for honesty in their global instructions.
- Praise what's genuinely good — don't just list problems.
- Quote specific lines when flagging issues.
- Suggest concrete rewrites, not just "make this better."
- The AI-tell check is the most important section. Zero tolerance.
