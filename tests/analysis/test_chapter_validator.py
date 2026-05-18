"""Tests for tools.analysis.chapter_validator (Issue #119).

The hook tests in ``tests/test_hooks.py`` exercise the underlying
scanners through the hook's re-exports; this file covers the new
``validate_chapter_path`` API and ``ValidationResult`` envelope, and the
gate translation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.analysis.chapter_validator import (
    DEFAULT_MODE,
    Finding,
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    ValidationResult,
    resolve_mode,
    validate_chapter,
    validate_chapter_path,
)


def _write_book(tmp_path: Path, *, frontmatter_mode: str | None = None) -> Path:
    """Build a minimal book with a chapter directory ready for the validator."""
    book = tmp_path / "demo-book"
    (book / "chapters" / "01-opening").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "world").mkdir()

    fm = ""
    if frontmatter_mode is not None:
        fm = f"---\nlinter_mode: {frontmatter_mode}\n---\n\n"
    (book / "README.md").write_text(
        "---\nslug: demo-book\nbook_category: fiction\n---\n\n# Demo Book\n",
        encoding="utf-8",
    )
    (book / "CLAUDE.md").write_text(f"{fm}# Book CLAUDE.md\n", encoding="utf-8")
    return book


def _write_draft(book: Path, text: str, chapter_slug: str = "01-opening") -> Path:
    chapter = book / "chapters" / chapter_slug
    chapter.mkdir(parents=True, exist_ok=True)
    draft = chapter / "draft.md"
    draft.write_text(text, encoding="utf-8")
    (chapter / "README.md").write_text("# Chapter 1\n\n## Chapter Timeline\n\n", encoding="utf-8")
    return draft


class TestValidationResultEnvelope:
    def test_clean_chapter_returns_pass_gate(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        prose = " ".join(
            [
                "The hero walked through a quiet field with no fanfare at all.",
                "Birds fell silent above the broken road as he passed by.",
                "Every step landed with deliberate weight on dry earth.",
                "He thought about the choice ahead in plain words.",
                "Morning would come no matter what he chose.",
                "The wind shifted; rain seemed possible by afternoon.",
            ]
        )
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))
        assert isinstance(result, ValidationResult)
        gate = result.to_gate()
        assert gate.status == "PASS"
        assert gate.metadata["mode"] == DEFAULT_MODE
        assert gate.metadata["blocking_count"] == 0

    def test_blocking_finding_in_strict_fails(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        # Meta-narrative trigger + enough words.
        prose = "The flame is a callback to last winter, but he never lit it himself.\n" + (
            "The river ran cold past the camp. " * 30
        )
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))
        assert result.mode == "strict"
        assert result.blocking, "expected at least one blocking finding"
        assert result.will_block is True
        gate = result.to_gate()
        assert gate.status == "FAIL"
        assert any(f.severity == "FAIL" for f in gate.findings)

    def test_warn_mode_demotes_blocking_to_warn(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, frontmatter_mode="warn")
        prose = "The flame is a callback to last winter, but he never lit it himself.\n" + (
            "The river ran cold past the camp. " * 30
        )
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))
        assert result.mode == "warn"
        assert result.blocking
        assert result.will_block is False
        gate = result.to_gate()
        assert gate.status == "WARN"

    def test_too_short_returns_pass(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        draft = _write_draft(book, "Not enough words.")
        result = validate_chapter_path(str(draft))
        assert result.findings == []
        assert result.to_gate().status == "PASS"

    def test_render_block_report_lists_blocking(self, tmp_path: Path) -> None:
        result = ValidationResult(
            file_path="/tmp/chapters/01/draft.md",
            mode="strict",
            findings=[
                Finding(severity=SEVERITY_BLOCK, category="meta_narrative", message="callback found", line=12),
                Finding(severity=SEVERITY_WARN, category="ai_tell", message="word found", line=4),
            ],
        )
        report = result.render_block_report()
        assert "StoryForge linter blocked this write" in report
        assert "[BLOCK] draft.md line 12: callback found" in report
        assert "Plus 1 non-blocking warning" in report

    def test_render_diagnostics_caps(self, tmp_path: Path) -> None:
        result = ValidationResult(
            file_path="/tmp/chapters/01/draft.md",
            mode="warn",
            findings=[
                Finding(severity=SEVERITY_WARN, category="ai_tell", message=f"hit {i}", line=i) for i in range(15)
            ],
        )
        diag = result.render_diagnostics(cap=5)
        assert len(diag) == 5

    def test_to_json_dict_round_trips(self, tmp_path: Path) -> None:
        result = ValidationResult(
            file_path=str(tmp_path / "draft.md"),
            mode="strict",
            findings=[
                Finding(severity=SEVERITY_BLOCK, category="meta_narrative", message="callback found", line=3),
            ],
        )
        payload = json.dumps(result.to_json_dict())
        restored = json.loads(payload)
        assert restored["mode"] == "strict"
        assert restored["blocking_count"] == 1
        assert restored["gate"]["status"] == "FAIL"
        assert restored["gate"]["findings"][0]["code"] == "META_NARRATIVE"


class TestResolveMode:
    def test_default_strict(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        draft = _write_draft(book, "Some prose " * 20)
        assert resolve_mode(draft) == "strict"

    def test_warn_via_frontmatter(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, frontmatter_mode="warn")
        draft = _write_draft(book, "Some prose " * 20)
        assert resolve_mode(draft) == "warn"

    def test_invalid_mode_falls_back(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        # Invalid frontmatter value.
        (book / "CLAUDE.md").write_text(
            "---\nlinter_mode: nonsense\n---\n\n# Book CLAUDE.md\n",
            encoding="utf-8",
        )
        draft = _write_draft(book, "Some prose " * 20)
        assert resolve_mode(draft) == "strict"


class TestBackwardCompat:
    """Confirm the legacy ``validate_chapter`` entry point still works."""

    def test_returns_list_of_findings(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path)
        draft = _write_draft(book, "The callback arrived. " * 30)
        findings = validate_chapter(str(draft))
        assert isinstance(findings, list)
        assert all(isinstance(f, Finding) for f in findings)

    def test_returns_empty_for_non_chapter_path(self) -> None:
        assert validate_chapter("/does/not/exist.md") == []
        assert validate_chapter("/some/notes.md") == []


# ---------------------------------------------------------------------------
# Author banlist hook coverage — Issue #172
# ---------------------------------------------------------------------------


@pytest.fixture
def patch_storyforge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``Path.home()/.storyforge`` to a fake home rooted in tmp_path.

    Returns the resolved storyforge_home path so test helpers can write
    fixture profile files into the right place. Mirrors the fixture used
    by ``test_writing_discoveries_scanner.py``.
    """
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    return fake_home / ".storyforge"


