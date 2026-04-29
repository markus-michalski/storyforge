"""Tests for ``tools.analysis.pov_boundary_checker`` — Issue #76.

Catches close-third POV boundary violations: prose that attributes
domain expertise to a POV character whose knowledge profile says
they have none. The named beta-feedback case is *"blood smells when
it has been on the ground for a while in cold air"* written from
Theo's IT-guy POV.
"""

from __future__ import annotations

from pathlib import Path

from tools.analysis.pov_boundary_checker import (
    CharacterKnowledge,
    PovBoundaryHit,
    load_domain_vocabularies,
    parse_character_knowledge,
    scan_pov_boundary,
    strip_dialog,
)


# ---------------------------------------------------------------------------
# parse_character_knowledge — load knowledge block from frontmatter
# ---------------------------------------------------------------------------


THEO_MD = """---
name: "Theo Wilkons"
role: "protagonist"
knowledge:
  expert: [it, programming, networking, devops]
  competent: [photography, brewing_coffee]
  layperson: [psychology, history, philosophy]
  none: [medicine, forensics, ballistics, tactical_combat]
---

# Theo Wilkons
"""

KAEL_MD = """---
name: "Kael"
role: "deuteragonist"
knowledge:
  expert: [tactical_combat, ballistics, forensics]
  competent: [medicine]
  layperson: []
  none: []
---

# Kael
"""

NO_KNOWLEDGE_MD = """---
name: "Random"
role: "supporting"
---

# Random
"""


def _write(tmp_path: Path, slug: str, body: str) -> Path:
    path = tmp_path / f"{slug}.md"
    path.write_text(body, encoding="utf-8")
    return path


class TestParseCharacterKnowledge:
    def test_loads_full_knowledge_block(self, tmp_path):
        path = _write(tmp_path, "theo-wilkons", THEO_MD)
        ck = parse_character_knowledge(path)
        assert ck is not None
        assert ck.name == "Theo Wilkons"
        assert ck.slug == "theo-wilkons"
        assert "forensics" in ck.none
        assert "psychology" in ck.layperson
        assert "it" in ck.expert
        assert ck.has_knowledge_data is True

    def test_returns_default_for_no_knowledge_block(self, tmp_path):
        path = _write(tmp_path, "random", NO_KNOWLEDGE_MD)
        ck = parse_character_knowledge(path)
        assert ck is not None
        assert ck.has_knowledge_data is False
        assert ck.expert == ()
        assert ck.none == ()

    def test_returns_none_for_missing_file(self, tmp_path):
        assert parse_character_knowledge(tmp_path / "ghost.md") is None


# ---------------------------------------------------------------------------
# load_domain_vocabularies — parse markdown bullet lists
# ---------------------------------------------------------------------------


FORENSICS_VOCAB = """# Forensics

A small starter set. Communities can extend via PR.

- blood spatter
- lividity
- rigor mortis
- blood smells when
- decomposition rate
"""

TACTICAL_COMBAT_VOCAB = """# Tactical Combat

- field of fire
- enfilade
- breach point
- fatal funnel
- flag of convenience
"""


class TestLoadDomainVocabularies:
    def test_loads_multiple_domains(self, tmp_path):
        domain_dir = tmp_path / "knowledge-domains"
        domain_dir.mkdir()
        (domain_dir / "forensics.md").write_text(FORENSICS_VOCAB, encoding="utf-8")
        (domain_dir / "tactical_combat.md").write_text(
            TACTICAL_COMBAT_VOCAB,
            encoding="utf-8",
        )

        vocab = load_domain_vocabularies(domain_dir)
        assert "forensics" in vocab
        assert "tactical_combat" in vocab
        assert "blood spatter" in vocab["forensics"]
        assert "blood smells when" in vocab["forensics"]
        assert "fatal funnel" in vocab["tactical_combat"]

    def test_ignores_non_bullet_lines(self, tmp_path):
        domain_dir = tmp_path / "knowledge-domains"
        domain_dir.mkdir()
        (domain_dir / "forensics.md").write_text(FORENSICS_VOCAB, encoding="utf-8")
        vocab = load_domain_vocabularies(domain_dir)
        # The "A small starter set..." line is prose, not a bullet — must
        # not be picked up as a vocabulary term.
        assert all("starter set" not in term for term in vocab["forensics"])

    def test_returns_empty_for_missing_dir(self, tmp_path):
        assert load_domain_vocabularies(tmp_path / "nope") == {}

    def test_returns_empty_for_dir_with_no_md_files(self, tmp_path):
        empty = tmp_path / "knowledge-domains"
        empty.mkdir()
        (empty / "README.txt").write_text("not markdown", encoding="utf-8")
        assert load_domain_vocabularies(empty) == {}


