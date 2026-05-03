"""Tests for ``tools.banlist_loader``.

Covers the three loaders (author-vocab, global anti-AI tells,
author-slug-from-book) and the BannedPattern dataclass.
"""

from __future__ import annotations

from pathlib import Path

from tools.banlist_loader import (
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    _extract_phrases_from_bold_title,
    author_slug_from_book,
    load_author_vocab,
    load_author_writing_discoveries,
    load_global_ai_tells,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# _extract_phrases_from_bold_title — Issue #151 follow-up
# ---------------------------------------------------------------------------


class TestExtractPhrasesFromBoldTitle:
    """Bold-title bullets in `## Writing Discoveries` carry the scannable
    phrase inside double-quotes. The extractor must:

    - Pick all double-quoted phrases as the primary patterns
    - Fall back to the cleaned bold-title text when no quotes are present
    - Skip degenerate cases (empty title, title shorter than 2 chars)
    """

    def test_extracts_inner_double_quoted_phrase(self):
        title = '**Vague-noun "thing" als Fallback**'
        assert _extract_phrases_from_bold_title(title) == ["thing"]

    def test_extracts_multiple_inner_quotes(self):
        title = '**"count" als Tic / "for a count of X"**'
        assert _extract_phrases_from_bold_title(title) == ["count", "for a count of X"]

    def test_falls_back_to_bold_title_text_when_no_quotes(self):
        title = "**Opened his mouth. Closed it.**"
        assert _extract_phrases_from_bold_title(title) == ["Opened his mouth. Closed it."]

    def test_strips_outer_asterisks_and_whitespace(self):
        title = "  **the way als Vergleichs-Tic**  "
        assert _extract_phrases_from_bold_title(title) == ["the way als Vergleichs-Tic"]

    def test_handles_typographic_quotes(self):
        # German typographic quotes "..." should be picked up as well.
        title = '**Vague-noun „thing" als Fallback**'
        result = _extract_phrases_from_bold_title(title)
        assert "thing" in result

    def test_skips_too_short_quoted_content(self):
        title = '**"x" als Tic**'
        # Single-char quotes are noise — fall back to title text.
        result = _extract_phrases_from_bold_title(title)
        assert "x" not in result

    def test_returns_empty_for_no_bold(self):
        assert _extract_phrases_from_bold_title("not a bold title") == []
        assert _extract_phrases_from_bold_title("") == []


# ---------------------------------------------------------------------------
# load_author_writing_discoveries — Issue #151 follow-up
# ---------------------------------------------------------------------------


def _make_profile(storyforge_home: Path, author_slug: str, discoveries_body: str) -> Path:
    profile_dir = storyforge_home / "authors" / author_slug
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / "profile.md"
    profile_path.write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n'
        "# Ethan Cole\n\n"
        "## Writing Discoveries\n\n"
        f"{discoveries_body}\n",
        encoding="utf-8",
    )
    return profile_path


