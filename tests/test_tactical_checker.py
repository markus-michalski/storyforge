"""Tests for ``tools.analysis.tactical_checker`` — Issue #75.

Pre-write sanity check for combat and travel scenes: cross-reference
character tactical profiles with the scene outline and surface
walking-order / formation problems before they make it to draft.
"""

from __future__ import annotations

from pathlib import Path

from tools.analysis.tactical_checker import (
    TacticalProfile,
    analyze_tactical_setup,
    detect_positions,
    is_tactical_scene,
    load_tactical_profiles,
    parse_tactical_profile,
    verify_tactical_setup,
)


# ---------------------------------------------------------------------------
# is_tactical_scene — combat/travel keyword detector
# ---------------------------------------------------------------------------


class TestIsTacticalScene:
    def test_walk_through_dangerous_space_triggers(self):
        text = "They walk through the snow toward the trailhead."
        assert is_tactical_scene(text) is True

    def test_combat_keyword_attack_triggers(self):
        text = "The attack comes from the tree line."
        assert is_tactical_scene(text) is True

    def test_drive_to_location_triggers(self):
        text = "Kael drives the truck up the mountain pass."
        assert is_tactical_scene(text) is True

    def test_hike_triggers(self):
        text = "They hike single-file toward the cabin."
        assert is_tactical_scene(text) is True

    def test_enter_the_building_triggers(self):
        text = "They approach and enter the building from the south."
        assert is_tactical_scene(text) is True

    def test_quiet_dialogue_scene_does_not_trigger(self):
        text = (
            "Theo and Miriel sit at the kitchen table. Miriel kneads bread. "
            "They talk about the past."
        )
        assert is_tactical_scene(text) is False

    def test_empty_text_does_not_trigger(self):
        assert is_tactical_scene("") is False


# ---------------------------------------------------------------------------
# parse_tactical_profile — load tactical block from character markdown
# ---------------------------------------------------------------------------


THEO_MD = """---
name: "Theo"
role: "protagonist"
tactical:
  protector_role: false
  protected_role: true
  combat_skill: none
  movement_lead: false
  movement_rear: false
  vulnerable_to:
    - daylight
    - silver
  carries: []
---

# Theo
"""

KAEL_MD = """---
name: "Kael"
role: "deuteragonist"
tactical:
  protector_role: true
  protected_role: false
  combat_skill: high
  movement_lead: true
  movement_rear: false
  vulnerable_to:
    - daylight
  carries: [knife, backup_blade]
---

# Kael
"""

CHARACTER_NO_TACTICAL_MD = """---
name: "Random Side Character"
role: "supporting"
---

# Random
"""


def _write_char(tmp_path: Path, slug: str, content: str) -> Path:
    path = tmp_path / f"{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


class TestParseTacticalProfile:
    def test_loads_full_tactical_block(self, tmp_path):
        path = _write_char(tmp_path, "theo", THEO_MD)
        profile = parse_tactical_profile(path)
        assert profile is not None
        assert profile.name == "Theo"
        assert profile.slug == "theo"
        assert profile.protector_role is False
        assert profile.protected_role is True
        assert profile.combat_skill == "none"
        assert profile.movement_lead is False
        assert profile.movement_rear is False
        assert "daylight" in profile.vulnerable_to
        assert profile.has_tactical_data is True

    def test_protector_profile_loads(self, tmp_path):
        path = _write_char(tmp_path, "kael", KAEL_MD)
        profile = parse_tactical_profile(path)
        assert profile is not None
        assert profile.protector_role is True
        assert profile.movement_lead is True
        assert "knife" in profile.carries

    def test_character_without_tactical_block_returns_default(self, tmp_path):
        path = _write_char(tmp_path, "random", CHARACTER_NO_TACTICAL_MD)
        profile = parse_tactical_profile(path)
        # Still returns a profile so we know the character exists, but
        # has_tactical_data signals there's nothing to validate against.
        assert profile is not None
        assert profile.has_tactical_data is False
        assert profile.protector_role is False
        assert profile.protected_role is False

    def test_missing_file_returns_none(self, tmp_path):
        assert parse_tactical_profile(tmp_path / "ghost.md") is None