# ---------------------------------------------------------------------------
# strip_dialog — remove quoted dialog from prose so the scan only sees
# narration / interiority
# ---------------------------------------------------------------------------


class TestStripDialog:
    def test_strips_straight_double_quotes(self):
        text = 'Theo turned. "Blood spatter," Kael said, glancing at the floor.'
        stripped = strip_dialog(text)
        assert "blood spatter" not in stripped.lower()
        assert "Theo turned" in stripped

    def test_strips_curly_double_quotes(self):
        text = "He paused. “Fatal funnel”, Kael muttered."
        stripped = strip_dialog(text)
        assert "fatal funnel" not in stripped.lower()
        assert "He paused" in stripped

    def test_preserves_non_dialog_prose(self):
        text = "Theo walked to the kitchen. The coffee was already brewed."
        stripped = strip_dialog(text)
        assert stripped.strip() == text.strip()

    def test_handles_multiline_quotes(self):
        text = 'Theo waited. "Sometimes blood spatter\ntells more than the body itself," Kael said.'
        stripped = strip_dialog(text)
        assert "blood spatter" not in stripped.lower()


# ---------------------------------------------------------------------------
# scan_pov_boundary — the core checker
# ---------------------------------------------------------------------------


def _theo() -> CharacterKnowledge:
    return CharacterKnowledge(
        name="Theo Wilkons",
        slug="theo-wilkons",
        expert=("it", "programming"),
        competent=("photography",),
        layperson=("psychology",),
        none=("forensics", "ballistics", "medicine", "tactical_combat"),
        has_knowledge_data=True,
    )


def _kael() -> CharacterKnowledge:
    return CharacterKnowledge(
        name="Kael",
        slug="kael",
        expert=("tactical_combat", "ballistics", "forensics"),
        competent=("medicine",),
        layperson=(),
        none=(),
        has_knowledge_data=True,
    )


_DOMAIN_VOCAB = {
    "forensics": ["blood smells when", "lividity", "rigor mortis", "blood spatter"],
    "tactical_combat": ["fatal funnel", "field of fire", "breach point"],
    "ballistics": ["muzzle velocity", "ballistic coefficient"],
    "medicine": ["subdural hematoma", "ringer's lactate"],
}


