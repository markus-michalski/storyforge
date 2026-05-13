"""Tests for ``tools.banlist_loader.load_author_dont_rules`` (Issue #210).

The PostToolUse hook (``hooks/validate_chapter.py``) enforces author-level
banned shapes from the author profile. Recurring Tics are already wired in
via :func:`load_author_writing_discoveries`; this loader closes the gap for
``## Writing Discoveries / ### Don'ts`` so the elegant-abstraction register
patterns ship as hard-blocks at write-time too.

Patterns extracted:

- Backtick-wrapped regex/literals — block on first hit
- Italic-wrapped phrases when the bullet carries a ban cue
  (``Never``, ``Avoid``, etc.) — block on first hit

Quoted phrases are intentionally **not** picked up by the hook (#70's design:
backticks-only is the hard-block convention; the manuscript-checker uses a
looser parser). Italics are the exception because the Don'ts subsection
uses italic example phrases as the user-facing source of truth.
"""

from __future__ import annotations

from pathlib import Path

from tools.banlist_loader import (
    SEVERITY_BLOCK,
    load_author_dont_rules,
)


def _write_profile(storyforge_home: Path, slug: str, donts_body: str) -> None:
    profile_dir = storyforge_home / "authors" / slug
    profile_dir.mkdir(parents=True)
    (profile_dir / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n'
        "# Ethan Cole\n\n"
        "## Writing Discoveries\n\n"
        f"### Don'ts\n\n{donts_body}",
        encoding="utf-8",
    )


class TestLoadAuthorDontRules:
    def test_returns_empty_when_profile_missing(self, tmp_path):
        result = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        assert result == []

    def test_returns_empty_when_no_donts_section(self, tmp_path):
        profile_dir = tmp_path / "authors" / "ethan-cole"
        profile_dir.mkdir(parents=True)
        (profile_dir / "profile.md").write_text(
            "# Ethan Cole\n\n## Writing Discoveries\n\n"
            "### Recurring Tics\n\n- **\"thing\"** — concretize.\n",
            encoding="utf-8",
        )
        result = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        assert result == []

    def test_extracts_backtick_regex(self, tmp_path):
        _write_profile(
            tmp_path,
            "ethan-cole",
            "- **Never personify rooms** — `\\bthe (room|silence) "
            "(received|held)\\b`\n",
        )
        result = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        assert result
        assert all(p.severity == SEVERITY_BLOCK for p in result)
        labels = [p.label for p in result]
        assert any("room|silence" in lab for lab in labels)

    def test_extracts_italic_phrase_when_ban_cue_present(self, tmp_path):
        _write_profile(
            tmp_path,
            "ethan-cole",
            "- **Never use word-count meta-commentary** — *Two words.* / *One word.*\n",
        )
        result = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        assert result
        labels = [p.label for p in result]
        assert "Two words." in labels
        assert "One word." in labels

    def test_skips_italics_without_ban_cue(self, tmp_path):
        _write_profile(
            tmp_path,
            "ethan-cole",
            "- Style note: sometimes *italics* are just emphasis.\n",
        )
        result = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        # No ban cue — italics are narrative emphasis only.
        assert result == []

    def test_source_attribution_includes_donts(self, tmp_path):
        _write_profile(
            tmp_path,
            "ethan-cole",
            "- **Never use rooms** — *The room received it.*\n",
        )
        result = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        assert result
        assert any("don't" in p.source.lower() or "donts" in p.source.lower() for p in result)

    def test_compiled_pattern_is_case_insensitive(self, tmp_path):
        _write_profile(
            tmp_path,
            "ethan-cole",
            "- **Never use rooms** — *The room received it.*\n",
        )
        result = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        assert result
        pat = result[0].pattern
        assert pat.search("the room received it.")
        assert pat.search("THE ROOM RECEIVED IT.")

    def test_does_not_pick_up_bold_title_as_italic(self, tmp_path):
        """Double-asterisks (bold) must not be mistaken for italic patterns."""
        _write_profile(
            tmp_path,
            "ethan-cole",
            "- **Never use rooms as receivers** — *The room received it.*\n",
        )
        result = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in result]
        # The bold title is not a pattern; only the italic phrase is.
        assert "Never use rooms as receivers" not in labels
        assert "The room received it." in labels
