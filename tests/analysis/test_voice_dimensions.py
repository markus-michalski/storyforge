"""Tests for the voice-dimension vocabulary — Epic #663 / Issue #666."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.voice_dimensions import (
    VoiceDimensionError,
    allowed_dimensions,
    direction_kind,
    load_voice_dimensions,
    memoir_only_dimensions,
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
        assert {"looking_back_hinge", "therapeutic_reframe"} <= set(memoir_only_dimensions(REPO_ROOT))
        assert {"ai_vocabulary", "repetition"} <= set(vocab)

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
        only = memoir_only_dimensions(REPO_ROOT)
        assert only
        for slug in only:
            assert vocab[slug]["categories"] == ["memoir"]
        assert not set(only) & set(allowed_dimensions("fiction", REPO_ROOT))

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
            validate_classification("looking_back_hinge", "less", "fiction", REPO_ROOT)

    def test_accepts_memoir_dimension_for_memoir(self):
        validate_classification("looking_back_hinge", "less", "memoir", REPO_ROOT)

    def test_fiction_counterparts_of_memoir_tells_are_available(self):
        for dim in ("hedging", "tidy_lesson_ending", "explanation_after_image"):
            validate_classification(dim, "less", "fiction", REPO_ROOT)

    @pytest.mark.parametrize("dimension", ["Sentence_Rhythm", " sentence_rhythm", "sentence_rhythm "])
    def test_is_case_and_whitespace_strict(self, dimension):
        with pytest.raises(VoiceDimensionError):
            validate_classification(dimension, "shorter", "fiction", REPO_ROOT)

    @pytest.mark.parametrize("bad", [None, 1, ["sentence_rhythm"], {"a": 1}])
    def test_non_string_inputs_raise_voice_dimension_error(self, bad):
        with pytest.raises(VoiceDimensionError):
            validate_classification(bad, "shorter", "fiction", REPO_ROOT)
        with pytest.raises(VoiceDimensionError):
            validate_classification("sentence_rhythm", bad, "fiction", REPO_ROOT)
        with pytest.raises(VoiceDimensionError):
            validate_classification("sentence_rhythm", "shorter", bad, REPO_ROOT)

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
        checked = 0
        for slug, dim in vocab.items():
            for name, spec in dim["directions"].items():
                if spec.get("opposite") is None:
                    assert opposite_direction(slug, name, REPO_ROOT) is None
                    checked += 1
        assert checked > 0

    def test_unknown_keys_raise_voice_dimension_error(self):
        with pytest.raises(VoiceDimensionError, match="nope"):
            direction_kind("nope", "x", REPO_ROOT)
        with pytest.raises(VoiceDimensionError, match="sideways"):
            opposite_direction("sentence_rhythm", "sideways", REPO_ROOT)


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


def _write_doc(root: Path, yaml_body: str, *, newline: str = "\n", before: str = "") -> Path:
    d = root / "reference" / "craft"
    d.mkdir(parents=True, exist_ok=True)
    text = f"# Doc\n{before}\n## Vocabulary\n\n```yaml\n{yaml_body}```\n"
    path = d / "voice-dimensions.md"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return path


_VALID = (
    "foo:\n"
    "  definition: A thing.\n"
    "  categories: [fiction]\n"
    "  directions:\n"
    "    up: {kind: prefer, opposite: down}\n"
    "    down: {kind: prefer, opposite: up}\n"
    "  examples: [a, b]\n"
)


class TestMalformedVocabulary:
    def test_valid_minimal_doc_loads(self, tmp_path):
        _write_doc(tmp_path, _VALID)
        assert list(load_voice_dimensions(tmp_path)) == ["foo"]

    @pytest.mark.parametrize("body,match", [
        ("foo: bar\n", "foo"),
        ("foo:\n  definition: x\n  directions: {a: {kind: prefer}}\n  examples: [a, b]\n", "categories"),
        ("foo:\n  definition: x\n  categories: fiction\n  directions: {a: {kind: prefer}}\n  examples: [a, b]\n", "categories"),
        ("foo:\n  definition: x\n  categories: [poetry]\n  directions: {a: {kind: prefer}}\n  examples: [a, b]\n", "categories"),
        ("foo:\n  definition: x\n  categories: [fiction]\n  directions: [a]\n  examples: [a, b]\n", "directions"),
        ("foo:\n  definition: x\n  categories: [fiction]\n  directions: {a: {kind: sideways}}\n  examples: [a, b]\n", "kind"),
        ("foo:\n  definition: x\n  categories: [fiction]\n  directions: {no: {kind: prefer}}\n  examples: [a, b]\n", "directions"),
        ("foo:\n  definition: x\n  categories: [fiction]\n  directions: {a: {kind: prefer, opposite: ghost}}\n  examples: [a, b]\n", "opposite"),
        ("foo:\n  definition: x\n  categories: [fiction]\n  directions: {a: {kind: prefer, opposite: b}, b: {kind: prefer}}\n  examples: [a, b]\n", "opposite"),
        ("foo:\n  definition: ''\n  categories: [fiction]\n  directions: {a: {kind: prefer}}\n  examples: [a, b]\n", "definition"),
        ("foo:\n  definition: x\n  categories: [fiction]\n  directions: {a: {kind: prefer}}\n  examples: [a]\n", "examples"),
    ])
    def test_schema_violations_raise_voice_dimension_error(self, tmp_path, body, match):
        _write_doc(tmp_path, body)
        with pytest.raises(VoiceDimensionError, match=match):
            load_voice_dimensions(tmp_path)

    def test_crlf_document_loads(self, tmp_path):
        _write_doc(tmp_path, _VALID, newline="\r\n")
        assert "foo" in load_voice_dimensions(tmp_path)

    def test_returned_vocabulary_cannot_corrupt_the_cache(self, tmp_path):
        _write_doc(tmp_path, _VALID)
        first = load_voice_dimensions(tmp_path)
        first["foo"]["categories"].append("poetry")
        first["bar"] = {}
        again = load_voice_dimensions(tmp_path)
        assert again["foo"]["categories"] == ["fiction"]
        assert "bar" not in again

    def test_same_mtime_rewrite_is_not_served_stale(self, tmp_path):
        import os

        path = _write_doc(tmp_path, _VALID)
        stamp = path.stat().st_mtime_ns
        load_voice_dimensions(tmp_path)
        _write_doc(tmp_path, _VALID.replace("foo", "bazz"))
        os.utime(path, ns=(stamp, stamp))
        assert "bazz" in load_voice_dimensions(tmp_path)

    def test_yaml_fence_in_later_section_is_not_picked_up(self, tmp_path):
        d = tmp_path / "reference" / "craft"
        d.mkdir(parents=True)
        (d / "voice-dimensions.md").write_text(
            "## Vocabulary\n\nnothing yet\n\n## Appendix\n\n```yaml\n" + _VALID + "```\n",
            encoding="utf-8",
        )
        with pytest.raises(VoiceDimensionError, match="vocabulary"):
            load_voice_dimensions(tmp_path)


class TestDocConsistency:
    def test_other_dimension_offers_exactly_the_generic_directions(self, vocab):
        assert set(vocab["other"]["directions"]) == {"prefer", "avoid"}

    def test_procedure_names_only_directions_that_exist(self):
        text = DOC.read_text(encoding="utf-8")
        assert "`more`, `less`" not in text

    def test_no_two_directions_of_a_dimension_share_a_meaning_marker(self, vocab):
        # One key per signal: the doc forbids aliases inside a dimension.
        for slug, dim in vocab.items():
            assert len(set(dim["directions"])) == len(dim["directions"]), slug
