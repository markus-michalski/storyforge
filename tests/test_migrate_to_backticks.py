"""Tests for the CLAUDE.md migration script.

Covers the in-process functions of ``tools.claudemd.migrate_to_backticks``
plus an end-to-end CLI smoke test in dry-run mode.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.claudemd.migrate_to_backticks import _migrate_text, main


SAMPLE_CLAUDEMD = """# Sample Book

## Rules

<!-- RULES:START -->
- Avoid "clocked" as a verb — reader edited it out twice.
- Do not use "began to" as an opener.
- Use "felt like" sparingly (no ban cue, advisory only).
- Avoid `pulsed` already in backticks — should not be touched.
- Limit the "specific kind of X that Y" construction.
<!-- RULES:END -->
"""


class TestMigrateText:
    def test_converts_avoid_quoted_phrase(self):
        new, changes = _migrate_text(SAMPLE_CLAUDEMD)
        assert "Avoid `clocked` as a verb" in new
        assert "Avoid \"clocked\"" not in new
        assert any("clocked" in after for _, _, after in changes)

    def test_converts_do_not_use(self):
        new, _ = _migrate_text(SAMPLE_CLAUDEMD)
        assert "Do not use `began to`" in new

    def test_advisory_quotes_stay(self):
        new, _ = _migrate_text(SAMPLE_CLAUDEMD)
        # No ban cue → should remain quoted.
        assert "Use \"felt like\" sparingly" in new

    def test_already_backticked_unchanged(self):
        new, _ = _migrate_text(SAMPLE_CLAUDEMD)
        assert "Avoid `pulsed` already in backticks" in new
        # No accidental double-wrapping.
        assert "``pulsed``" not in new

    def test_limit_with_qualifier(self):
        new, _ = _migrate_text(SAMPLE_CLAUDEMD)
        assert "Limit the `specific kind of X that Y` construction" in new

    def test_changes_count_matches_expectation(self):
        _, changes = _migrate_text(SAMPLE_CLAUDEMD)
        # Three rules should change: clocked, began to, specific kind of X that Y.
        assert len(changes) == 3

    def test_empty_input(self):
        new, changes = _migrate_text("")
        assert new == ""
        assert changes == []

    def test_preserves_trailing_newline(self):
        text_with = "- Avoid \"x\" please.\n"
        new, _ = _migrate_text(text_with)
        assert new.endswith("\n")

        text_without = "- Avoid \"x\" please."
        new_wo, _ = _migrate_text(text_without)
        assert not new_wo.endswith("\n")

    def test_non_bullet_lines_untouched(self):
        text = (
            "Some narrative paragraph mentioning \"clocked\" and avoid it.\n"
            "- Avoid \"clocked\" as a verb.\n"
        )
        new, changes = _migrate_text(text)
        assert "narrative paragraph mentioning \"clocked\"" in new
        assert "Avoid `clocked`" in new
        assert len(changes) == 1


class TestMigrateCLI:
    def _write_book(self, tmp_path: Path, body: str) -> Path:
        book = tmp_path / "sample-book"
        book.mkdir()
        (book / "CLAUDE.md").write_text(body, encoding="utf-8")
        return book

    def test_missing_claudemd_returns_error(self, tmp_path, capsys):
        book = tmp_path / "no-such-book"
        book.mkdir()
        rc = main([str(book)])
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_dry_run_shows_diff_without_writing(self, tmp_path, capsys):
        book = self._write_book(tmp_path, SAMPLE_CLAUDEMD)
        original = (book / "CLAUDE.md").read_text(encoding="utf-8")

        rc = main([str(book)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "would change" in captured.out
        # File unchanged.
        assert (book / "CLAUDE.md").read_text(encoding="utf-8") == original

    def test_no_changes_needed(self, tmp_path, capsys):
        body = "## Rules\n- Avoid `clocked` as a verb.\n"
        book = self._write_book(tmp_path, body)
        rc = main([str(book)])
        assert rc == 0
        assert "No changes needed" in capsys.readouterr().out

    def test_apply_writes_with_yes_confirmation(
        self, tmp_path, capsys, monkeypatch
    ):
        book = self._write_book(tmp_path, SAMPLE_CLAUDEMD)
        monkeypatch.setattr("builtins.input", lambda _: "y")
        rc = main([str(book), "--apply"])
        assert rc == 0
        new = (book / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Avoid `clocked` as a verb" in new

    def test_apply_aborts_on_no(self, tmp_path, capsys, monkeypatch):
        book = self._write_book(tmp_path, SAMPLE_CLAUDEMD)
        original = (book / "CLAUDE.md").read_text(encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _: "n")
        rc = main([str(book), "--apply"])
        assert rc == 0
        assert "Aborted" in capsys.readouterr().out
        assert (book / "CLAUDE.md").read_text(encoding="utf-8") == original


class TestMigrateSubprocess:
    """Smoke test the script as a subprocess (CLI invocation path)."""

    def test_dry_run_subprocess(self, tmp_path):
        book = tmp_path / "sample-book"
        book.mkdir()
        (book / "CLAUDE.md").write_text(SAMPLE_CLAUDEMD, encoding="utf-8")

        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.claudemd.migrate_to_backticks",
                str(book),
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
        assert "Avoid `clocked`" in result.stdout
        # File unchanged in dry-run.
        assert "Avoid \"clocked\"" in (book / "CLAUDE.md").read_text(
            encoding="utf-8"
        )