# ---------------------------------------------------------------------------
# detect_positions — extract walking-order positions from scene text
# ---------------------------------------------------------------------------


class TestDetectPositions:
    def test_rear_keyword_back_of_formation(self):
        text = "Theo walked at the back of the formation, the others ahead."
        positions = detect_positions(
            text,
            character_names=["Theo", "Kael", "Viktor", "Dom"],
        )
        assert positions["Theo"] == "rear"

    def test_point_keyword_takes_lead(self):
        text = "Kael took point. Viktor brought up the rear."
        positions = detect_positions(text, character_names=["Kael", "Viktor"])
        assert positions["Kael"] == "lead"
        assert positions["Viktor"] == "rear"

    def test_flanked_keyword_yields_middle(self):
        text = "Theo walked flanked by Kael at point and Viktor at the rear."
        positions = detect_positions(
            text, character_names=["Theo", "Kael", "Viktor"],
        )
        assert positions["Theo"] == "middle"
        assert positions["Kael"] == "lead"
        assert positions["Viktor"] == "rear"

    def test_unknown_when_character_not_mentioned(self):
        text = "Kael took point."
        positions = detect_positions(text, character_names=["Theo", "Kael"])
        assert positions["Theo"] == "unknown"
        assert positions["Kael"] == "lead"


# ---------------------------------------------------------------------------
# analyze_tactical_setup — heuristic engine
# ---------------------------------------------------------------------------


def _theo() -> TacticalProfile:
    return TacticalProfile(
        name="Theo", slug="theo",
        protector_role=False, protected_role=True,
        combat_skill="none",
        movement_lead=False, movement_rear=False,
        vulnerable_to=("daylight", "silver"),
        carries=(),
        has_tactical_data=True,
    )


def _kael() -> TacticalProfile:
    return TacticalProfile(
        name="Kael", slug="kael",
        protector_role=True, protected_role=False,
        combat_skill="high",
        movement_lead=True, movement_rear=False,
        vulnerable_to=("daylight",),
        carries=("knife", "backup_blade"),
        has_tactical_data=True,
    )


def _viktor() -> TacticalProfile:
    return TacticalProfile(
        name="Viktor", slug="viktor",
        protector_role=True, protected_role=False,
        combat_skill="elite",
        movement_lead=False, movement_rear=True,
        vulnerable_to=("daylight",),
        carries=("blade",),
        has_tactical_data=True,
    )


def _dom() -> TacticalProfile:
    return TacticalProfile(
        name="Dom", slug="dom",
        protector_role=True, protected_role=False,
        combat_skill="high",
        movement_lead=False, movement_rear=False,
        vulnerable_to=("daylight",),
        carries=(),
        has_tactical_data=True,
    )