class TestScanPovBoundary:
    def test_flags_forensics_term_in_theo_pov(self):
        # Acceptance: blood-smells-when in Theo POV is flagged when
        # forensics: none.
        text = (
            "Theo crouched. The blood smells when it has been on the "
            "ground for a while in cold air, and this was older."
        )
        hits = scan_pov_boundary(text, _theo(), _DOMAIN_VOCAB)
        assert any(h.domain == "forensics" and "blood smells when" in h.phrase.lower() for h in hits)
        # Severity stays warn — POV calls are nuanced.
        assert all(h.severity == "warn" for h in hits)

    def test_does_not_flag_for_competent_or_expert_pov(self):
        # Acceptance: same sentence in Kael POV (forensics: expert)
        # does not flag.
        text = "Kael crouched. The blood smells when it has been on the ground for a while in cold air."
        hits = scan_pov_boundary(text, _kael(), _DOMAIN_VOCAB)
        assert not any(h.domain == "forensics" for h in hits)

    def test_does_not_flag_inside_dialog(self):
        # Acceptance: same phrase in dialog by another character
        # does not flag.
        text = (
            'Kael nodded at the floor. "Blood smells when it has been on the ground for a while in cold air," he said.'
        )
        hits = scan_pov_boundary(text, _theo(), _DOMAIN_VOCAB)
        assert not any(h.domain == "forensics" for h in hits)

    def test_layperson_knowledge_still_flags(self):
        # Layperson is below the threshold for technical terms — flag.
        theo_layperson_forensics = CharacterKnowledge(
            name="Theo",
            slug="theo",
            expert=(),
            competent=(),
            layperson=("forensics",),
            none=(),
            has_knowledge_data=True,
        )
        text = "He noted the lividity in the corpse's lower back."
        hits = scan_pov_boundary(
            text,
            theo_layperson_forensics,
            _DOMAIN_VOCAB,
        )
        assert any(h.domain == "forensics" and h.knowledge_level == "layperson" for h in hits)

    def test_no_hit_when_no_domain_keywords_present(self):
        text = "Theo opened the laptop. The terminal blinked. He typed a command and waited."
        hits = scan_pov_boundary(text, _theo(), _DOMAIN_VOCAB)
        assert hits == []

    def test_hit_carries_remediation_options(self):
        text = "He noted the lividity."
        hits = scan_pov_boundary(text, _theo(), _DOMAIN_VOCAB)
        assert hits
        hit = hits[0]
        assert isinstance(hit.options, list)
        # At least 2 remediation options surfaced (move-to-dialog,
        # reframe-as-lay).
        assert len(hit.options) >= 2

    def test_no_knowledge_data_skips_scan(self):
        no_data = CharacterKnowledge(
            name="Theo",
            slug="theo",
            expert=(),
            competent=(),
            layperson=(),
            none=(),
            has_knowledge_data=False,
        )
        text = "He noted the lividity."
        hits = scan_pov_boundary(text, no_data, _DOMAIN_VOCAB)
        # No data means we can't validate — pass through silently.
        assert hits == []

    def test_returns_PovBoundaryHit_instances(self):
        text = "He noted the lividity."
        hits = scan_pov_boundary(text, _theo(), _DOMAIN_VOCAB)
        assert all(isinstance(h, PovBoundaryHit) for h in hits)

    def test_hit_records_line_number(self):
        text = "Theo entered.\nThe room was dark.\nHe noted the lividity in the body.\n"
        hits = scan_pov_boundary(text, _theo(), _DOMAIN_VOCAB)
        assert hits
        assert hits[0].line == 3

    def test_word_boundary_avoids_substring_matches(self):
        # Smoke-tested regression: "pea" (medical abbreviation for
        # pulseless electrical activity) must NOT match inside
        # "appeared", "speak", "ahead", etc.
        text = "Theo crouched. A bowl appeared on the sideboard. He could speak now. The path lay ahead."
        vocab = {"medicine": ["pea", "pulseless electrical activity"]}
        hits = scan_pov_boundary(text, _theo(), vocab)
        assert hits == []

    def test_word_boundary_still_matches_standalone_token(self):
        text = "The monitor went flat — pea — and Kael shouted."
        vocab = {"medicine": ["pea"]}
        hits = scan_pov_boundary(text, _theo(), vocab)
        assert len(hits) == 1
        assert hits[0].domain == "medicine"

    def test_deduplicates_repeated_phrase_in_same_paragraph(self):
        # If the same phrase appears multiple times near each other,
        # don't flood with duplicate hits — one finding per phrase
        # per paragraph is enough for the writer to act on.
        text = "He saw the lividity. He photographed the lividity. Then he turned away from the lividity."
        hits = scan_pov_boundary(text, _theo(), _DOMAIN_VOCAB)
        forensics_hits = [h for h in hits if h.domain == "forensics"]
        assert len(forensics_hits) == 1
