# Changelog

All notable changes to StoryForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MCP: `pov_character_inventory` field in `get_chapter_writing_brief` — deterministic extraction of the POV character's last established physical inventory (frontmatter > timeline_regex > draft_heuristic > none) so the chapter-writer surfaces gaps instead of inventing items (#157)
- Skills: `chapter-writer` Pre-Scene Logic Audit — mandatory pre-prose audit block (inventory / geography / character biography / banned phrases + tics / sensory plausibility) emitted to chat before each scene (Mode A) or once per chapter (Mode B), so source-discipline is structurally enforced instead of being a passive rule the model overlooks under context pressure (#155)

### Changed
- Nothing yet

### Deprecated
- Nothing yet

### Removed
- Nothing yet

### Fixed
- Nothing yet

### Security
- Nothing yet

## [1.19.1] - 2026-05-03

### Fixed
- enforce promoted Writing Discoveries via brief + manuscript-checker (#154)

## [1.19.0] - 2026-05-03

### Added
- harvest-author-rules — promote book findings into author profile (#151) (#153)

## [1.18.0] - 2026-05-03

### Added
- plothole checker — analyze_plot_logic + chapter promises (#150) (#152)

### Changed
- bump actions/checkout from 4 to 6 in the actions-all group (#149)

## [1.17.0] - 2026-04-30

### Added
- add /storyforge:rules-audit skill (#148)
- lint at rule append + push for documented alternative (#147)
- add update_book_rule MCP tool with list/lint companions (#145) (#146)

## [1.16.0] - 2026-04-29

### Added
- GateResult schema for checker MCP tools (#122) (#133)
- memoir support for 10 supporting skills (Phase 4, #64) (#114)
- add emotional-truth-prompt skill (Phase 3 #66) (#113)
- add memoir-ethics-checker skill (Phase 3 #65) (#112)
- branch voice-checker for memoir AI-tells (#62) (#111)
- branch manuscript-checker for memoir-specific patterns (#61) (#110)
- branch chapter-writer for memoir mode (Path E Phase 2, #57) (#109)
- branch plot-architect for memoir structure types (Path E Phase 2, #58) (#108)
- branch character-creator into real-people-handler for memoir (Path E Phase 2, #59) (#107)
- branch book-conceptualizer for memoir 5-phase concept (Path E Phase 2, #60) (#106)
- branch new-book and book-dashboard for book_category (Path E Phase 2, #63) (#105)
- add book_category field for memoir support (Path E Phase 1) (#104)

### Changed
- add weekly watcher for issue #138 split trigger (#144)
- add coverage for zero-coverage modules (#124) (#143)
- mirror tests/ structure to source modules (#127) (#142)
- Phase 3 quick wins — ruff format + .gitignore (#123, #125) (#140)
- split server.py monolith into domain router modules (#120) (#139)
- split plot-architect SKILL into fiction + memoir variants (#126) (#137)
- split manuscript_checker.py god-module into focused modules (#118) (#136)
- extract chapter_writing_brief loaders into focused modules (#121) (#135)
- extract validate_chapter hook logic into MCP tool (#119) (#134)
- add memoir integration tests for Phase 2-4 branching (#68)

### Fixed
- remove spurious f-prefix in test helper (ruff F541)
- remove unused imports flagged by ruff

### Security
- allowlist pandoc PDF args to prevent LaTeX/shell injection (#132)
- harden MCP boundary against path traversal and arbitrary write (#131)

## [1.15.0] - 2026-04-27

### Added
- report-issue and promote-rule — close the beta-feedback loop (#102)

### Changed
- replace direct file reads with get_review_brief() and get_continuity_brief() MCP tools (#103)
- document data-briefs-over-prompt-instructions principle (#101)

## [1.14.0] - 2026-04-27

### Added
- cross-chapter timeline validator (#79)
- Sprint 3 — cliché banlist, sentence repetition, snapshot detector, callback validator (#98)
- knowledge-domain boundary checker for POV character plausibility (#95)
- tactical sanity check before combat/travel scenes (#94)
- get_recent_chapter_timelines() — load last 3 intra-day grids as JSON brief (#93)
- get_current_story_anchor() MCP tool + relative-time hook (#92)
- unified banned-phrase hook (author vocab + global anti-AI) (#91)
- per-scene counter for structural tics with chapter-cap limits (#90)
- meta-narrative detector blocks script-reviewer language in prose (#89)
- wire validate_chapter as PostToolUse with hard-block exit code (#86)

### Changed
- get_chapter_writing_brief() — replace prose prereq-load with structured JSON (#96)

### Fixed
- banned-phrase format strictness — hook backticks-only + persistence normalization (#88)

## [1.13.1] - 2026-04-26

### Changed
- add reference/research/ to ignore list for working documents

### Fixed
- sharpen brainstorm trigger to fiction-only and namespace MCP calls

## [1.13.0] - 2026-04-25

### Changed
- Apply 4.7 Positive-Voice hardening to plugin Rules (#53)
- Migrate 20 skills to Claude Opus 4.7 + behavior-shift hardening (#51)

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
[1.13.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.13.0
[1.13.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.13.1
[1.14.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.14.0
[1.15.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.15.0
[1.16.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.16.0
[1.17.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.17.0
[1.18.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.18.0
[1.19.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.19.0
[1.19.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.19.1
