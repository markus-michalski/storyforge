# Changelog

All notable changes to StoryForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

### Changed
- `BODY_PARTS` vocabulary gained `chins`/`elbows`/`wrists`/`thumbs` — n-grams containing
  these may now classify as `character_tell` where they previously landed in another
  repetition category (#511).

### Deprecated
- Nothing yet

### Removed
- Nothing yet

### Fixed
- `manuscript-checker` now detects paraphrased body-language tells. The n-gram repetition
  pass only fires on verbatim repetition, so a tic the author rephrases each time (e.g.
  "shoulders came down" / "shoulders had dropped") was invisible to it. A new slot-based
  detector matches `[body part] + [state signal]` regardless of exact wording, additive to
  the existing pass (#511).
- `extract_text_from_file` rejected a null-byte path via `Path.resolve()`'s platform-dependent
  behavior (raises on POSIX, doesn't on Windows), producing a different error message — and on
  Windows, for a path resolving inside an allowed root, no rejection message at all, only a
  generic file-not-found. An explicit pre-check now rejects the path uniformly before
  `resolve()` is called (#512).
- `update_field` did not catch `ValueError` when resolving `file_path`, so a null-byte path
  raised an unhandled exception on POSIX instead of a clean JSON error response; on Windows it
  fell through to a generic file-not-found instead of a rejection. Same fix as #512: an explicit
  null-byte pre-check ahead of `Path.resolve()`, plus `ValueError` added to the except clause
  (#516).
- `resolve_path` did not reject embedded null bytes in `component`/`sub_path`, so
  `Path.resolve()`'s platform-dependent behavior leaked through: an unhandled `ValueError`
  on POSIX, and on Windows a path that resolved inside `content_root` was returned as a
  success response with the null byte intact. Same fix as #512/#516: an explicit pre-check
  rejects both parameters uniformly before `resolve()`, with `ValueError` added to the
  except clause as a second layer (#517).
- `update_field` accepted a field name with a trailing newline. `_FIELD_NAME_RE` was
  anchored with `$`, which also matches before a trailing newline, so `field="status\n"`
  passed the allowlist and silently wrote a junk YAML key instead of updating `status` —
  while still returning `success: true`. Anchored with `\Z` instead (#518).

### Security
- Nothing yet

## [3.3.1] - 2026-08-09

### Fixed
- bound remaining unbounded get_continuity_brief fields (#504) (#505) (#507)
- cap unbounded canon_log_facts (#503)
- bound canon_log_facts size, fix stale changed_facts refs (#500) (#502)

## [3.3.0] - 2026-08-08

### Added
- add chapter-fixer for targeted reviewer-finding fixes (#496) (#497)

### Changed
- bump the pip-all group across 1 directory with 3 updates (#495)

### Fixed
- correct target updates no longer duplicate promise rows (#498) (#499)
- close MCP smoke/protocol test-coverage gap, re-export delete_author (#494)
- re-anchor voice per-character in ensemble/first-speak scenes (#493)
- widen §11.1 count-and-editorialise shape beyond "word" (#491)

## [3.2.2] - 2026-07-30

### Fixed
- migrate FastMCP -> MCPServer for mcp 2.0.0, fix ToolAnnotations fields (#488)
- cap mcp to <2.0.0, guard against dependabot re-widening it (#487)

## [3.2.1] - 2026-07-27

### Changed
- Resolve 4 open issues: canon-fact count, revision-pass tracking, manuscript-checker doc, researcher fallback (#476, #478, #479, #483)
- add .claude/worktrees/ to .gitignore for local-only leftovers
- fix vocabulary.md refs, resolve_path gaps, and enforce-rule stale doc (#435, #437, #439) (#440)
- bump actions/setup-python in the actions-all group (#432)

### Fixed
- use resolve_path for sources.md and harden rules (#484)
- add routing guards and correct get_book_full return shape (#482)
- clarify progress fields, DB sections, next-step logic (#481)
- clarify revision sub-phases and tighten workflow table wording (#480)
- clarify canon-column gap, session-book resolution, and category grouping (#477)
- correct banned-phrase field and add missing checks (#475)
- reconcile correction handling with Rule 14 and close gate loopholes (#474)
- audit all skills for stale CLAUDE.md-Rules-edit assumption (#473)
- resolve 14 open plugin issues (ban-severity, JSON format, model bump, skill logic) (#472)
- close front-matter placeholder gap and pandoc/config issues (#465)
- fix Midjourney length overflow and prompt conflicts (#464)
- reconcile vocabulary hard gate with memoir mode and verdict contract (#463)
- prefer DB snapshot over stale frontmatter with recency check (#462)
- correct book_rules DB field names and annotate-path gaps (#461)
- correct MCP fields and un-block character callbacks (#459)
- correct find_book resolution and rule_match ambiguity guard (#458)
- fix global-write parser mismatch and error handling (#456)
- correct enforcement claims for author/global scope rules (#454)
- gate step 3 on explicit wait, validate genres, strip quotes (#451)
- read callback register from book_rules DB, not dead CLAUDE.md markers (#449)
- fix Step 4 chapter scan and D4/export gate mapping (#447)
- scope memoir hard-stop to Categories 1-2 only (#446)
- correct ET1 scope, Step 1 fallback, and prerequisite ordering (#445)
- resolve overlapping-hit apply conflict and pass-vs-batch confusion (#436)
- correct language-fallback and avoid-list claims (#438)

## [3.2.0] - 2026-07-25

### Added
- add create-testdata/reset-testdata/delete-testdata skills (#433)
- add delete_author MCP tool and delete-author skill (#385) (#386)

### Changed
- list Fact Recording Gate + Draft-Skip Scope in shared-procedures summary (#429)
- clarify Step 7 per-save vs per-close scope (#427)
- fix stale add_canon_fact(chapter_slug, ...) call examples (#424)
- extract Fact Recording Gate to fix skill-bloat (#423, #405) (#428)
- scale EA-Scan rewrite threshold by word count (#426)
- add missing genre-filter language to Step 2 (#425)
- autouse-isolate DB_DIR for the whole test tree (#422)
- skills(chapter-reviewer): fix severity tier, promise scoping, and Anti-AI numbering collision (#413)
- skills(chapter-writer-memoir): delegate pre-logic audit + add EA-scan gate (#411)
- add guardrails from eval-driven hardening pass (#404)
- skills(world-builder): reinforce Rules/Key-principle constraints inline at trigger points (#403)
- character-creator-memoir: eval-loop fixes (100% simulated + live) (#402)
- storyforge: character-creator self-improvement (69/69 simulated) (#399)
- skills(plot-architect-memoir): close 4 adversarial-eval gaps (numeric-bound enforcement, order-as-argument, STOP-gate/delegation, Rules-section reinforcement) (#398)
- storyforge/ideas: self-improvement loop, simulated 49/49 + live 5/5 (#390)
- skills(brainstorm): self-improvement loop + book_category persistence fix (#388)
- close 4 adversarial-eval gaps found by the skill-improvement loop (#376)
- scope Python-missing install advice to python.org (#375)
- update pymupdf requirement in the pip-all group (#346)
- author-check: require judgments to name their concrete trigger (#348)
- add /logs to .gitignore

### Fixed
- document memoir Step 7 unconditional-write mapping (#430)
- tactical-gate info findings mis-severitized as WARN (#421)
- wire book_category + consent gate into review brief (#414)
- correct canon_log_facts schema refs and wire consent-status source (#412)
- bound snapshot_db lookups to avoid future-state leak (#409)
- has_existing_ende false-positive for never-harvested trackers (#400)
- self-improvement loop (simulated 57/57, live 12/12) (#397)
- self-improvement loop + live-tier MCP bug fix (#396)
- close 5 adversarial-eval gaps + 1 live-tier factual correction (#395)
- match genre substrings in list_ideas (#393)
- close adversarial-eval gaps in genre/category/POV-tense/series-copy handling (#392)
- close 6 adversarial-eval gaps in skill workflow (#391)
- scope force-delete approval per author, not per session (#387)
- unify last_phase semantics + add SKILL.md placeholder lint (#384)
- wire up chapter/session tracking, fix dead anchor fallback (#383)
- close 6 adversarial-eval gaps + verify live-MCP tier (#382)
- close 18 adversarial-eval gaps + 2 live-MCP-tier server bugs (#380)
- report-format gaps + get_session() schema-drift fix (#379)
- require full/unabridged reproduction, protect command syntax (#377)
- patch single field instead of re-dumping whole YAML (#374)
- add memoir-specific theme-development craft reference (#373)
- close 4 adversarial-eval gaps in book-conceptualizer (#370)
- close 7 adversarial-eval gaps in book-conceptualizer (57/68 -> 68/68) (#369)
- correct stale memoir skill-routing references (#364)
- close 4 spec gaps found by self-improvement loop (66/71 -> 71/71) (#363)
- close 6 spec/test issues in one bundle (#349 #350 #354 #358 #359 #360) (#362)
- close cluster B + C follow-up (78/82 -> 80/82) (#361)
- distinguish omitted vs. explicit-empty in update_session() (#357)
- distinct memoir-scope skip message via mode: frontmatter (#356)
- close 3 spec gaps found by self-improvement loop (#355)
- resolve chapter paths via resolve_path, not a nonexistent project_path field (#353)
- allow study-author to persist quantitative targets (#352)
- remove ${HOME} env override that Claude Code never expands (#351)

## [3.1.0] - 2026-07-18

### Added
- route MCP server and hooks through a cross-platform wrapper (#347)

## [3.0.2] - 2026-06-29

### Changed
- add tool annotations to all 79 MCP tools (#345)
- pin dependencies with lock file, update CI (closes #331) (#344)
- bump the pip-all group with 4 updates (#338)

### Fixed
- warn on slug collision between projects/ and series/ (closes #340) (#343)
- bundle prev chapter draft into writing brief (#342)

## [3.0.1] - 2026-06-29

### Fixed
- series book indexer + vocabulary.md payload fix (#341)

## [3.0.0] - 2026-06-26

### Added
- Cluster C — vocabulary DB consolidation (#293) (#303)
- complete #277 — universal override + genre registry validation (#290)
- book_rules SQLite — migrate rules/callbacks/workflows out of CLAUDE.md markers (#282) (#287)
- SQLite schema + canon_facts + session DB (Issue #280) (#285)
- add genre-tagging and example extraction to backfill-style-principles (#276)
- series directory layout — books live in series/{slug}/{book}/ (Issue #279) (#284)
- genre-tagging for style_principles via when: field (#274)
- phase 2 — voice demonstration layer and world-rules scaffold (#273)
- Phase 1 — style control, world rules, callback intensity

### Changed
- pin security-relevant transitive deps to CVE-fixed versions
- fix duplicate step 11 in Plantser workflow, add start-session routing (#319)
- migrate 29 skills to claude-opus-4-8 with body-hardening (#318)
- add mypy to CI, fix 16 type errors (#317)
- document add_vocabulary_entry as user-callable utility tool (#316)
- fix stale CLAUDE.md storage refs in skills after #282 DB migration (#305)
- DB-only canon_brief — remove MD read path (#297) (#300)
- Phase 5 — parser cleanup + source_genres skill chain (#283) (#288)
- author_discoveries + character_snapshots in SQLite (Issue #281) (#286)

### Fixed
- register extract_text_from_file as MCP tool, complete server.py re-exports (#315)
- enforce canon fact recording before chapter status advancement (#307)
- read active_rules and callbacks from book_rules DB in brief assemblers (#306)
- surface profile.md body as style_notes in get_author() (#294) (#302)
- update author Don't test suite after DB migration (#298) (#299)
- wire DB canon facts into chapter-writer brief (#296)
- sync genre-filter and world-rules.md to chapter-reviewer and author-check (#275)

### Security
- field allowlist for update_author, format guard for update_field (#328)
- sanitize exception messages and STORYFORGE_DB_DIR (#327 #329)
- fix DB slug traversal, pandoc metadata injection, rule body limit
- fix ReDoS risk in book rules regex compilation (#322)
- fix path traversal in extract_text_from_file, get_genre, get_craft_reference (#320, #321) (#332)

## [2.2.2] - 2026-06-23

### Fixed
- load previous chapter draft and activate style_principles (#265)

## [2.2.1] - 2026-06-23

### Fixed
- add question-as-statement punctuation hard gate (#264)

## [2.2.0] - 2026-06-22

### Added
- backfill-style-principles skill (#262) (#263)

### Changed
- update mcp requirement in the pip-all group (#257)
- bump actions/checkout from 6 to 7 in the actions-all group (#256)

## [2.1.0] - 2026-06-22

### Added
- add positive style compliance verification skill (#261)
- genre-driven positive style extraction (#259) (#260)

### Changed
- update mcp requirement in the pip-all group (#255)

## [2.0.1] - 2026-05-21

### Added
- add anti-checklist warning for scene beats (#253) (#254)

## [2.0.0] - 2026-05-18

### Added
- add next-step hints to mid-pipeline skills (#239) (#250)
- add create_character_tracker MCP tool + improve series-planner skill (#237) (#248)

### Changed
- session-start → start-session (#241) (#252)
- H2 structural drift detection for fiction/memoir skill pairs (#238) (#249)
- remove deprecated v2.0 tools, document internals (#247)
- extract shared craft reference (#246)
- update xfail reference from #235 to #245

### Fixed
- disambiguate unblock vs next-step trigger conditions (#240) (#251)
- trim chapter-writer scan sections + add skill-size smoke test (#244)
- repair broken MCP tool calls and routing after coherence audit (#243)
- support WARN severity and chapter_limit for Writing Discoveries

## [1.26.2] - 2026-05-18

### Added
- upgrade Step 6d EA-Scan to interactive hard-gate (#233)

## [1.26.1] - 2026-05-17

### Added
- extend AI-tell catalog with shapes 11.9, 11.10 and transition tells (#232)

## [1.26.0] - 2026-05-17

### Added
- add chapter-humanizer skill + Elegant Abstraction Scan hardening (#231)

## [1.25.2] - 2026-05-15

### Added
- chapter-writer — prompt rolling-planner for plantser/discovery authors

## [1.25.1] - 2026-05-15

### Added
- chapter-reviewer — add 14b Phrase Micro-Echo check (closes #228)

### Fixed
- cap chapter-writer Mode A at 2 scenes per session to prevent compaction degradation
- persist scene plan to README.md in chapter-writer Mode A (closes #230)

## [1.25.0] - 2026-05-15

### Added
- add chapter-proofreader skill (#224) (#227)
- add native_language + preferred_writing_language to author profile (#226)

## [1.24.0] - 2026-05-13

### Added
- auto-scan Section 11 shape bans for every author (#213) (#214)

### Changed
- Add manuscript-checker scan for catalog Section 1 ai-tells (#216) (#223)
- Split hook author-banlist into three distinct categories (#215) (#222)
- Lint author profile writes via write_author_discovery (#218) (#221)
- Extract Recurring-Tic patterns from bullet body, not just bold title (#212) (#220)
- Fix author Don't extractor blocking recommended phrases (#217) (#219)

## [1.23.0] - 2026-05-13

### Added
- scan author profile Don'ts and vocabulary (#210) (#211)

### Changed
- Add elegant-abstraction register to anti-AI patterns (#209)

## [1.22.1] - 2026-05-10

### Changed
- update mcp requirement in the pip-all group (#207)

### Fixed
- tighten POV facts char-budget to keep brief under MCP cap (#208)

## [1.22.0] - 2026-05-07

### Added
- add series_evolution field per character (#205, D-3 of #195) (#206)
- add bootstrap-book-from-series skill (#203, D-2 of #195) (#204)
- auto-copy recurring character files from prior book in series (#196) (#202)
- add harvest-character-evolution skill (#200, D-1 of #195) (#201)
- add series-tracker book_slug resolver (#194) (#199)

## [1.21.1] - 2026-05-06

### Fixed
- extend VALID_ROLES with love-interest, mentor, foil, herald, confidant (#193) (#198)
- skip series-character-trackers in validate_character (#192) (#197)

## [1.21.0] - 2026-05-06

### Changed
- add char-size trigger to issue #138 watcher (#191)
- split into fiction + memoir variants (audit H-3, #176) (#190)
- establish skill-bloat budget rule (audit Rec 10, #178) (#189)
- sweep 7 likely-dead tools — deprecate 4, document 3 as utilities (audit M-5) (#188)
- split into fiction + memoir variants (audit H-4) (#187)
- extract memoir path into chapter-writer-memoir skill (#174 PR C) (#186)
- dedup Mode A/B Pre-Logic Audit into shared section (#174 PR B) (#185)
- trim brief schema to critical-action lines (#174 PR A) (#184)
- Sprint 1 quick-wins from audit (epic #179) (#181)

### Fixed
- suppress DeprecationWarning in test_get_character (audit M-5 follow-up)
- resolve character aliases in scan_for_named_characters (#183)
- modernize + activate validate_character hook (audit H-1) (#180)
- enforce author profile Writing Discoveries at draft save-time (#172) (#173)

## [1.20.3] - 2026-05-05

### Fixed
- char-budget trim for pov_relevant_facts (#170) (#171)

## [1.20.2] - 2026-05-05

### Changed
- ignore .git-workflow/ skill state directory

### Fixed
- word-boundary token match for multi-token POV names (#168) (#169)

## [1.20.1] - 2026-05-05

### Changed
- drop obsolete Revision Impact Tracker references after #161/#164 (#166)

### Fixed
- drop canon_brief.current_facts from chapter_writing_brief inline (#165) (#167)

## [1.20.0] - 2026-05-05

### Added
- canon_brief projector for canon-log/people-log scope-truncation fix (Issue #161) (#164)
- add pov_character_state field for sensory plausibility (#160) (#163)
- add update_character_snapshot + chapter-writer step 7b write-back (#162)

### Changed
- chapter-writer source discipline hardening (epic #158) (#159)

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
[1.20.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.20.0
[1.20.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.20.1
[1.20.2]: https://github.com/markus-michalski/storyforge/releases/tag/v1.20.2
[1.20.3]: https://github.com/markus-michalski/storyforge/releases/tag/v1.20.3
[1.21.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.21.0
[1.21.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.21.1
[1.22.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.22.0
[1.22.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.22.1
[1.23.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.23.0
[1.24.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.24.0
[1.25.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.25.0
[1.25.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.25.1
[1.25.2]: https://github.com/markus-michalski/storyforge/releases/tag/v1.25.2
[1.26.0]: https://github.com/markus-michalski/storyforge/releases/tag/v1.26.0
[1.26.1]: https://github.com/markus-michalski/storyforge/releases/tag/v1.26.1
[1.26.2]: https://github.com/markus-michalski/storyforge/releases/tag/v1.26.2
[2.0.0]: https://github.com/markus-michalski/storyforge/releases/tag/v2.0.0
[2.0.1]: https://github.com/markus-michalski/storyforge/releases/tag/v2.0.1
[2.1.0]: https://github.com/markus-michalski/storyforge/releases/tag/v2.1.0
[2.2.0]: https://github.com/markus-michalski/storyforge/releases/tag/v2.2.0
[2.2.1]: https://github.com/markus-michalski/storyforge/releases/tag/v2.2.1
[2.2.2]: https://github.com/markus-michalski/storyforge/releases/tag/v2.2.2
[3.0.0]: https://github.com/markus-michalski/storyforge/releases/tag/v3.0.0
[3.0.1]: https://github.com/markus-michalski/storyforge/releases/tag/v3.0.1
[3.0.2]: https://github.com/markus-michalski/storyforge/releases/tag/v3.0.2
[3.1.0]: https://github.com/markus-michalski/storyforge/releases/tag/v3.1.0
[3.2.0]: https://github.com/markus-michalski/storyforge/releases/tag/v3.2.0
[3.2.1]: https://github.com/markus-michalski/storyforge/releases/tag/v3.2.1
[3.2.2]: https://github.com/markus-michalski/storyforge/releases/tag/v3.2.2
[3.3.0]: https://github.com/markus-michalski/storyforge/releases/tag/v3.3.0
[3.3.1]: https://github.com/markus-michalski/storyforge/releases/tag/v3.3.1