def _write_book_with_author(tmp_path: Path, *, author_slug: str = "ethan-cole") -> Path:
    """Build a book layout that exposes the author slug to ``author_slug_from_book``."""
    book = tmp_path / "demo-book"
    (book / "chapters" / "01-opening").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        f'---\nslug: demo-book\nauthor: "{author_slug}"\nbook_category: fiction\n---\n\n'
        "# Demo Book\n",
        encoding="utf-8",
    )
    (book / "CLAUDE.md").write_text(
        "# Demo Book\n\n## Book Facts\n\n- **Author:** Ethan Cole\n",
        encoding="utf-8",
    )
    return book


def _write_author_profile_with_discoveries(
    home: Path, slug: str, discoveries_body: str
) -> None:
    """Create ``~/.storyforge/authors/{slug}/profile.md`` with a ## Writing
    Discoveries section."""
    profile_dir = home / "authors" / slug
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n'
        "# Ethan Cole\n\n"
        "## Writing Discoveries\n\n"
        f"{discoveries_body}",
        encoding="utf-8",
    )


def _write_author_vocabulary(home: Path, slug: str, body: str) -> None:
    """Create ``~/.storyforge/authors/{slug}/vocabulary.md`` for the vocab path."""
    profile_dir = home / "authors" / slug
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "vocabulary.md").write_text(body, encoding="utf-8")


