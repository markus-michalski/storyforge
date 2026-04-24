## Description

<!-- Brief description of the change and the problem it solves. -->

## Type of Change

- [ ] feat: New feature (minor version bump)
- [ ] fix: Bug fix (patch version bump)
- [ ] docs: Documentation only
- [ ] chore: Maintenance (no version bump)
- [ ] refactor: Code refactoring without behavior change
- [ ] BREAKING CHANGE (major version bump)

## Checklist

### Before Submitting

- [ ] I have read the [CONTRIBUTING.md](../CONTRIBUTING.md) guidelines
- [ ] I have signed the [Contributor License Agreement (CLA)](../CLA.md) via cla-assistant
- [ ] My commits follow [Conventional Commits](https://conventionalcommits.org/)
- [ ] I included the co-author line when applicable: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- [ ] All tests pass locally (`pytest`)
- [ ] `ruff check .` passes
- [ ] I have updated `CHANGELOG.md` under the `[Unreleased]` section

### Version Updates (release PRs only)

- [ ] I have updated `.claude-plugin/plugin.json` version
- [ ] Version matches the `CHANGELOG.md` release heading

### Documentation

- [ ] I have updated `CLAUDE.md` if workflow rules changed
- [ ] I have updated `README.md` if user-facing behavior changed
- [ ] I have added/updated `SKILL.md` if a skill was added or changed

### Testing

**Automated CI checks (run automatically):**
- pytest (17 test files)
- ruff lint
- JSON validation (`.claude-plugin/plugin.json`, `.mcp.json`)
- SKILL.md frontmatter validation

**Manual testing details:**
<!-- Describe manual testing performed, if applicable. -->

## Related Issues

Closes #<!-- issue number -->
