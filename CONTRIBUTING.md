# Contributing to StoryForge

Thank you for your interest. This document explains how to contribute and what to expect.

## Governance Model

StoryForge follows a **Benevolent Dictator For Life (BDFL)** model. [Markus Michalski](https://github.com/markus-michalski) is the sole maintainer with final say on all changes, direction, and releases. Contributions are welcome within that structure.

## License & CLA

**Important — read this before opening a PR:**

1. This project is licensed under the **[PolyForm Noncommercial License 1.0.0](LICENSE.md)**. It is source-available but **not** OSI Open Source. Commercial use is prohibited.
2. All contributors must sign the **[Contributor License Agreement (CLA)](CLA.md)** before their PR can be merged. The [cla-assistant.io](https://cla-assistant.io/) bot will comment on your PR with a one-click signing link.

Why a CLA? The CLA grants the maintainer the rights needed to keep the project viable (relicensing flexibility, legal protection). Without it, your contribution cannot be accepted.

## Branch Model

Single-branch model:

- **`main`** — the only long-lived branch. Always in a releasable state.
- **Feature branches** — short-lived, branched from `main`, merged via PR.

Branch naming:

- `feat/description` — new features
- `fix/description` — bug fixes
- `docs/description` — documentation
- `chore/description` — maintenance
- `refactor/description` — refactoring

## Development Workflow

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR-USERNAME/storyforge.git
cd storyforge
git remote add upstream https://github.com/markus-michalski/storyforge.git
```

### 2. Create a Feature Branch

```bash
git checkout main
git pull upstream main
git checkout -b feat/your-feature-name
```

### 3. Set Up Local Development

```bash
# Create venv for the MCP server
python3 -m venv ~/.storyforge/venv
~/.storyforge/venv/bin/pip install -r requirements.txt

# Install dev dependencies
~/.storyforge/venv/bin/pip install pytest ruff
```

### 4. Make Your Changes

Follow existing code patterns. For each change type:

- **New skill**: Create `skills/your-skill/SKILL.md` with frontmatter (`name`, `description`, `argument-hint` if applicable, `user-invocable: true`). Add routing entry to `CLAUDE.md`. Add entry to `skills/help/SKILL.md`.
- **New MCP tool**: Add to `servers/storyforge-server/`. Export via the server's tool registry. Document in `CLAUDE.md` under "MCP Server" section.
- **New template**: Add to `templates/`. Reference from the relevant skill.
- **New genre**: Add to `genres/{name}/README.md`. Update CLAUDE.md genre list.
- **Craft reference**: Add to `reference/craft/` or `reference/genre/`. Update skill loading instructions in CLAUDE.md.

### 5. Test Locally

```bash
# Run all tests
~/.storyforge/venv/bin/python -m pytest

# Lint
~/.storyforge/venv/bin/python -m ruff check .

# Format check
~/.storyforge/venv/bin/python -m ruff format --check .
```

### 6. Commit with Conventional Commits

Format: `<type>(<scope>): <subject>`

| Type | Version Bump |
|------|--------------|
| `feat:` | MINOR |
| `fix:` | PATCH |
| `feat!:` or `BREAKING CHANGE:` | MAJOR |
| `docs:`, `chore:`, `refactor:`, `test:` | None |

Examples:

```
feat(chapter-writer): add scene-by-scene mode
fix(mcp): handle missing canon-log gracefully
docs(contributing): clarify CLA process
chore(deps): bump ruff to 0.8.0
```

When working with Claude Code, include the co-author line:

```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### 7. Update the Changelog

Add an entry under `[Unreleased]` in `CHANGELOG.md`:

```markdown
## [Unreleased]

### Added
- feature description (#issue-number)

### Fixed
- bug description (#issue-number)
```

### 8. Push and Open a PR

```bash
git push -u origin feat/your-feature-name
```

Open a PR via the GitHub UI or:

```bash
gh pr create --base main
```

The PR template will guide you through the checklist. The CLA bot will comment with a signing link on first contribution.

## PR Review Process

1. **Automated checks** must pass (pytest, ruff, JSON validation, CLA signed)
2. **Maintainer review** — @markus-michalski reviews every PR personally. Expect feedback cycles.
3. **Squash merge** — all PRs are squash-merged into `main` with a Conventional Commit message
4. **Release** — the maintainer batches features into releases and cuts version tags

## Release Process (maintainer only)

1. Update `CHANGELOG.md`: move `[Unreleased]` entries to `[X.Y.Z] - YYYY-MM-DD`
2. Bump version in `.claude-plugin/plugin.json`
3. Commit: `chore: release X.Y.Z`
4. Tag: `git tag -a vX.Y.Z -m "Release X.Y.Z" && git push --tags`
5. Create GitHub Release from the tag

## Code Style

- **Python**: PEP 8, type hints, English comments. Ruff is the formatter and linter.
- **Markdown**: English for reference docs, skill docs, templates. User-facing skill output may be German per user configuration.
- **YAML frontmatter**: Required in all SKILL.md, book README.md, chapter README.md, character files.
- **No emojis** in code comments, skill files, or internal documentation (UTF8MB4 issues in integrations).

## What Does NOT Belong in a PR

- Generated book content (belongs in user's private repos)
- Claude API keys, GitHub tokens, or any secrets (see [SECURITY.md](.github/SECURITY.md))
- Commented-out code blocks without justification
- Unrelated refactoring bundled with a feature change
- Documentation for features that haven't shipped yet
- Changes to `LICENSE.md`, `CLA.md`, or `.github/CODEOWNERS` (maintainer-only)

## Questions

- **Usage questions** → [Documentation](https://faq.markus-michalski.net/en/plugins/storyforge)
- **Feature ideas** → Open a Feature Request issue
- **Bug reports** → Open a Bug Report issue
- **Security issues** → [Private Vulnerability Reporting](https://github.com/markus-michalski/storyforge/security/advisories/new)

## Code of Conduct

Be civil. Disagreements about craft are welcome and encouraged; personal attacks, harassment, or bad-faith behavior are not. The maintainer reserves the right to close issues or block users that cross that line, without explanation.