class TestAuthorBanlistEnforcesWritingDiscoveries:
    """Issue #172: phrases promoted to ``## Writing Discoveries`` must trigger
    the strict-mode hard-block at draft save time, just like phrases in
    ``vocabulary.md`` already do."""

    def test_writing_discovery_phrase_blocks_in_strict_mode(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **Vague-noun "thing" als Fallback** — concretize on sight.\n'
            ),
        )
        # Draft with the banned phrase + enough words for the variance scanner
        # to leave us alone.
        prose = "He was doing a thing with his hand again. " * 30
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))

        # Issue #215: Recurring Tic hits are emitted under their own category,
        # matching the manuscript-checker vocabulary.
        author_findings = [
            f for f in result.findings if f.category == "writing_discovery_violation"
        ]
        assert author_findings, "expected at least one writing_discovery_violation"
        assert any(
            "Writing Discoveries" in f.message for f in author_findings
        ), "expected the source-tag for Writing Discoveries in the message"
        assert all(f.severity == SEVERITY_BLOCK for f in author_findings)
        assert result.will_block

    def test_writing_discovery_dedups_with_vocabulary(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """Same phrase in vocabulary.md and profile.md ``## Writing Discoveries``
        must yield exactly ONE finding (vocabulary wins on dedup)."""
        book = _write_book_with_author(tmp_path)
        # Vocabulary.md banlist ('thing' in the AI-tells subsection).
        _write_author_vocabulary(
            patch_storyforge_home,
            "ethan-cole",
            (
                "## Banned Words\n\n"
                "### Forbidden Hedging Phrases\n\n"
                "- thing\n"
            ),
        )
        # Same phrase also promoted as a Writing Discoveries tic.
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **Vague-noun "thing" als Fallback** — concretize on sight.\n'
            ),
        )
        prose = "He was doing a thing again, deliberate-feeling. " * 30
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))

        author_findings = [
            f for f in result.findings if f.category == "author_vocab_violation"
        ]
        # Exactly one entry — dedup kicks in. Vocabulary wins (canonical store).
        assert len(author_findings) == 1
        assert "vocab" in author_findings[0].message.lower()

    def test_vocabulary_only_path_unchanged(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """Books whose author has no Writing Discoveries section keep blocking
        on vocabulary.md exactly as before."""
        book = _write_book_with_author(tmp_path)
        _write_author_vocabulary(
            patch_storyforge_home,
            "ethan-cole",
            (
                "## Banned Words\n\n"
                "### Absolutely Forbidden\n\n"
                "- delve\n"
            ),
        )
        prose = "He had to delve into the question one more time today. " * 30
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))

        author_findings = [
            f for f in result.findings if f.category == "author_vocab_violation"
        ]
        assert author_findings
        assert all(f.severity == SEVERITY_BLOCK for f in author_findings)
        assert result.will_block


class TestAuthorBanlistEnforcesDonts:
    """Issue #210: ``### Don'ts`` in the author profile must trigger the
    strict-mode hard-block at draft save time, alongside vocabulary.md and
    ``### Recurring Tics``."""

    def test_dont_italic_phrase_blocks_in_strict_mode(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                "### Don'ts\n\n"
                "- **Never personify rooms as receivers** — *The room received it.*\n"
            ),
        )
        # Draft with the banned shape + enough words to clear the variance gate.
        prose = "The room received it without complaint that night. " * 30
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))

        # Issue #215: Don't hits are emitted under author_rule_violation,
        # matching the manuscript-checker vocabulary.
        author_findings = [
            f for f in result.findings if f.category == "author_rule_violation"
        ]
        assert author_findings, "expected at least one Don't violation"
        assert any(
            "don't" in f.message.lower() or "donts" in f.message.lower()
            for f in author_findings
        ), "expected the Don'ts source tag in the message"
        assert all(f.severity == SEVERITY_BLOCK for f in author_findings)
        assert result.will_block

    def test_dont_backtick_regex_blocks_in_strict_mode(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                "### Don'ts\n\n"
                "- **Never personify rooms** — `\\bthe (room|silence) "
                "(received|held)\\b`\n"
            ),
        )
        prose = "The silence held the verdict in place for far too long. " * 30
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))

        author_findings = [
            f for f in result.findings if f.category == "author_rule_violation"
        ]
        assert author_findings
        assert all(f.severity == SEVERITY_BLOCK for f in author_findings)
        assert result.will_block

    def test_dont_without_violation_does_not_block(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                "### Don'ts\n\n"
                "- **Never use rooms** — *The room received it.*\n"
            ),
        )
        prose = "Clean prose with no banned shapes at all whatsoever. " * 30
        draft = _write_draft(book, prose)

        result = validate_chapter_path(str(draft))

        # No author findings, no block.
        dont_findings = [
            f for f in result.findings
            if f.category == "author_rule_violation"
            and ("don't" in f.message.lower() or "donts" in f.message.lower())
        ]
        assert not dont_findings


