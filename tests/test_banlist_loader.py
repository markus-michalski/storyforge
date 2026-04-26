"""Tests for ``tools.banlist_loader``.

Covers the three loaders (author-vocab, global anti-AI tells,
author-slug-from-book) and the BannedPattern dataclass.
"""

from __future__ import annotations

from pathlib import Path

from tools.banlist_loader import (
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    author_slug_from_book,
    load_author_vocab,
    load_global_ai_tells,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# author_slug_from_book
# ---------------------------------------------------------------------------


def _make_book_with_author(tmp_path: Path, author_line: str | None) -> Path:
    book = tmp_path / "test-book"
    book.mkdir()
    body = "# Test Book\n\n## Book Facts\n\n"
    if author_line:
        body += f"{author_line}\n"
    body += "- **Genre:** test\n"
    (book / "CLAUDE.md").write_text(body, encoding="utf-8")
    return book


class TestAuthorSlugFromBook:
    def test_basic_author_line(self, tmp_path):
        book = _make_book_with_author(tmp_path, "- **Author:** Ethan Cole")
        assert author_slug_from_book(book) == "ethan-cole"

    def test_author_with_parenthetical(self, tmp_path):
        book = _make_book_with_author(
            tmp_path, "- **Author:** Ethan Cole (Eddings-humor with Twilight-stakes)"
        )
        assert author_slug_from_book(book) == "ethan-cole"

    def test_no_author_line(self, tmp_path):
        book = _make_book_with_author(tmp_path, None)
        assert author_slug_from_book(book) is None

    def test_no_claudemd(self, tmp_path):
        book = tmp_path / "empty-book"
        book.mkdir()
        assert author_slug_from_book(book) is None

    def test_multi_word_name(self, tmp_path):
        book = _make_book_with_author(tmp_path, "- **Author:** Ursula K. Le Guin")
        assert author_slug_from_book(book) == "ursula-k-le-guin"


# ---------------------------------------------------------------------------
# load_author_vocab
# ---------------------------------------------------------------------------


def _make_vocab(
    storyforge_home: Path, author_slug: str, body: str
) -> Path:
    """Write a vocabulary.md under a fake storyforge home."""
    vocab_dir = storyforge_home / "authors" / author_slug
    vocab_dir.mkdir(parents=True, exist_ok=True)
    vocab_path = vocab_dir / "vocabulary.md"
    vocab_path.write_text(body, encoding="utf-8")
    return vocab_path


class TestLoadAuthorVocab:
    def test_missing_author_returns_empty(self, tmp_path):
        patterns = load_author_vocab("nonexistent", storyforge_home=tmp_path)
        assert patterns == []

    def test_parses_absolutely_forbidden(self, tmp_path):
        body = (
            "# Vocabulary Profile\n\n"
            "## Banned Words — AI Tells\n\n"
            "### Absolutely Forbidden\n"
            "- delve\n"
            "- tapestry\n"
            "- vibrant\n"
        )
        _make_vocab(tmp_path, "alice", body)
        patterns = load_author_vocab("alice", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "tapestry" in labels
        assert "vibrant" in labels
        assert all(p.severity == SEVERITY_BLOCK for p in patterns)
        assert all("author-vocab" in p.source for p in patterns)

    def test_splits_aliases_on_slash(self, tmp_path):
        body = (
            "## Banned Words\n\n"
            "### Absolutely Forbidden\n"
            "- delve / delve into\n"
            "- embark / embark on\n"
        )
        _make_vocab(tmp_path, "bob", body)
        patterns = load_author_vocab("bob", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "delve into" in labels
        assert "embark" in labels
        assert "embark on" in labels

    def test_strips_parenthetical_clarifications(self, tmp_path):
        body = (
            "## Banned Words\n\n"
            "### Absolutely Forbidden\n"
            "- tapestry (metaphorical)\n"
            "- landscape (metaphorical)\n"
        )
        _make_vocab(tmp_path, "carol", body)
        patterns = load_author_vocab("carol", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "tapestry" in labels
        assert "landscape" in labels
        # Original parenthetical not present
        assert not any("metaphorical" in label for label in labels)

    def test_loads_all_four_forbidden_sections(self, tmp_path):
        body = (
            "## Banned\n\n"
            "### Absolutely Forbidden\n- delve\n\n"
            "### Forbidden Hedging Phrases\n- it's worth noting that\n\n"
            "### Forbidden Emotional Tells\n- her heart raced\n\n"
            "### Forbidden Structural Patterns\n- in essence\n"
        )
        _make_vocab(tmp_path, "dora", body)
        patterns = load_author_vocab("dora", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "it's worth noting that" in labels
        assert "her heart raced" in labels
        assert "in essence" in labels

    def test_dedupes_across_sections(self, tmp_path):
        body = (
            "## Banned\n\n"
            "### Absolutely Forbidden\n- delve\n\n"
            "### Forbidden Hedging Phrases\n- delve\n"
        )
        _make_vocab(tmp_path, "eve", body)
        patterns = load_author_vocab("eve", storyforge_home=tmp_path)
        delves = [p for p in patterns if p.label == "delve"]
        assert len(delves) == 1

    def test_skips_short_entries(self, tmp_path):
        body = (
            "## Banned\n\n"
            "### Absolutely Forbidden\n"
            "- a\n"
            "- delve\n"
        )
        _make_vocab(tmp_path, "frank", body)
        patterns = load_author_vocab("frank", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "a" not in labels

    def test_pattern_catches_inflections_for_single_word(self, tmp_path):
        body = "## Banned\n\n### Absolutely Forbidden\n- delve\n"
        _make_vocab(tmp_path, "gina", body)
        patterns = load_author_vocab("gina", storyforge_home=tmp_path)
        delve = next(p for p in patterns if p.label == "delve")
        # Catches inflections (delved, delves, delving)
        assert delve.pattern.search("she delved into the box") is not None
        assert delve.pattern.search("she delves into") is not None
        assert delve.pattern.search("delving deep") is not None
        # Bare word still matches
        assert delve.pattern.search("she went to delve into") is not None
        # Mid-word matches NOT triggered (leading word-boundary)
        assert delve.pattern.search("the redelve was misnamed") is None
        # Case-insensitive
        assert delve.pattern.search("DELVE!") is not None
        # Unrelated word does not match
        assert delve.pattern.search("the deliverer arrived") is None

    def test_multi_word_phrase_uses_full_boundary(self, tmp_path):
        body = "## Banned\n\n### Forbidden Hedging Phrases\n- it's worth noting that\n"
        _make_vocab(tmp_path, "henrietta", body)
        patterns = load_author_vocab("henrietta", storyforge_home=tmp_path)
        phrase = next(
            p for p in patterns if p.label == "it's worth noting that"
        )
        assert phrase.pattern.search(
            "Now it's worth noting that we tried."
        ) is not None
        # Same phrase mid-sentence still works
        assert phrase.pattern.search(
            "Look — it's worth noting that this fails."
        ) is not None

    def test_higher_heading_terminates_section(self, tmp_path):
        """A `##`-level heading after a `###` Forbidden block stops parsing."""
        body = (
            "## Banned Words\n\n"
            "### Absolutely Forbidden\n- delve\n\n"
            "## Preferred Vocabulary\n\n"
            "- said\n- went\n"
        )
        _make_vocab(tmp_path, "henry", body)
        patterns = load_author_vocab("henry", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        # 'said' / 'went' must NOT be banned — they live under Preferred Vocabulary.
        assert "said" not in labels
        assert "went" not in labels


# ---------------------------------------------------------------------------
# load_global_ai_tells
# ---------------------------------------------------------------------------


class TestLoadGlobalAITells:
    def test_loads_from_real_anti_ai_patterns_md(self):
        """Sanity check against the actual repo file. Should yield > 30
        tells (the curated list is much longer)."""
        patterns = load_global_ai_tells(PLUGIN_ROOT)
        assert len(patterns) >= 30
        labels = [p.label.lower() for p in patterns]
        # Spot-check a few high-confidence entries
        assert "delve" in labels
        assert "tapestry" in labels
        assert "vibrant" in labels
        assert all(p.severity == SEVERITY_WARN for p in patterns)
        assert all(p.source == "global anti-ai" for p in patterns)

    def test_missing_file_returns_empty(self, tmp_path):
        patterns = load_global_ai_tells(tmp_path)
        assert patterns == []

    def test_parses_synthetic_section(self, tmp_path):
        # Simulate a minimal anti-ai-patterns.md
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "anti-ai-patterns.md").write_text(
            "# Anti-AI Patterns\n\n"
            "## 1. Known AI Tells — Vocabulary\n\n"
            "### Heavily Flagged Words and Phrases (AI Tell Indicators)\n\n"
            "1. **Delve** / **Delve into** — One of the most notorious AI tells.\n"
            "2. **Tapestry** (metaphorical) — Almost never used by humans.\n"
            "3. **Vibrant** — Favored descriptor for colors.\n"
            "\n## 2. Other Section\n\n- something irrelevant\n",
            encoding="utf-8",
        )
        patterns = load_global_ai_tells(tmp_path)
        labels = [p.label for p in patterns]
        assert "Delve" in labels
        assert "Delve into" in labels
        assert "Tapestry" in labels
        assert "Vibrant" in labels
        # Section after `## 2.` must not be picked up.
        assert "something irrelevant" not in labels

    def test_explanation_truncated_into_reason(self, tmp_path):
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        long_expl = "Lorem ipsum " * 20
        (ref / "anti-ai-patterns.md").write_text(
            "### Heavily Flagged Words and Phrases (X)\n\n"
            f"1. **Delve** — {long_expl}\n",
            encoding="utf-8",
        )
        patterns = load_global_ai_tells(tmp_path)
        delve = next(p for p in patterns if p.label == "Delve")
        assert len(delve.reason) <= 120
