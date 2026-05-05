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

        author_findings = [
            f for f in result.findings if f.category == "author_vocab_violation"
        ]
        assert author_findings, "expected at least one author_vocab_violation"
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
