# Security Policy

## Reporting a Vulnerability

**Do not open public issues for security vulnerabilities.**

Use GitHub's [Private Vulnerability Reporting](https://github.com/markus-michalski/storyforge/security/advisories/new) feature to report security issues privately. You will receive an acknowledgement within 72 hours.

For non-sensitive security questions, open a regular issue.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

Security fixes are released as patch versions on the latest minor.

## Code Review Requirements

### Workflow Files (`.github/workflows/*`)

**Workflow files execute code in CI/CD and require strict security review.**

Requirements for workflow changes:
- Must be reviewed and approved by @markus-michalski
- Manual security audit required (no automated approval)
- Changes must be explained in the PR description
- Do not include executable code in PR descriptions or issue comments

Security considerations:
- Workflows run with `GITHUB_TOKEN` access
- Can read repository contents
- Can create releases and tags
- Can access repository secrets (if configured)

### Plugin Manifest Files

Changes to `.claude-plugin/plugin.json`:
- Trigger version recognition in plugin marketplaces
- Must be reviewed by the maintainer
- Version bumps must match `CHANGELOG.md`

### AI-Assisted Development

This project uses Claude Code (AI pair programming). When contributing:

**DO:**
- Review all code changes carefully before submitting
- Use Conventional Commits format
- Follow existing code patterns
- Test changes locally before opening a PR

**DO NOT:**
- Include prompts or instructions for AI in code comments or docstrings
- Attempt to manipulate AI review via PR descriptions
- Include executable commands or scripts in PR descriptions
- Assume AI-reviewed code is automatically safe

## Secrets and Credentials

**Never commit secrets to this repository.** This includes:
- API keys (Anthropic, OpenAI, Claude, etc.)
- Access tokens (GitHub PATs, etc.)
- Private keys (`.pem`, `.key` files)
- Credentials (passwords, service accounts)
- Environment files (`.env`, `config.local.yaml`)

User-specific configuration lives at `~/.storyforge/config.yaml` — outside this repository.

If you accidentally commit a secret:
1. Immediately revoke or rotate the credential
2. Contact the maintainer via Private Vulnerability Reporting
3. Do NOT just delete the commit — it remains in git history

## Dependencies

Python dependencies are pinned in `requirements.txt`. Dependabot scans weekly and opens PRs for updates. When adding dependencies:
- Prefer well-maintained, popular packages
- Check for known vulnerabilities (e.g. via `pip-audit`)
- Pin to specific versions for reproducibility

## Security Best Practices for Users

If you're using this plugin:

1. **Keep your config secure**: `~/.storyforge/config.yaml` may contain local paths and settings
2. **Use `.gitignore`**: Never commit your book projects to public repos accidentally
3. **Review generated content**: Always review AI-generated prose before publishing
4. **Separate repos**: Keep this plugin (public) separate from your manuscripts (private)

## Attribution

This project uses AI assistance (Claude Code) for development. Commits include the co-author line:
```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

This is for transparency. All AI-generated code is reviewed by the maintainer before merging.
