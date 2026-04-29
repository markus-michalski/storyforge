"""Tests for ``tools.rule_writer``.

Covers write_book_rule, write_author_rule, write_global_rule, and promote_rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.rule_writer import (
    SCOPE_AUTHOR,
    SCOPE_BOOK,
    SCOPE_GLOBAL,
    promote_rule,
    write_author_rule,
    write_book_rule,
    write_global_rule,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CLAUDEMD_TEMPLATE = """\
# My Book — CLAUDE.md

## Rules

<!-- RULES:START -->
<!-- RULES:END -->

## Workflows

<!-- WORKFLOW:START -->
<!-- WORKFLOW:END -->
"""

_VOCABULARY_TEMPLATE = """\
# Author Vocabulary

## Banned Words

### Absolutely Forbidden

- clocked

### Forbidden Hedging Phrases

- to some extent
"""

_ANTI_AI_TEMPLATE = """\
# Anti-AI Patterns

## 1. Known AI Tells — Vocabulary

### Heavily Flagged Words and Phrases (AI Tell Indicators)

1. **Delve** — Notorious AI tell.
2. **Tapestry** — Almost never used by humans.

### Why These Words Signal AI

They hedge commitment.
"""


@pytest.fixture
def book_config(tmp_path: Path) -> dict:
    content_root = tmp_path / "books"
    book_dir = content_root / "projects" / "my-book"
    book_dir.mkdir(parents=True)
    claudemd = book_dir / "CLAUDE.md"
    claudemd.write_text(_CLAUDEMD_TEMPLATE, encoding="utf-8")
    return {"paths": {"content_root": str(content_root)}}


@pytest.fixture
def author_vocab(tmp_path: Path) -> Path:
    vocab_dir = tmp_path / "authors" / "test-author"
    vocab_dir.mkdir(parents=True)
    vocab_path = vocab_dir / "vocabulary.md"
    vocab_path.write_text(_VOCABULARY_TEMPLATE, encoding="utf-8")
    return tmp_path  # return storyforge_home


@pytest.fixture
def anti_ai_file(tmp_path: Path) -> Path:
    """Return a plugin_root with a real-ish anti-ai-patterns.md."""
    craft_dir = tmp_path / "reference" / "craft"
    craft_dir.mkdir(parents=True)
    (craft_dir / "anti-ai-patterns.md").write_text(_ANTI_AI_TEMPLATE, encoding="utf-8")
    return tmp_path  # return plugin_root


# ---------------------------------------------------------------------------
# write_book_rule
# ---------------------------------------------------------------------------


class TestWriteBookRule:
    def test_writes_phrase_to_claudemd(self, book_config, tmp_path):
        written, msg = write_book_rule(
            phrase="pulsed with energy",
            reason="overused metaphor",
            config=book_config,
            book_slug="my-book",
            source_context="report-issue based on Ch 22 review",
        )
        assert written is True
        content_root = Path(book_config["paths"]["content_root"])
        claudemd = content_root / "projects" / "my-book" / "CLAUDE.md"
        content = claudemd.read_text(encoding="utf-8")
        assert "pulsed with energy" in content
        assert "overused metaphor" in content
        assert "report-issue based on Ch 22 review" in content

    def test_idempotent_on_second_write(self, book_config):
        kwargs = dict(
            phrase="pulsed with energy",
            reason="overused metaphor",
            config=book_config,
            book_slug="my-book",
        )
        write_book_rule(**kwargs)
        written, _ = write_book_rule(**kwargs)
        assert written is False

    def test_phrase_formatted_as_backtick(self, book_config):
        write_book_rule("razor edge", "cliche", book_config, "my-book")
        content_root = Path(book_config["paths"]["content_root"])
        claudemd = content_root / "projects" / "my-book" / "CLAUDE.md"
        content = claudemd.read_text(encoding="utf-8")
        assert "`razor edge`" in content


# ---------------------------------------------------------------------------
# write_author_rule
# ---------------------------------------------------------------------------


class TestWriteAuthorRule:
    def test_writes_phrase_to_absolutely_forbidden(self, author_vocab):
        written, msg = write_author_rule(
            phrase="pulsed with energy",
            reason="overused metaphor",
            author_slug="test-author",
            source_context="report-issue based on My Book",
            storyforge_home=author_vocab,
        )
        assert written is True
        vocab_path = author_vocab / "authors" / "test-author" / "vocabulary.md"
        content = vocab_path.read_text(encoding="utf-8")
        assert "pulsed with energy" in content
        assert "report-issue based on My Book" in content

    def test_phrase_placed_in_absolutely_forbidden_section(self, author_vocab):
        write_author_rule("bad phrase", "test reason", "test-author", storyforge_home=author_vocab)
        vocab_path = author_vocab / "authors" / "test-author" / "vocabulary.md"
        content = vocab_path.read_text(encoding="utf-8")
        forbidden_idx = content.index("### Absolutely Forbidden")
        phrase_idx = content.index("bad phrase")
        assert phrase_idx > forbidden_idx

    def test_idempotent_on_duplicate(self, author_vocab):
        kwargs = dict(phrase="bad phrase", reason="test", author_slug="test-author", storyforge_home=author_vocab)
        write_author_rule(**kwargs)
        written, msg = write_author_rule(**kwargs)
        assert written is False
        assert "already present" in msg

    def test_creates_section_if_missing(self, tmp_path):
        vocab_dir = tmp_path / "authors" / "no-section-author"
        vocab_dir.mkdir(parents=True)
        vocab_path = vocab_dir / "vocabulary.md"
        vocab_path.write_text("# Author Vocabulary\n\n## Banned Words\n\n", encoding="utf-8")
        written, _ = write_author_rule("new phrase", "test", "no-section-author", storyforge_home=tmp_path)
        assert written is True
        content = vocab_path.read_text(encoding="utf-8")
        assert "### Absolutely Forbidden" in content
        assert "new phrase" in content

    def test_returns_false_if_vocab_missing(self, tmp_path):
        written, msg = write_author_rule("test", "reason", "nonexistent-author", storyforge_home=tmp_path)
        assert written is False
        assert "not found" in msg.lower()


# ---------------------------------------------------------------------------
# write_global_rule
# ---------------------------------------------------------------------------


class TestWriteGlobalRule:
    def test_writes_numbered_entry(self, anti_ai_file):
        written, msg = write_global_rule(
            phrase="pulsed with energy",
            reason="overused metaphor",
            plugin_root=anti_ai_file,
            source_context="report-issue",
        )
        assert written is True
        content = (anti_ai_file / "reference" / "craft" / "anti-ai-patterns.md").read_text(encoding="utf-8")
        assert "**pulsed with energy**" in content
        assert "overused metaphor" in content

    def test_entry_number_increments_from_last(self, anti_ai_file):
        write_global_rule("phrase one", "reason one", anti_ai_file)
        write_global_rule("phrase two", "reason two", anti_ai_file)
        content = (anti_ai_file / "reference" / "craft" / "anti-ai-patterns.md").read_text(encoding="utf-8")
        assert "3. **phrase one**" in content
        assert "4. **phrase two**" in content

    def test_idempotent_on_duplicate(self, anti_ai_file):
        write_global_rule("Delve", "classic AI tell", anti_ai_file)
        written, msg = write_global_rule("Delve", "classic AI tell", anti_ai_file)
        assert written is False
        assert "already present" in msg

    def test_entry_placed_before_why_section(self, anti_ai_file):
        write_global_rule("new phrase", "reason", anti_ai_file)
        content = (anti_ai_file / "reference" / "craft" / "anti-ai-patterns.md").read_text(encoding="utf-8")
        new_idx = content.index("**new phrase**")
        why_idx = content.index("### Why These Words Signal AI")
        assert new_idx < why_idx

    def test_returns_false_if_file_missing(self, tmp_path):
        written, msg = write_global_rule("phrase", "reason", tmp_path)
        assert written is False
        assert "not found" in msg.lower()


# ---------------------------------------------------------------------------
# promote_rule
# ---------------------------------------------------------------------------


class TestPromoteRule:
    def test_book_to_author_writes_and_removes(self, book_config, author_vocab):
        write_book_rule("old phrase", "reason", book_config, "my-book")
        success, msg = promote_rule(
            phrase="old phrase",
            reason="reason",
            from_scope=SCOPE_BOOK,
            to_scope=SCOPE_AUTHOR,
            config=book_config,
            book_slug="my-book",
            author_slug="test-author",
            storyforge_home=author_vocab,
            remove_from_source=True,
        )
        assert success is True
        # Phrase should be in author vocabulary.
        vocab_path = author_vocab / "authors" / "test-author" / "vocabulary.md"
        assert "old phrase" in vocab_path.read_text(encoding="utf-8")
        # Phrase should be removed from book CLAUDE.md.
        content_root = Path(book_config["paths"]["content_root"])
        claudemd = content_root / "projects" / "my-book" / "CLAUDE.md"
        assert "old phrase" not in claudemd.read_text(encoding="utf-8")

    def test_book_to_author_keep_source(self, book_config, author_vocab):
        write_book_rule("kept phrase", "reason", book_config, "my-book")
        promote_rule(
            phrase="kept phrase",
            reason="reason",
            from_scope=SCOPE_BOOK,
            to_scope=SCOPE_AUTHOR,
            config=book_config,
            book_slug="my-book",
            author_slug="test-author",
            storyforge_home=author_vocab,
            remove_from_source=False,
        )
        content_root = Path(book_config["paths"]["content_root"])
        claudemd = content_root / "projects" / "my-book" / "CLAUDE.md"
        assert "kept phrase" in claudemd.read_text(encoding="utf-8")

    def test_author_to_global(self, author_vocab, anti_ai_file):
        write_author_rule("author phrase", "reason", "test-author", storyforge_home=author_vocab)
        success, msg = promote_rule(
            phrase="author phrase",
            reason="reason",
            from_scope=SCOPE_AUTHOR,
            to_scope=SCOPE_GLOBAL,
            author_slug="test-author",
            plugin_root=anti_ai_file,
            storyforge_home=author_vocab,
        )
        assert success is True
        content = (anti_ai_file / "reference" / "craft" / "anti-ai-patterns.md").read_text(encoding="utf-8")
        assert "author phrase" in content

    def test_rejects_same_scope(self, book_config):
        success, msg = promote_rule(
            "phrase",
            "reason",
            SCOPE_BOOK,
            SCOPE_BOOK,
            config=book_config,
            book_slug="my-book",
        )
        assert success is False
        assert "higher" in msg.lower()

    def test_rejects_downgrade(self, anti_ai_file, author_vocab):
        success, msg = promote_rule(
            "phrase",
            "reason",
            SCOPE_GLOBAL,
            SCOPE_AUTHOR,
            author_slug="test-author",
            plugin_root=anti_ai_file,
            storyforge_home=author_vocab,
        )
        assert success is False