class TestLoadAuthorWritingDiscoveries:
    def test_returns_empty_when_profile_missing(self, tmp_path):
        result = load_author_writing_discoveries("missing-author", storyforge_home=tmp_path)
        assert result == []

    def test_returns_empty_when_no_discoveries_section(self, tmp_path):
        profile_dir = tmp_path / "authors" / "x"
        profile_dir.mkdir(parents=True)
        (profile_dir / "profile.md").write_text(
            '---\nname: x\n---\n\n# x\n\n## Writing Style\n\nSparse.\n',
            encoding="utf-8",
        )
        result = load_author_writing_discoveries("x", storyforge_home=tmp_path)
        assert result == []

    def test_extracts_recurring_tic_quoted_phrases(self, tmp_path):
        body = (
            '### Recurring Tics\n\n'
            '- **Vague-noun "thing" als Fallback** — concretize on sight. '
            '_(emerged from blood-and-binary-firelight, 2026-05)_\n'
        )
        _make_profile(tmp_path, "ethan-cole", body)

        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "thing" in labels
        # Source string should make the origin obvious.
        assert all(p.source.startswith("author profile") for p in patterns)
        # Severity is block — discoveries are author-voice intent.
        assert all(p.severity == SEVERITY_BLOCK for p in patterns)

    def test_falls_back_to_bold_title_when_no_inner_quote(self, tmp_path):
        body = (
            '### Recurring Tics\n\n'
            '- **Opened his mouth. Closed it.** — vary or skip. '
            '_(emerged from firelight, 2026-05)_\n'
        )
        _make_profile(tmp_path, "ethan-cole", body)
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "Opened his mouth. Closed it." in labels

    def test_skips_style_principles_and_donts(self, tmp_path):
        """Only `recurring_tics` are scannable patterns. Style principles and
        don'ts are prose-level rules, not phrase bans."""
        body = (
            '### Recurring Tics\n\n'
            '- **"thing" als Fallback** — fix.\n\n'
            '### Style Principles\n\n'
            '- **POV-Wissens-Integrität** — kein POV-Charakter macht Fachbehauptungen.\n\n'
            "### Don'ts (beyond banned phrases)\n\n"
            '- **Avoid weather openings** — never start chapters with weather.\n'
        )
        _make_profile(tmp_path, "ethan-cole", body)

        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "thing" in labels
        assert "POV-Wissens-Integrität" not in labels
        assert "Avoid weather openings" not in labels

    def test_dedups_within_section(self, tmp_path):
        body = (
            '### Recurring Tics\n\n'
            '- **"thing" als Fallback** — fix.\n'
            '- **"thing" als zweiter Tic** — fix again.\n'
        )
        _make_profile(tmp_path, "ethan-cole", body)
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert labels.count("thing") == 1

    def test_preserves_origin_in_source_string(self, tmp_path):
        body = (
            '### Recurring Tics\n\n'
            '- **"thing"** — fix. _(emerged from firelight, 2026-05)_\n'
        )
        _make_profile(tmp_path, "ethan-cole", body)
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        # Source should mention the discovery section so the brief can show
        # users WHERE the rule came from.
        assert "Writing Discoveries" in patterns[0].source


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
        book = _make_book_with_author(tmp_path, "- **Author:** Ethan Cole (Eddings-humor with Twilight-stakes)")
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


def _make_vocab(storyforge_home: Path, author_slug: str, body: str) -> Path:
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
        body = "## Banned Words\n\n### Absolutely Forbidden\n- delve / delve into\n- embark / embark on\n"
        _make_vocab(tmp_path, "bob", body)
        patterns = load_author_vocab("bob", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "delve into" in labels
        assert "embark" in labels
        assert "embark on" in labels

    def test_strips_parenthetical_clarifications(self, tmp_path):
        body = "## Banned Words\n\n### Absolutely Forbidden\n- tapestry (metaphorical)\n- landscape (metaphorical)\n"
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
        body = "## Banned\n\n### Absolutely Forbidden\n- delve\n\n### Forbidden Hedging Phrases\n- delve\n"
        _make_vocab(tmp_path, "eve", body)
        patterns = load_author_vocab("eve", storyforge_home=tmp_path)
        delves = [p for p in patterns if p.label == "delve"]
        assert len(delves) == 1

    def test_skips_short_entries(self, tmp_path):
        body = "## Banned\n\n### Absolutely Forbidden\n- a\n- delve\n"
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
        phrase = next(p for p in patterns if p.label == "it's worth noting that")
        assert phrase.pattern.search("Now it's worth noting that we tried.") is not None
        # Same phrase mid-sentence still works
        assert phrase.pattern.search("Look — it's worth noting that this fails.") is not None

    def test_higher_heading_terminates_section(self, tmp_path):
        """A `##`-level heading after a `###` Forbidden block stops parsing."""
        body = "## Banned Words\n\n### Absolutely Forbidden\n- delve\n\n## Preferred Vocabulary\n\n- said\n- went\n"
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
            f"### Heavily Flagged Words and Phrases (X)\n\n1. **Delve** — {long_expl}\n",
            encoding="utf-8",
        )
        patterns = load_global_ai_tells(tmp_path)
        delve = next(p for p in patterns if p.label == "Delve")
        assert len(delve.reason) <= 120