class TestAnalyzeTacticalSetup:
    def test_protected_at_rear_warns(self):
        # Acceptance: Theo at the rear of a Kael/Viktor/Dom protector
        # team triggers a warning.
        scene_text = (
            "Theo walked at the back of the formation. "
            "Kael led the way, Viktor and Dom flanked the middle."
        )
        analysis = analyze_tactical_setup(
            scene_text,
            profiles=[_theo(), _kael(), _viktor(), _dom()],
        )
        assert analysis.passes is False
        assert any(
            "Theo" in w.message and "rear" in w.message.lower()
            for w in analysis.warnings
        )

    def test_protected_flanked_passes(self):
        # Acceptance: Theo flanked by Kael (point) and Viktor (rear) passes.
        scene_text = (
            "Theo walked flanked by Kael at point and Viktor at the rear. "
            "They moved single-file toward the trailhead."
        )
        analysis = analyze_tactical_setup(
            scene_text,
            profiles=[_theo(), _kael(), _viktor()],
        )
        assert analysis.passes is True
        # No "Theo at rear" warnings.
        assert not any(
            "Theo" in w.message and "rear" in w.message.lower()
            for w in analysis.warnings
        )

    def test_returns_at_least_three_questions(self):
        # Acceptance: tool returns at least 3 tactical questions for
        # any combat/travel scene.
        scene_text = "They walk through the woods toward the cabin."
        analysis = analyze_tactical_setup(
            scene_text, profiles=[_theo(), _kael()],
        )
        assert len(analysis.questions_for_writer) >= 3

    def test_questions_returned_even_when_passes(self):
        scene_text = (
            "Theo walked flanked by Kael at point and Viktor at the rear."
        )
        analysis = analyze_tactical_setup(
            scene_text,
            profiles=[_theo(), _kael(), _viktor()],
        )
        assert analysis.passes is True
        assert len(analysis.questions_for_writer) >= 3

    def test_no_tactical_data_degrades_gracefully(self):
        # Acceptance: graceful degrade when characters lack tactical data.
        no_data_theo = TacticalProfile(
            name="Theo", slug="theo",
            protector_role=False, protected_role=False,
            combat_skill="unknown",
            movement_lead=False, movement_rear=False,
            vulnerable_to=(), carries=(),
            has_tactical_data=False,
        )
        scene_text = "Theo walked at the back of the line."
        analysis = analyze_tactical_setup(
            scene_text, profiles=[no_data_theo],
        )
        # No crash; passes (we can't validate without data) but a
        # warning notes the missing tactical profile.
        assert analysis.passes is True
        assert any(
            "tactical profile" in w.message.lower()
            or "no tactical" in w.message.lower()
            for w in analysis.warnings
        )
        assert len(analysis.questions_for_writer) >= 3


# ---------------------------------------------------------------------------
# load_tactical_profiles — book-level loader
# ---------------------------------------------------------------------------


class TestLoadTacticalProfiles:
    def test_loads_profiles_for_listed_slugs(self, tmp_path):
        chars = tmp_path / "book" / "characters"
        chars.mkdir(parents=True)
        _write_char(chars, "theo", THEO_MD)
        _write_char(chars, "kael", KAEL_MD)
        # Skip a character that isn't requested.
        _write_char(chars, "random", CHARACTER_NO_TACTICAL_MD)

        profiles = load_tactical_profiles(
            tmp_path / "book", slugs=["theo", "kael"],
        )
        assert {p.slug for p in profiles} == {"theo", "kael"}

    def test_missing_character_dropped_silently(self, tmp_path):
        chars = tmp_path / "book" / "characters"
        chars.mkdir(parents=True)
        _write_char(chars, "theo", THEO_MD)

        profiles = load_tactical_profiles(
            tmp_path / "book", slugs=["theo", "ghost"],
        )
        # Only Theo loaded; ghost is not on disk so it's dropped.
        assert {p.slug for p in profiles} == {"theo"}


# ---------------------------------------------------------------------------
# verify_tactical_setup — full orchestrator (used by MCP tool)
# ---------------------------------------------------------------------------


class TestVerifyTacticalSetup:
    def test_end_to_end_warn_case(self, tmp_path):
        chars = tmp_path / "book" / "characters"
        chars.mkdir(parents=True)
        _write_char(chars, "theo", THEO_MD)
        _write_char(chars, "kael", KAEL_MD)
        _write_char(chars, "viktor", """---
name: "Viktor"
tactical:
  protector_role: true
  protected_role: false
  combat_skill: elite
  movement_lead: false
  movement_rear: true
---

# Viktor
""")

        result = verify_tactical_setup(
            tmp_path / "book",
            scene_outline_text=(
                "Theo walks at the back of the formation. "
                "Kael leads, Viktor walks in the middle."
            ),
            characters_present=["theo", "kael", "viktor"],
        )
        assert result["passes"] is False
        assert isinstance(result["warnings"], list)
        assert isinstance(result["questions_for_writer"], list)
        assert len(result["questions_for_writer"]) >= 3
