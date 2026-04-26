# Knowledge Domains

Vocabulary lists used by `pov_boundary_checker.py` (Issue #76) to flag
prose that attributes domain expertise to a POV character whose
`knowledge:` profile says they have none or only layperson awareness.

## How the lookup works

For each domain file in this directory:

1. The filename stem becomes the domain key (`forensics.md` → `forensics`).
2. Bullet-list items (`- term` / `* term`) become the term list.
3. Heading lines, paragraphs, and HTML comments are ignored.
4. Terms match case-insensitively as substrings against narration
   (dialog is stripped before scanning).

Reference these domain keys from your character profiles:

```yaml
---
knowledge:
  expert: [it, programming]
  competent: [photography]
  layperson: [psychology, history]
  none: [forensics, ballistics, medicine, tactical_combat]
---
```

A POV character with `forensics: none` triggers a warning when
narration contains any term from `forensics.md`. Free-form domain
names not present in this directory are treated as `competent` so
character authors can encode "learned from Kael" without needing a
vocabulary file.

## Extending

Drop a new `{domain}.md` file with a bullet list. Communities can PR
new domains or extend existing ones — there is no hardcoded master
list.

The default lists are deliberately small starter sets. The goal is
catching the named beta-feedback violations without flooding chapter
reviews with false positives. Tune to your project.
