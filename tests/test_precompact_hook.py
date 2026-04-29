"""Tests for the PreCompact CLAUDE.md sync hook."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hooks.precompact_sync_claudemd import (
    _extract_user_text,
    _read_transcript,
    run,
)
from tools.claudemd.manager import get_claudemd, init_claudemd

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _write_transcript(path: Path, entries: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


class TestReadTranscript:
    def test_reads_jsonl(self, tmp_path):
        path = tmp_path / "t.jsonl"
        _write_transcript(path, [{"type": "user", "message": {"content": "hi"}}, {"type": "assistant"}])
        entries = _read_transcript(path)
        assert len(entries) == 2

    def test_missing_returns_empty(self, tmp_path):
        assert _read_transcript(tmp_path / "nope.jsonl") == []

    def test_skips_invalid_lines(self, tmp_path):
        path = tmp_path / "t.jsonl"
        path.write_text('{"valid": 1}\nnot-json\n{"valid": 2}\n', encoding="utf-8")
        assert len(_read_transcript(path)) == 2


class TestExtractUserText:
    def test_string_content(self):
        entries = [
            {"type": "user", "message": {"content": "Regel: X"}},
            {"type": "assistant", "message": {"content": "ignored"}},
        ]
        assert _extract_user_text(entries) == "Regel: X"

    def test_block_content(self):
        entries = [
            {
                "type": "user",
                "message": {"content": [{"type": "text", "text": "Callback: Gary"}]},
            }
        ]
        assert _extract_user_text(entries) == "Callback: Gary"

    def test_ignores_assistant(self):
        entries = [{"type": "assistant", "message": {"content": "Regel: no"}}]
        assert _extract_user_text(entries) == ""


class TestRun:
    @pytest.fixture
    def book_setup(self, tmp_path):
        """Set up a book with CLAUDE.md and a mock state.json pointing to it."""
        content_root = tmp_path / "books"
        book_dir = content_root / "projects" / "test-book"
        book_dir.mkdir(parents=True)
        (book_dir / "README.md").write_text("# Test Book\n", encoding="utf-8")

        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps({"session": {"last_book": "test-book"}}),
            encoding="utf-8",
        )

        config = {"paths": {"content_root": str(content_root)}}
        init_claudemd(config, PLUGIN_ROOT, "test-book", facts={"pov": "first"})

        return {"config": config, "state_path": state_path}

    def test_extracts_and_persists(self, book_setup, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        _write_transcript(
            transcript,
            [
                {"type": "user", "message": {"content": "Regel: keep it tight"}},
                {"type": "user", "message": {"content": "Callback: Gary the cat"}},
                {"type": "user", "message": {"content": "just chatting"}},
            ],
        )

        with (
            patch("tools.shared.config.STATE_PATH", book_setup["state_path"]),
            patch("tools.shared.config.load_config", return_value=book_setup["config"]),
        ):
            result = run({"transcript_path": str(transcript)})

        assert result["book"] == "test-book"
        assert result["counts"]["rule"] == 1
        assert result["counts"]["callback"] == 1
        assert result["counts"]["workflow"] == 0

        content = get_claudemd(book_setup["config"], "test-book")
        assert "keep it tight" in content
        assert "Gary the cat" in content

    def test_skip_no_transcript(self):
        assert run({}) == {"skipped": "no transcript_path"}

    def test_skip_no_session(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("", encoding="utf-8")
        missing_state = tmp_path / "nonexistent-state.json"
        with patch("tools.shared.config.STATE_PATH", missing_state):
            result = run({"transcript_path": str(transcript)})
        assert result == {"skipped": "no active book in session"}