# ---------------------------------------------------------------------------
# Issue #215: hook category split — each loader source gets its own category
# ---------------------------------------------------------------------------


class TestAuthorBanlistCategorySplit:
    """The hook scanner must emit three distinct categories — matching the
    manuscript-checker's vocabulary — so users can grep / filter hook output
    consistently across both layers.
    """

    def test_vocabulary_hit_emits_author_vocab_violation(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        book = _write_book_with_author(tmp_path)
        _write_author_vocabulary(
            patch_storyforge_home,
            "ethan-cole",
            (
                "## Banned Words\n\n"
                "### Absolutely Forbidden\n\n"
                "- delve\n"
            ),
        )
        prose = "He had to delve into the question one more time today. " * 30
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        categories = {f.category for f in result.findings}
        assert "author_vocab_violation" in categories
        # Pure-vocab path: no Recurring-Tic or Don't categories emitted.
        assert "writing_discovery_violation" not in categories
        assert "author_rule_violation" not in categories

    def test_recurring_tic_hit_emits_writing_discovery_violation(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **Vague-noun "thing" als Fallback** — concretize.\n'
            ),
        )
        prose = "He was doing a thing again, definitely a thing. " * 30
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        categories = [f.category for f in result.findings]
        assert "writing_discovery_violation" in categories
        # Pure-tic path: no vocab or Don't categories.
        assert "author_vocab_violation" not in categories
        assert "author_rule_violation" not in categories

    def test_dont_hit_emits_author_rule_violation(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                "### Don'ts\n\n"
                "- **Never use rooms** — *The room received it.*\n"
            ),
        )
        prose = "The room received it without complaint last night. " * 30
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        categories = [f.category for f in result.findings]
        assert "author_rule_violation" in categories
        assert "author_vocab_violation" not in categories
        assert "writing_discovery_violation" not in categories

    def test_three_sources_yield_three_distinct_categories(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """All three sources present + distinct phrases in the draft —
        the hook emits one finding per source under its dedicated category."""
        book = _write_book_with_author(tmp_path)
        _write_author_vocabulary(
            patch_storyforge_home,
            "ethan-cole",
            (
                "## Banned Words\n\n"
                "### Absolutely Forbidden\n\n"
                "- delve\n"
            ),
        )
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **Vague-noun "thing" als Fallback** — concretize.\n\n'
                "### Don'ts\n\n"
                "- **Never use rooms** — *The room received it.*\n"
            ),
        )
        prose = (
            "He had to delve into the question. Then a thing happened. "
            "The room received it without complaint. " * 30
        )
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        categories = {f.category for f in result.findings}
        assert "author_vocab_violation" in categories
        assert "writing_discovery_violation" in categories
        assert "author_rule_violation" in categories

    def test_dedup_preserves_winning_source_category(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """The dedup precedence (vocabulary > tics > don'ts) is unchanged.
        When the same phrase appears in multiple sources, only the winning
        source's category surfaces — and the winner is vocabulary.
        """
        book = _write_book_with_author(tmp_path)
        _write_author_vocabulary(
            patch_storyforge_home,
            "ethan-cole",
            (
                "## Banned Words\n\n"
                "### Forbidden Hedging Phrases\n\n"
                "- thing\n"
            ),
        )
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **Vague-noun "thing" als Fallback** — concretize.\n'
            ),
        )
        prose = "He was doing a thing again, deliberate-feeling. " * 30
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        thing_findings = [
            f for f in result.findings
            if "thing" in f.message.lower()
            and f.category in {
                "author_vocab_violation",
                "writing_discovery_violation",
                "author_rule_violation",
            }
        ]
        assert len(thing_findings) == 1
        assert thing_findings[0].category == "author_vocab_violation"

    def test_warn_severity_tic_does_not_block(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """A tic tagged [warn] produces a WARN finding but never blocks the write."""
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                "### Recurring Tics\n\n"
                "- **Vague-plural things** — "
                "`\\b(did|does|doing)\\s+things\\b` — [warn] advisory.\n"
            ),
        )
        prose = "He did things he normally would not do. " * 30
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        tic_findings = [
            f for f in result.findings if f.category == "writing_discovery_violation"
        ]
        assert tic_findings, "expected a writing_discovery_violation finding"
        assert all(f.severity == SEVERITY_WARN for f in tic_findings)
        assert not result.will_block

    def test_chapter_limit_allows_hits_under_cap(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """A tic with 'Max 2 per chapter' does not fire when hits <= cap."""
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **"the way" Vergleichs-Tic** — Max 2 per chapter.\n'
            ),
        )
        # Use ~3 000 words so _scaled_scene_limit does not reduce cap below 2.
        filler = "This sentence is unrelated filler content for test validation purposes. " * 200
        prose = (
            "He moved the way a cat moves. She spoke the way people speak at funerals. "
            + filler
        )
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        tic_findings = [
            f for f in result.findings if f.category == "writing_discovery_violation"
        ]
        assert not tic_findings, f"unexpected finding with 2 hits at cap 2: {tic_findings}"

    def test_chapter_limit_blocks_hits_over_cap(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """A tic with 'Max 2 per chapter' fires when hits exceed the cap."""
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **"the way" Vergleichs-Tic** — Max 2 per chapter.\n'
            ),
        )
        filler = "This sentence is unrelated filler content for test validation purposes. " * 200
        prose = (
            "He moved the way a cat moves. She spoke the way people speak. "
            "He laughed the way tired men laugh. "
            + filler
        )
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        tic_findings = [
            f for f in result.findings if f.category == "writing_discovery_violation"
        ]
        assert tic_findings, "expected a writing_discovery_violation finding at 3 hits over cap 2"
        assert "3" in tic_findings[0].message

    def test_german_limit_syntax_parsed(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """German 'Max. 2–3 pro Kapitel' phrasing is parsed as chapter_limit=3."""
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **"count" Zeitmarker-Tic** — Max. 2–3 pro Kapitel.\n'
            ),
        )
        filler = "This sentence is unrelated filler content for test validation purposes. " * 200
        # 3 hits of bare "count" at cap 3 — must pass.
        # Avoid "counted" which also matches \bcount\w*.
        prose = (
            "For a count of three he held still. For a count of two she waited. "
            "For a count of five they breathed. "
            + filler
        )
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        tic_findings = [
            f for f in result.findings if f.category == "writing_discovery_violation"
        ]
        assert not tic_findings, f"3 hits at cap 3 should not block: {tic_findings}"

    def test_einmal_limit_syntax_parsed(
        self, tmp_path: Path, patch_storyforge_home: Path
    ) -> None:
        """German 'Max einmal pro Kapitel' parses as chapter_limit=1."""
        book = _write_book_with_author(tmp_path)
        _write_author_profile_with_discoveries(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **"the way" Tic** — Max einmal pro Kapitel.\n'
            ),
        )
        filler = "This sentence is unrelated filler content for test validation purposes. " * 200
        # 2 hits — exceeds cap of 1 even at full word count.
        prose = (
            "He moved the way a ghost moves. She smiled the way old friends smile. "
            + filler
        )
        draft = _write_draft(book, prose)
        result = validate_chapter_path(str(draft))

        tic_findings = [
            f for f in result.findings if f.category == "writing_discovery_violation"
        ]
        assert tic_findings, "2 hits should exceed cap of 1"
        assert "2" in tic_findings[0].message
