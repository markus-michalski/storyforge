"""Tests for StoryForge PostToolUse hooks."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

from hooks import validate_chapter as vc
from hooks.validate_character import validate_character


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path, claudemd_body: str | None = None) -> Path:
    """Create a minimal book scaffold and return the book root."""
    book = tmp_path / "blood-and-binary"
    (book / "chapters" / "01-intro").mkdir(parents=True)
    (book / "README.md").write_text("# Blood & Binary\n", encoding="utf-8")
    if claudemd_body is not None:
        (book / "CLAUDE.md").write_text(claudemd_body, encoding="utf-8")
    return book


def _write_draft(book: Path, body: str, chapter: str = "01-intro") -> Path:
    draft = book / "chapters" / chapter / "draft.md"
    draft.write_text(body, encoding="utf-8")
    return draft


# ---------------------------------------------------------------------------
# validate_chapter() — pure-function behavior
# ---------------------------------------------------------------------------


class TestValidateChapter:
    def test_ignores_non_chapter_files(self):
        assert vc.validate_chapter("/some/other/file.md") == []

    def test_ignores_readme(self):
        assert vc.validate_chapter("/project/chapters/01-intro/README.md") == []

    def test_detects_ai_tells(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "She delved into the tapestry of nuanced experiences, "
                "each thread a vibrant testament to the intricate myriad "
                "of unprecedented journeys she had embarked upon. "
                "The beacon of hope resonated with a pivotal force. " * 3
            ),
        )

        findings = vc.validate_chapter(str(draft))
        ai_warns = [f for f in findings if f.category == "ai_tell"]
        assert len(ai_warns) > 3
        assert all(f.severity == vc.SEVERITY_WARN for f in ai_warns)

    def test_clean_prose_passes(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "The door slammed. She froze, one hand on the railing, "
                "the other clutching a paper bag from the Korean grocery "
                "on Seventh. The stairs smelled like wet concrete and old "
                "cigarettes. Three flights up, apartment 4B, the deadbolt "
                "she'd been meaning to replace since February. "
                "Her keys jangled. Too loud in the silence. "
                "Something was wrong. She could feel it — that prickle "
                "at the back of her neck, the one her mother called "
                "'the animal knowing.' Twenty-eight years of ignoring it. "
                "Tonight she listened." * 3
            ),
        )

        findings = vc.validate_chapter(str(draft))
        ai_warns = [f for f in findings if f.category == "ai_tell"]
        assert ai_warns == []

    def test_skips_short_drafts(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# Chapter 1\n\n")
        assert vc.validate_chapter(str(draft)) == []

    def test_blocks_book_rule_violation(self, tmp_path):
        # Book CLAUDE.md with a backtick-wrapped banned literal — the same
        # syntax the existing manuscript-checker already understands.
        book = _make_book(
            tmp_path,
            claudemd_body=(
                "# Blood & Binary\n\n"
                "## Rules\n"
                "- Do not use `clocked` as a verb for noticing/realizing — "
                "reader dislikes the word.\n"
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the door from across the room. The handle "
                "looked wrong. He shifted his weight, kept the bag tight "
                "against his ribs, and waited for the next breath. " * 5
            ),
        )

        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert len(blocking) >= 1
        assert any(f.category == "book_rule_violation" for f in blocking)
        assert any("clocked" in f.message for f in blocking)
        assert all(f.line is not None for f in blocking)

    def test_clean_prose_with_book_claudemd_passes(self, tmp_path):
        book = _make_book(
            tmp_path,
            claudemd_body=(
                "# Blood & Binary\n\n"
                "## Rules\n"
                "- Do not use `clocked` as a verb.\n"
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo noticed the door from across the room. The handle "
                "looked wrong. He shifted his weight, kept the bag tight "
                "against his ribs, and waited for the next breath. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert blocking == []

    def test_double_quoted_phrases_do_not_trigger_block(self, tmp_path):
        """Hook only honors backtick patterns. Double-quoted phrases in
        rules are advisory text only — typically positive examples or
        replacement suggestions — and must not produce hard-block
        findings (see #87)."""
        book = _make_book(
            tmp_path,
            claudemd_body=(
                "# Book\n\n"
                "## Rules\n"
                "- Avoid \"clocked\" as a verb. Replace with "
                "\"noticed\" or \"registered\".\n"
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the room and let his shoulders drop. "
                "The bag slid off the bench. He counted three breaths "
                "before he turned to face the door. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        # Quoted phrases are not block patterns — only backticks are.
        assert blocking == []

    def test_backtick_regex_pattern_with_alternation(self, tmp_path):
        """Backticks containing regex metacharacters compile as regex."""
        book = _make_book(
            tmp_path,
            claudemd_body=(
                "# Book\n\n"
                "## Rules\n"
                "- Avoid `the (specific|particular|certain) [a-z]+ that` "
                "as filler.\n"
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "She noticed the specific quietude that follows a slammed "
                "door. The room held its breath. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert len(blocking) >= 1

    def test_blocks_meta_narrative_callback_phrase(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 22\n\n"
            + (
                "He stepped into the corridor. The Ch 15 callback was, "
                "technically, funny. The wallpaper smelled like rain. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        # Both "Ch 15" and "callback" should fire.
        assert len(meta) >= 2
        assert all(f.severity == vc.SEVERITY_BLOCK for f in meta)

    def test_blocks_foreshadow_in_prose(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 4\n\n"
            + (
                "The lamp on the table foreshadowed the long night ahead. "
                "She watched it without thinking. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert any("foreshadow" in f.message.lower() for f in meta)

    def test_blocks_calls_back_to(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 6\n\n"
            + (
                "The smell of pine calls back to the cabin scene in chapter "
                "three. He felt his shoulders drop. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert any("calls back to" in f.message.lower() for f in meta)

    def test_blocks_parallels_her_earlier(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 7\n\n"
            + (
                "Her hand on the door parallels her earlier reluctance, "
                "the one she had carried into the cottage. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert any("parallels" in f.message.lower() for f in meta)

    def test_html_comment_is_ignored(self, tmp_path):
        """Outline scaffolding inside HTML comments may use structural
        language without triggering the hook."""
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 5\n\n"
            "<!-- Ch 4 callback: the cabin pine smell. Foreshadow the trail. -->\n\n"
            + (
                "He stepped into the corridor. The wallpaper smelled like "
                "rain on cedar. She had not slept. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert meta == []

    def test_html_comment_does_not_shield_following_prose(self, tmp_path):
        """Multi-line HTML comment should end before later prose, so a
        meta-narrative phrase after the comment still fires."""
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 8\n\n"
            "<!--\n"
            "Ch 6 callback: the deferred-beer deal.\n"
            "-->\n\n"
            + (
                "The Ch 6 callback was funny in retrospect. He turned "
                "the page. The book smelled like dust. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert any("Ch 6" in f.message for f in meta)
        # And callback also fires.
        assert any("callback" in f.message.lower() for f in meta)

    def test_clean_prose_no_meta_narrative(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 9\n\n"
            + (
                "She turned the corner and the smell of bread reached her "
                "before the lamplight did. The kitchen door was open. "
                "Her brother had been baking again. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert meta == []

    def test_word_boundaries_avoid_false_positives(self, tmp_path):
        """'called' must not match 'calls back to', 'channel' must not
        match 'Ch \\d+', etc."""
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 10\n\n"
            + (
                "She called him back later. The channel was rough. "
                "He paralleled her stride down the dock without thinking. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert meta == []

    def test_block_via_main_for_meta_narrative(self, tmp_path, monkeypatch, capsys):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 22\n\n"
            + (
                "She crossed the room. The Ch 15 callback was, technically, "
                "funny. The wallpaper smelled like rain. " * 5
            ),
        )
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 2
        err = capsys.readouterr().err
        assert "meta-narrative" in err.lower() or "callback" in err.lower()

    def test_backtick_regex_does_not_match_unrelated_text(self, tmp_path):
        book = _make_book(
            tmp_path,
            claudemd_body=(
                "# Book\n\n"
                "## Rules\n"
                "- Avoid `the (specific|particular|certain) [a-z]+ that` "
                "as filler.\n"
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "The door slammed. She held her breath, counted to four, "
                "then exhaled into the fabric of her sleeve. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert blocking == []


# ---------------------------------------------------------------------------
# Mode resolution (strict vs warn)
# ---------------------------------------------------------------------------


class TestResolveMode:
    def test_default_is_strict_when_no_book_root(self, tmp_path):
        path = tmp_path / "loose-file.md"
        path.write_text("nothing", encoding="utf-8")
        assert vc._resolve_mode(path) == "strict"

    def test_default_is_strict_without_claudemd(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "strict"

    def test_default_is_strict_without_frontmatter(self, tmp_path):
        book = _make_book(tmp_path, claudemd_body="# Book\n\nNo frontmatter.\n")
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "strict"

    def test_warn_mode_via_frontmatter(self, tmp_path):
        body = (
            "---\n"
            "linter_mode: warn\n"
            "---\n\n"
            "# Book\n\n## Rules\n- Avoid `clocked`.\n"
        )
        book = _make_book(tmp_path, claudemd_body=body)
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "warn"

    def test_strict_mode_explicit(self, tmp_path):
        body = '---\nlinter_mode: "strict"\n---\n\n# Book\n'
        book = _make_book(tmp_path, claudemd_body=body)
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "strict"

    def test_invalid_mode_falls_back_to_strict(self, tmp_path):
        body = "---\nlinter_mode: chaotic\n---\n\n# Book\n"
        book = _make_book(tmp_path, claudemd_body=body)
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "strict"


# ---------------------------------------------------------------------------
# Hook entry point — JSON stdin protocol + exit codes
# ---------------------------------------------------------------------------


def _run_hook(payload: dict | None, monkeypatch, capsys) -> int:
    """Invoke vc.main() with a faked stdin/argv, return exit code."""
    if payload is None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    else:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    # Force isatty=False so _read_payload reads stdin
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(sys, "argv", ["validate_chapter.py"])
    return vc.main()


class TestMainEntryPoint:
    def test_no_payload_no_argv_returns_zero(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
        monkeypatch.setattr(sys, "argv", ["validate_chapter.py"])
        assert vc.main() == 0

    def test_unwatched_tool_is_ignored(self, monkeypatch, capsys):
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/anything/draft.md"},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_write_to_unrelated_file_is_ignored(self, monkeypatch, capsys):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/notes.md"},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_block_exit_2_in_strict_mode(self, tmp_path, monkeypatch, capsys):
        book = _make_book(
            tmp_path,
            claudemd_body=(
                "# Book\n\n## Rules\n- Avoid `clocked` as a verb.\n"
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the room and let his shoulders drop. "
                "The bag slid off the bench. He counted three breaths "
                "before he turned to face the door. " * 5
            ),
        )
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        captured = capsys.readouterr()
        assert rc == 2
        assert "blocked this write" in captured.err.lower()
        assert "clocked" in captured.err

    def test_warn_mode_does_not_block(self, tmp_path, monkeypatch, capsys):
        body = (
            "---\nlinter_mode: warn\n---\n\n"
            "# Book\n\n## Rules\n- Avoid `clocked` as a verb.\n"
        )
        book = _make_book(tmp_path, claudemd_body=body)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the room and let his shoulders drop. "
                "The bag slid off the bench. He counted three breaths "
                "before he turned to face the door. " * 5
            ),
        )
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 0

    def test_clean_prose_returns_zero(self, tmp_path, monkeypatch, capsys):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "The door slammed. She froze, one hand on the railing, "
                "the other clutching a paper bag from the Korean grocery "
                "on Seventh. Twenty-eight years of ignoring the prickle "
                "at the back of her neck. Tonight she listened. " * 5
            ),
        )
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 0


# ---------------------------------------------------------------------------
# Integration: invoke the hook script as a subprocess
# ---------------------------------------------------------------------------


class TestHookSubprocess:
    """Run the hook as Claude Code would — fresh process, JSON on stdin."""

    def _hook_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "hooks" / "validate_chapter.py"

    def test_strict_block_via_subprocess(self, tmp_path):
        book = _make_book(
            tmp_path,
            claudemd_body=(
                "# Book\n\n## Rules\n- Avoid `clocked` as a verb.\n"
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the room and let his shoulders drop. "
                "The bag slid off the bench. He counted three breaths "
                "before he turned to face the door. " * 5
            ),
        )
        payload = json.dumps(
            {"tool_name": "Write", "tool_input": {"file_path": str(draft)}}
        )
        result = subprocess.run(
            [sys.executable, str(self._hook_path())],
            input=payload,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 2, result.stderr
        assert "clocked" in result.stderr

    def test_unwatched_tool_subprocess(self, tmp_path):
        payload = json.dumps(
            {"tool_name": "Read", "tool_input": {"file_path": "/x/draft.md"}}
        )
        result = subprocess.run(
            [sys.executable, str(self._hook_path())],
            input=payload,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# validate_character — preserved from prior suite
# ---------------------------------------------------------------------------


class TestValidateCharacter:
    def test_ignores_non_character_files(self):
        assert validate_character("/some/other/file.md") == []

    def test_ignores_index(self):
        assert validate_character("/project/characters/INDEX.md") == []

    def test_valid_character(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text(
            '---\nname: "Alex"\nrole: "protagonist"\nstatus: "Concept"\n---\n\n'
            "# Alex\n\n## Want vs. Need\n\nContent.\n\n## Fatal Flaw\n\nContent.\n\n"
            "## The Ghost\n\nContent.\n\n## Motivation Chain\n\nContent.\n",
            encoding="utf-8",
        )
        assert validate_character(str(char_file)) == []

    def test_missing_frontmatter(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text("# Alex\n\nNo frontmatter here.\n", encoding="utf-8")
        issues = validate_character(str(char_file))
        assert any("Missing YAML frontmatter" in i for i in issues)

    def test_missing_required_sections(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text(
            '---\nname: "Alex"\nrole: "protagonist"\nstatus: "Concept"\n---\n\n'
            "# Alex\n\nNo required sections.\n",
            encoding="utf-8",
        )
        issues = validate_character(str(char_file))
        assert any("Want vs. Need" in i for i in issues)
        assert any("Fatal Flaw" in i for i in issues)

    def test_minor_characters_skip_sections(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "barista.md"
        char_file.write_text(
            '---\nname: "Barista"\nrole: "minor"\nstatus: "Concept"\n---\n\n'
            "# Barista\n\nJust a minor character.\n",
            encoding="utf-8",
        )
        issues = validate_character(str(char_file))
        assert not any("Want vs. Need" in i for i in issues)
