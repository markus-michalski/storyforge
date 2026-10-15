"""Tests for the voice-dimension vocabulary — Epic #663 / Issue #666."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.voice_dimensions import (
    MEMOIR_ONLY_DIMENSIONS,
    VoiceDimensionError,
    allowed_dimensions,
    direction_kind,
    load_voice_dimensions,
    opposite_direction,
    validate_classification,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = REPO_ROOT / "reference" / "craft" / "voice-dimensions.md"


@pytest.fixture(scope="module")
def vocab() -> dict:
    return load_voice_dimensions(REPO_ROOT)


class TestDocument:
    def test_doc_exists_with_craft_frontmatter(self):
        text = DOC.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        head = text.split("---", 2)[1]
        assert "book_categories: [fiction, memoir]" in head
        assert "craft_topic:" in head
        assert "status:" in head

    def test_doc_describes_classification_procedure(self):
        text = DOC.read_text(encoding="utf-8")
        assert "## Classification Procedure" in text
        assert "classify once" in text.lower()


class TestVocabulary:
    def test_has_core_and_memoir_dimensions(self, vocab):
        assert {"sentence_rhythm", "dialog_tags", "simile_density", "other"} <= set(vocab)
        assert MEMOIR_ONLY_DIMENSIONS <= set(vocab)

    def test_every_dimension_is_complete(self, vocab):
        for slug, dim in vocab.items():
            assert dim["definition"].strip(), slug
            assert dim["directions"], slug
            assert len(dim["examples"]) >= 2, f"{slug}: needs two worked examples"
            assert set(dim["categories"]) <= {"fiction", "memoir"}, slug
            assert dim["categories"], slug

    def test_direction_kinds_are_prefer_or_avoid(self, vocab):
        for slug, dim in vocab.items():
            for name, spec in dim["directions"].items():
                assert spec["kind"] in {"prefer", "avoid"}, f"{slug}.{name}"

    def test_opposites_exist_and_are_symmetric(self, vocab):
        for slug, dim in vocab.items():
            for name, spec in dim["directions"].items():
                opp = spec.get("opposite")
                if opp is None:
                    continue
                assert opp in dim["directions"], f"{slug}.{name} -> {opp}"
                assert dim["directions"][opp].get("opposite") == name, f"{slug}.{name}"

    def test_slugs_are_machine_friendly(self, vocab):
        import re

        for slug, dim in vocab.items():
            assert re.fullmatch(r"[a-z][a-z0-9_]*", slug), slug
            for name in dim["directions"]:
                assert re.fullmatch(r"[a-z][a-z0-9_]*", name), f"{slug}.{name}"

    def test_memoir_only_dimensions_are_not_offered_for_fiction(self, vocab):
        for slug in MEMOIR_ONLY_DIMENSIONS:
            assert vocab[slug]["categories"] == ["memoir"]
        assert not MEMOIR_ONLY_DIMENSIONS & set(allowed_dimensions("fiction", REPO_ROOT))

    def test_fiction_dimensions_are_offered_for_memoir_unless_fiction_only(self, vocab):
        assert "sentence_rhythm" in allowed_dimensions("memoir", REPO_ROOT)


class TestValidation:
    def test_accepts_valid_pair(self):
        validate_classification("sentence_rhythm", "shorter", "fiction", REPO_ROOT)

    def test_rejects_unknown_dimension_with_actionable_message(self):
        with pytest.raises(VoiceDimensionError, match="sentence_rhythm"):
            validate_classification("sentence_length_ish", "shorter", "fiction", REPO_ROOT)

    def test_rejects_unknown_direction_listing_allowed(self):
        with pytest.raises(VoiceDimensionError, match="shorter"):
            validate_classification("sentence_rhythm", "sideways", "fiction", REPO_ROOT)

    def test_rejects_memoir_dimension_for_fiction(self):
        with pytest.raises(VoiceDimensionError, match="memoir"):
            validate_classification("tidy_lesson_ending", "less", "fiction", REPO_ROOT)

    def test_accepts_memoir_dimension_for_memoir(self):
        validate_classification("tidy_lesson_ending", "less", "memoir", REPO_ROOT)

    def test_is_case_and_whitespace_strict(self):
        with pytest.raises(VoiceDimensionError):
            validate_classification("Sentence_Rhythm", "shorter", "fiction", REPO_ROOT)

    def test_unknown_category_raises(self):
        with pytest.raises(VoiceDimensionError, match="book_category"):
            validate_classification("sentence_rhythm", "shorter", "poetry", REPO_ROOT)


class TestDirectionHelpers:
    def test_direction_kind(self):
        assert direction_kind("sentence_rhythm", "shorter", REPO_ROOT) == "prefer"

    def test_opposite_direction(self):
        assert opposite_direction("sentence_rhythm", "shorter", REPO_ROOT) == "longer"
        assert opposite_direction("sentence_rhythm", "longer", REPO_ROOT) == "shorter"

    def test_opposite_none_when_not_defined(self, vocab):
        for slug, dim in vocab.items():
            for name, spec in dim["directions"].items():
                if spec.get("opposite") is None:
                    assert opposite_direction(slug, name, REPO_ROOT) is None
                    return
        pytest.skip("every direction has an opposite")


class TestLoader:
    def test_missing_doc_raises_clear_error(self, tmp_path):
        with pytest.raises(VoiceDimensionError, match="voice-dimensions"):
            load_voice_dimensions(tmp_path)

    def test_doc_without_vocabulary_block_raises(self, tmp_path):
        d = tmp_path / "reference" / "craft"
        d.mkdir(parents=True)
        (d / "voice-dimensions.md").write_text("# nothing here\n", encoding="utf-8")
        with pytest.raises(VoiceDimensionError, match="vocabulary"):
            load_voice_dimensions(tmp_path)
