"""Unit tests for tools.analysis.manuscript.rules — rule parser + scanner."""

from __future__ import annotations

import sqlite3

import pytest
from pathlib import Path

from tools.analysis.manuscript.rules import (
    _extract_patterns_from_rule,
    _read_book_rules,
    _rule_label,
    _scan_book_rules,
)


@pytest.fixture
def patch_db_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import tools.db.connection as _conn

    monkeypatch.setattr(_conn, "DB_DIR", tmp_path / "db")
    return tmp_path / "db"


def _seed_rules(db_dir: Path, book_slug: str, rules: list[str], book_num: int = 1) -> None:
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_dir / f"{book_slug}.db"))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS book_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_num INTEGER,
            rule_type TEXT NOT NULL,
            text TEXT NOT NULL,
            added_at TEXT DEFAULT '',
            UNIQUE(book_num, rule_type, text)
        )
        """
    )
    for rule in rules:
        conn.execute(
            "INSERT OR IGNORE INTO book_rules (book_num, rule_type, text) VALUES (?, ?, ?)",
            (book_num, "rule", rule),
        )
    conn.commit()
    conn.close()


class TestExtractPatternsFromRule:
    def test_backtick_literal(self) -> None:
        patterns = _extract_patterns_from_rule("Avoid `synergy` in narration.")
        assert len(patterns) == 1
        label, compiled = patterns[0]
        assert label == "synergy"
        assert compiled.search("the synergy here") is not None

    def test_backtick_with_regex_metachars(self) -> None:
        patterns = _extract_patterns_from_rule("Limit `(very|really)\\s+\\w+` adverb pile-ups.")
        assert len(patterns) == 1
        _label, compiled = patterns[0]
        assert compiled.search("very tired") is not None

    def test_quoted_with_ban_cue_extracts(self) -> None:
        patterns = _extract_patterns_from_rule('Banned phrase: "the worn-out construction".')
        assert any("worn-out" in label for label, _ in patterns)

    def test_quoted_without_ban_cue_skipped(self) -> None:
        # No ban cue → quoted phrase treated as example, not pattern.
        patterns = _extract_patterns_from_rule('Use "fresh imagery" instead of stale phrasing.')
        assert patterns == []

    def test_short_backtick_skipped(self) -> None:
        patterns = _extract_patterns_from_rule("Note `a` is too short to ban.")
        assert patterns == []


class TestRuleLabel:
    def test_extracts_bold_title(self) -> None:
        label = _rule_label("**No vague nouns** — avoid 'thing' as filler.")
        assert label == "No vague nouns"

    def test_falls_back_to_rule_text(self) -> None:
        label = _rule_label("Plain rule with no bold prefix.")
        assert "Plain rule" in label

    def test_truncates_long_titles(self) -> None:
        label = _rule_label("a" * 200)
        assert len(label) <= 80


class TestReadBookRules:
    def test_reads_rules_from_db(self, tmp_path: Path, patch_db_dir: Path) -> None:
        _seed_rules(patch_db_dir, tmp_path.name, ["First rule", "Second rule"])
        rules = _read_book_rules(tmp_path)
        assert rules == ["First rule", "Second rule"]

    def test_no_db_returns_empty(self, tmp_path: Path, patch_db_dir: Path) -> None:
        assert _read_book_rules(tmp_path) == []

    def test_db_with_single_rule_returns_it(self, tmp_path: Path, patch_db_dir: Path) -> None:
        _seed_rules(patch_db_dir, tmp_path.name, ["Real rule"])
        rules = _read_book_rules(tmp_path)
        assert rules == ["Real rule"]


class TestScanBookRules:
    def _build_book(self, tmp_path: Path, draft_text: str) -> Path:
        book = tmp_path / "demo"
        (book / "chapters" / "01-opening").mkdir(parents=True)
        (book / "chapters" / "01-opening" / "draft.md").write_text(draft_text, encoding="utf-8")
        return book

    def test_finds_rule_violation(self, tmp_path: Path, patch_db_dir: Path) -> None:
        book = self._build_book(tmp_path, "The synergy of the team was unmatched.\n")
        _seed_rules(patch_db_dir, "demo", ["Avoid `synergy` in narration."])
        findings = _scan_book_rules(book)
        assert len(findings) == 1
        assert findings[0].category == "book_rule_violation"
        assert findings[0].severity == "high"
        assert findings[0].source_rule.startswith("Avoid")

    def test_no_findings_when_clean(self, tmp_path: Path, patch_db_dir: Path) -> None:
        book = self._build_book(tmp_path, "Their teamwork was excellent.\n")
        _seed_rules(patch_db_dir, "demo", ["Avoid `synergy`."])
        assert _scan_book_rules(book) == []
