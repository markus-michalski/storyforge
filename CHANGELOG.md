# Changelog

All notable changes to StoryForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- manuscript-checker: `cliche` detection against a curated banlist (~35 entries)
- manuscript-checker: `question_as_statement` detection — dialogue starting with
  an interrogative word but ending with "." instead of "?" (McCarthy-style
  overuse detector). Recommends either converting to "?" or pairing the flat
  delivery with a narrative beat ("It was a demand, not a question.")
- manuscript-checker: `filter_word` detection — POV-distancing verbs per
  chapter with density thresholds
- manuscript-checker: `adverb_density` detection — per-chapter `-ly` adverb
  ratio with density thresholds

### Changed
- rename skill `repetition-checker` → `manuscript-checker`, reflecting its
  full scope beyond n-gram repetition
- rename MCP tool `scan_book_repetitions` → `scan_manuscript`
- rename report file `research/repetition-report.md` → `research/manuscript-report.md`
- rename module `tools/analysis/repetition_checker.py` → `manuscript_checker.py`
- book-rule violations and clichés now always sort to the top of the report,
  ahead of n-gram findings

### Deprecated
- Nothing yet

### Removed
- Nothing yet

### Fixed
- Nothing yet

### Security
- Nothing yet

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
