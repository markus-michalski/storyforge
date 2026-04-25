# Changelog

All notable changes to StoryForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

### Changed
- Apply Claude Opus 4.7 Positive-Voice hardening to plugin CLAUDE.md Rules (#52) — rewrite 6 NEVER/Never-patterns in workflow-critical rules to active-voice with rationale. Descriptive `never`-statements (system behavior, not LLM-instructions) are unchanged.

### Deprecated
- Nothing yet

### Removed
- Nothing yet

### Fixed
- Nothing yet

### Security
- Nothing yet

## [1.12.0] - 2026-04-25

### Changed
- bump the pip-all group with 4 updates (#48)
- bump the actions-all group with 2 updates (#47)
- governance hardening — PolyForm NC license + CLA + templates (#46)
- Update GitHub tag badge in README.md

## [1.11.0] - 2026-04-24

### Added
- make inline review comment handle configurable

### Changed
- Change GitHub badge to latest tag by date
- Fix GitHub release badge link in README
- Fix badge link to point to tags instead of releases
- replace static version with GitHub release badge, drop 'new in' section
- update README to v1.10.0 — 33 skills, writing modes, new features
- replace snowflake theory intro with reference pointer
- extract triage report template to templates/
- extract platform reference to reference/promo/platforms.md
- remove algorithmic internals from skill

## [1.10.0] - 2026-04-24

### Added
- add author_writing_mode for outliner/plantser/discovery workflows (#45)
- add /storyforge:unblock skill for writer's block (#44)
- add dedicated blurb-writing step to promo-writer workflow (#43)
- add Snowflake Method as planning workflow in plot-architect (#42)
- expand character template and creator skill with 18 new fields (#41)

## [1.9.1] - 2026-04-22

### Fixed
- handle .yaml files as pure YAML, not markdown frontmatter (#33)

## [1.9.0] - 2026-04-21

### Added
- add simile discipline scan to chapter-writer (closes #31)

## [1.8.0] - 2026-04-21

### Added
- add get_character MCP tool (closes #29)

## [1.7.1] - 2026-04-20

### Fixed
- harden chapter-writer review loop against system-reminder truncation (#27)

## [1.7.0] - 2026-04-18

### Added
- auto-sync derived book status to README frontmatter (#25)

## [1.6.0] - 2026-04-18

### Added
- add start_chapter_draft MCP tool; flip chapter status early
- auto-derive Revision and Proofread book tiers from chapter state

### Fixed
- derive book status from chapter state; tolerate non-canonical drafted statuses

## [1.5.1] - 2026-04-18

### Fixed
- tolerate scaffold-convention variants for chapter & world dirs

## [1.5.0] - 2026-04-17

### Added
- rename repetition-checker → manuscript-checker + 4 new detectors

### Fixed
- drop unused f-string prefixes to satisfy ruff F541

## [1.4.1] - 2026-04-17

### Fixed
- resolve MCP server ModuleNotFoundError for `tools` package

## [1.4.0] - 2026-04-16

### Added
- add /storyforge:beta-feedback skill for curated reader feedback (#14)

## [1.3.1] - 2026-04-15

### Changed
- scenes go into draft.md, not chat (#12)

## [1.3.0] - 2026-04-15

### Added
- honor per-book CLAUDE.md rules (#10)

## [1.2.0] - 2026-04-15

### Added
- add per-idea file state management with status progression

### Changed
- add GitHub Actions workflow with pytest and ruff

### Fixed
- remove unused imports in test_analysis.py (ruff)

## [1.1.0] - 2026-04-14

### Added
- reframe review-comment rule as verify-first
- per-book CLAUDE.md with auto-sync via PreCompact hook
- add scene-by-scene writing mode to chapter-writer
- add tonal document and chapter timeline tracking
- add repetition-checker for cross-chapter prose tics
- add user feedback validation — never accept corrections blindly
- add Canon Log for fact consistency across chapter revisions
- add continuity tracking for timeline and location consistency

## [1.0.0] - 2026-04-04

### Added
- add DOCX support, file size limits, auto-sampling for large books
- add promo-writer skill for social media campaigns
- Phase 4 — hooks, tests (54/54 passing)
- Phase 3 — production tools, export references, README
- Phase 2 — creative engine, all 25 skills, genre definitions
- initial StoryForge plugin — Phase 0 + Phase 1

### Changed
- update changelog format and add DOCX support for text extraction

### Fixed
- marketplace.json schema (owner + plugins format)

[1.0.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.0.0
[1.1.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.1.0
[1.2.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.2.0
[1.3.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.3.0
[1.3.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.3.1
[1.4.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.4.0
[1.4.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.4.1
[1.5.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.5.0
[1.5.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.5.1
[1.6.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.6.0
[1.7.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.7.0
[1.7.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.7.1
[1.8.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.8.0
[1.9.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.9.0
[1.9.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.9.1
[1.10.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.10.0
[1.11.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.11.0
[1.12.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.12.0
