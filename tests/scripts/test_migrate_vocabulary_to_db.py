"""Tests for scripts/migrate_vocabulary_to_db.py and tools/author/vocabulary_parser.py.

Issue #293 — vocabulary.md → author_discoveries DB migration (Cluster C).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import tools.db.connection as _conn_mod
from tools.author.vocabulary_parser import parse_vocabulary_banned_words
from tools.db.author_discoveries import get_discoveries
from tools.db.connection import ensure_authors_schema, open_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MINIMAL_VOCAB = """\
# Vocabulary Profile: Test Author

## Banned Words — AI Tells

### Absolutely Forbidden

- delve
- tapestry
- nuanced / nuance

### Forbidden Hedging Phrases
- it's worth noting that
- in many cases

## Preferred Vocabulary — Evidence-Based

### Dialog Tags

| Tag | Usage |
|-----|-------|
| said | Primary |

## Sentence Patterns

### Test Author Uses:
- Fragments for impact.
"""

_VOCAB_WITH_ANNOTATIONS = """\
# Vocabulary

## Banned Words — AI Tells

- registered it and did not _(added 2026-06-24 — source: harvest-author-rules)_
- did not name it _(added 2026-06-24 — source: harvest-author-rules)_
- dynamic (as vague intensifier)

## Banned Words — Reader Flagged

- **clocked** (as verb for noticing/realizing) — reader flagged. Alternatives: *noticed*. _(emerged from book, 2026-05)_
"""

_VOCAB_WITH_STRUCTURAL = """\
# Vocabulary

## Banned Words — AI Tells

### Forbidden Structural Patterns
- Triadic lists ("brave, intelligent, and kind") — use pairs or fours instead
- Uniform paragraph length — vary wildly
"""


@pytest.fixture
def author_setup(tmp_path, monkeypatch):
    authors_root = tmp_path / "authors"
    authors_root.mkdir()
    author_dir = authors_root / "test-author"
    author_dir.mkdir()
    (author_dir / "profile.md").write_text(
        '---\nname: "Test Author"\nslug: "test-author"\n---\n',
        encoding="utf-8",
    )

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_conn_mod, "DB_DIR", db_dir)

    return {"authors_root": authors_root, "author_dir": author_dir, "db_dir": db_dir}


def _open_authors_db(db_dir: Path):
    db_path = db_dir / "authors.db"
    conn = open_db(db_path)
    ensure_authors_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# parse_vocabulary_banned_words
# ---------------------------------------------------------------------------


class TestParseVocabularyBannedWords:
    def test_extracts_simple_bullets_from_banned_section(self):
        entries = parse_vocabulary_banned_words(_MINIMAL_VOCAB)
        texts = [e for e in entries]
        assert any("delve" in t for t in texts)
        assert any("tapestry" in t for t in texts)
        assert any("nuanced" in t for t in texts)

    def test_extracts_from_multiple_banned_subsections(self):
        entries = parse_vocabulary_banned_words(_MINIMAL_VOCAB)
        texts = " ".join(entries)
        assert "it's worth noting" in texts
        assert "in many cases" in texts

    def test_ignores_preferred_vocabulary_section(self):
        entries = parse_vocabulary_banned_words(_MINIMAL_VOCAB)
        texts = " ".join(entries)
        assert "said" not in texts
        assert "Dialog Tags" not in texts

    def test_ignores_sentence_patterns_section(self):
        entries = parse_vocabulary_banned_words(_MINIMAL_VOCAB)
        texts = " ".join(entries)
        assert "Fragments for impact" not in texts

    def test_strips_date_annotations(self):
        entries = parse_vocabulary_banned_words(_VOCAB_WITH_ANNOTATIONS)
        for e in entries:
            assert "_(added" not in e
            assert "_(emerged" not in e

    def test_extracts_from_reader_flagged_section(self):
        entries = parse_vocabulary_banned_words(_VOCAB_WITH_ANNOTATIONS)
        texts = " ".join(entries)
        assert "clocked" in texts

    def test_handles_structural_patterns(self):
        entries = parse_vocabulary_banned_words(_VOCAB_WITH_STRUCTURAL)
        texts = " ".join(entries)
        assert "Triadic lists" in texts
        assert "Uniform paragraph length" in texts

    def test_skips_table_rows(self):
        entries = parse_vocabulary_banned_words(_MINIMAL_VOCAB)
        for e in entries:
            assert not e.startswith("|")

    def test_returns_list(self):
        entries = parse_vocabulary_banned_words(_MINIMAL_VOCAB)
        assert isinstance(entries, list)
        assert len(entries) > 0

    def test_no_empty_entries(self):
        entries = parse_vocabulary_banned_words(_MINIMAL_VOCAB)
        assert all(e.strip() for e in entries)

    def test_empty_vocabulary_returns_empty_list(self):
        entries = parse_vocabulary_banned_words("# Vocabulary\n\n## Preferred Words\n\n- said\n")
        assert entries == []


# ---------------------------------------------------------------------------
# migrate_author_vocabulary (integration)
# ---------------------------------------------------------------------------


class TestMigrateAuthorVocabulary:
    def test_inserts_banned_words_into_db(self, author_setup):
        from tools.author.vocabulary_migrator import migrate_author

        vocab_path = author_setup["author_dir"] / "vocabulary.md"
        vocab_path.write_text(_MINIMAL_VOCAB, encoding="utf-8")

        inserted = migrate_author(
            author_slug="test-author",
            vocab_path=vocab_path,
            execute=True,
        )
        assert inserted > 0

        conn = _open_authors_db(author_setup["db_dir"])
        rows = get_discoveries(conn, "test-author", discovery_type="donts")
        conn.close()
        assert len(rows) >= inserted

    def test_idempotent_second_run_inserts_zero(self, author_setup):
        from tools.author.vocabulary_migrator import migrate_author

        vocab_path = author_setup["author_dir"] / "vocabulary.md"
        vocab_path.write_text(_MINIMAL_VOCAB, encoding="utf-8")

        first = migrate_author("test-author", vocab_path, execute=True)
        second = migrate_author("test-author", vocab_path, execute=True)
        assert first > 0
        assert second == 0

    def test_dry_run_inserts_nothing(self, author_setup):
        from tools.author.vocabulary_migrator import migrate_author

        vocab_path = author_setup["author_dir"] / "vocabulary.md"
        vocab_path.write_text(_MINIMAL_VOCAB, encoding="utf-8")

        migrate_author("test-author", vocab_path, execute=False)

        conn = _open_authors_db(author_setup["db_dir"])
        rows = get_discoveries(conn, "test-author", discovery_type="donts")
        conn.close()
        assert len(rows) == 0

    def test_strips_annotations_before_insert(self, author_setup):
        from tools.author.vocabulary_migrator import migrate_author

        vocab_path = author_setup["author_dir"] / "vocabulary.md"
        vocab_path.write_text(_VOCAB_WITH_ANNOTATIONS, encoding="utf-8")

        migrate_author("test-author", vocab_path, execute=True)

        conn = _open_authors_db(author_setup["db_dir"])
        rows = get_discoveries(conn, "test-author", discovery_type="donts")
        conn.close()
        for row in rows:
            assert "_(added" not in row["text"]
            assert "_(emerged" not in row["text"]

    def test_missing_vocabulary_file_returns_zero(self, author_setup):
        from tools.author.vocabulary_migrator import migrate_author

        vocab_path = author_setup["author_dir"] / "vocabulary.md"
        # File does not exist
        result = migrate_author("test-author", vocab_path, execute=True)
        assert result == 0
