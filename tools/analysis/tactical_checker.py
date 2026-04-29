"""Tactical sanity checker for combat and travel scenes — Issue #75.

Cross-references the optional `tactical` block of each character's
markdown profile with the scene outline, and surfaces walking-order
or formation problems before the scene is written. The MCP tool
``verify_tactical_setup`` orchestrates load + analysis and returns a
JSON brief (``passes`` / ``warnings`` / ``questions_for_writer``) so
``chapter-writer`` can resolve issues before drafting.

Heuristic — not a ground-truth model. The purpose is to force 30
seconds of structured thought before tactical scenes, not to validate
every formation. False positives are acceptable; false negatives
(silent passes on the obviously broken setup beta-feedback called
out) are not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.state.parsers import parse_frontmatter


# ---------------------------------------------------------------------------
# Tactical-scene detection
# ---------------------------------------------------------------------------

# Single-word triggers covered by a word-boundary match. Multi-word
# phrases are matched separately because the boundary regex would fight
# the whitespace between tokens.
_TACTICAL_WORD_KEYWORDS = (
    "fight",
    "fights",
    "fighting",
    "fought",
    "attack",
    "attacks",
    "attacking",
    "attacked",
    "combat",
    "drive",
    "drives",
    "driving",
    "drove",
    "walk",
    "walks",
    "walking",
    "walked",
    "hike",
    "hikes",
    "hiking",
    "hiked",
    "run",
    "runs",
    "running",
    "ran",
    "mission",
    "approach",
    "approaches",
    "approaching",
    "approached",
    "ambush",
    "ambushed",
    "raid",
    "infiltrate",
    "extract",
    "pursue",
    "flee",
    "fled",
)

_TACTICAL_PHRASES = (
    "enter the building",
    "enter the house",
    "breach the door",
    "go in hot",
    "single-file",
    "cover me",
)


def is_tactical_scene(scene_text: str) -> bool:
    """Return True when the scene reads as combat or group movement.

    Detects overt action verbs (``fight``, ``attack``, ``walk``,
    ``drive``, etc.) and a small set of multi-word phrases. A quiet
    dialogue scene with no movement keywords stays False so the
    pre-write check does not run on every kitchen-table beat.
    """
    if not scene_text:
        return False
    lowered = scene_text.lower()
    for phrase in _TACTICAL_PHRASES:
        if phrase in lowered:
            return True
    if re.search(
        r"\b(?:" + "|".join(_TACTICAL_WORD_KEYWORDS) + r")\b",
        lowered,
    ):
        return True
    return False


# ---------------------------------------------------------------------------
# Tactical profile (loaded from character markdown frontmatter)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TacticalProfile:
    """Per-character tactical metadata used by the formation checker."""

    name: str
    slug: str
    protector_role: bool = False
    protected_role: bool = False
    combat_skill: str = "unknown"
    movement_lead: bool = False
    movement_rear: bool = False
    vulnerable_to: tuple[str, ...] = ()
    carries: tuple[str, ...] = ()
    has_tactical_data: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "protector_role": self.protector_role,
            "protected_role": self.protected_role,
            "combat_skill": self.combat_skill,
            "movement_lead": self.movement_lead,
            "movement_rear": self.movement_rear,
            "vulnerable_to": list(self.vulnerable_to),
            "carries": list(self.carries),
            "has_tactical_data": self.has_tactical_data,
        }


def _coerce_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(v) for v in value)
    if isinstance(value, str):
        return (value,)
    return ()


def parse_tactical_profile(path: Path) -> TacticalProfile | None:
    """Load a TacticalProfile from a character markdown file.

    Characters without a ``tactical:`` frontmatter block still load —
    the returned profile carries ``has_tactical_data=False`` so the
    analyzer can warn rather than silently pass.
    """
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    meta, _body = parse_frontmatter(text)
    tactical = meta.get("tactical")
    has_data = isinstance(tactical, dict) and bool(tactical)
    if not isinstance(tactical, dict):
        tactical = {}

    return TacticalProfile(
        name=str(meta.get("name", path.stem)),
        slug=path.stem,
        protector_role=bool(tactical.get("protector_role", False)),
        protected_role=bool(tactical.get("protected_role", False)),
        combat_skill=str(tactical.get("combat_skill", "unknown")),
        movement_lead=bool(tactical.get("movement_lead", False)),
        movement_rear=bool(tactical.get("movement_rear", False)),
        vulnerable_to=_coerce_list(tactical.get("vulnerable_to", [])),
        carries=_coerce_list(tactical.get("carries", [])),
        has_tactical_data=has_data,
    )


def load_tactical_profiles(
    book_root: Path,
    slugs: list[str],
) -> list[TacticalProfile]:
    """Load tactical profiles for the given character slugs.

    Missing files are silently dropped so callers can pass scene-derived
    rosters that may include placeholder names. Pure I/O wrapper around
    :func:`parse_tactical_profile`.
    """
    chars_dir = book_root / "characters"
    profiles: list[TacticalProfile] = []
    for slug in slugs:
        profile = parse_tactical_profile(chars_dir / f"{slug}.md")
        if profile is not None:
            profiles.append(profile)
    return profiles


# ---------------------------------------------------------------------------
# Position detection
# ---------------------------------------------------------------------------

# Position-keyword vocabularies. Order matters within a class — the
# more specific phrase wins when multiple match the same character.
_LEAD_KEYWORDS = (
    "took the lead",
    "takes the lead",
    "leads the way",
    "led the way",
    "took point",
    "takes point",
    "at point",
    "on point",
    "leading",
    "leads",
    "led",
    "lead",
    "point",
    "front",
    "ahead",
    "scouts",
    "scout",
    "scouting",
)
_REAR_KEYWORDS = (
    "brings up the rear",
    "brought up the rear",
    "at the rear",
    "in the rear",
    "at the back",
    "in the back",
    "falls behind",
    "fell behind",
    "trailing",
    "trailed",
    "trail",
    "rear",
    "back",
    "tail",
    "last",
)
_MIDDLE_KEYWORDS = (
    "flanked by",
    "flanked",
    "flanks",
    "in the middle",
    "in between",
    "between",
    "walks in the middle",
    "walked in the middle",
)

_POSITION_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("middle", _MIDDLE_KEYWORDS),
    ("lead", _LEAD_KEYWORDS),
    ("rear", _REAR_KEYWORDS),
)

# Flat keyword list, sorted longest-first so multi-word phrases match
# before their substrings (e.g. "at the back" wins over "back").
_FLAT_POSITION_KEYWORDS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        ((kw, label) for label, keywords in _POSITION_CLASSES for kw in keywords),
        key=lambda item: -len(item[0]),
    )
)


def _find_position_keywords(text: str) -> list[tuple[int, int, str]]:
    """Return non-overlapping (start, end, class) hits, longest-match first.

    The greedy occupation pass guarantees ``"at the back"`` consumes its
    span before the bare ``"back"`` keyword can claim a subset of the
    same characters.
    """
    text_lower = text.lower()
    occupied = [False] * len(text)
    hits: list[tuple[int, int, str]] = []
    for keyword, label in _FLAT_POSITION_KEYWORDS:
        for match in re.finditer(re.escape(keyword), text_lower):
            start, end = match.start(), match.end()
            if any(occupied[start:end]):
                continue
            for i in range(start, end):
                occupied[i] = True
            hits.append((start, end, label))
    hits.sort()
    return hits


def _split_sentences(text: str) -> list[tuple[int, int]]:
    """Sentence boundaries as ``(start, end)`` offsets into ``text``."""
    spans: list[tuple[int, int]] = []
    last = 0
    for match in re.finditer(r"[.!?](?:\s|$)", text):
        spans.append((last, match.end()))
        last = match.end()
    if last < len(text):
        spans.append((last, len(text)))
    return spans


def detect_positions(
    scene_text: str,
    character_names: list[str],
) -> dict[str, str]:
    """Map each character name to ``lead`` / ``rear`` / ``middle`` / ``unknown``.

    Heuristic — attributes each position keyword to the *preceding*
    character name in its sentence. This matches natural prose
    syntax: "Theo walked flanked by Kael at point" attributes
    ``flanked`` to Theo and ``point`` to Kael, not the reverse.
    Sentence boundaries prevent keyword bleed across full stops.
    Falls back to nearest-name attribution when no name precedes the
    keyword in the same sentence.
    """
    positions: dict[str, str] = {name: "unknown" for name in character_names}
    if not scene_text or not character_names:
        return positions

    for sent_start, sent_end in _split_sentences(scene_text):
        sentence = scene_text[sent_start:sent_end]
        name_hits: list[tuple[int, int, str]] = []
        for name in character_names:
            for match in re.finditer(re.escape(name), sentence):
                name_hits.append((match.start(), match.end(), name))
        if not name_hits:
            continue
        keyword_hits = _find_position_keywords(sentence)
        if not keyword_hits:
            continue
        for kstart, _kend, klabel in keyword_hits:
            preceding = [hit for hit in name_hits if hit[1] <= kstart]
            target_name: str | None = None
            if preceding:
                target_name = max(preceding, key=lambda hit: hit[1])[2]
            else:
                target_name = min(
                    name_hits,
                    key=lambda hit: abs(hit[0] - kstart),
                )[2]
            if positions[target_name] == "unknown":
                positions[target_name] = klabel
    return positions


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TacticalWarning:
    severity: str  # "warn" | "info"
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class TacticalAnalysis:
    passes: bool
    warnings: list[TacticalWarning] = field(default_factory=list)
    questions_for_writer: list[str] = field(default_factory=list)
    detected_positions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passes": self.passes,
            "warnings": [w.to_dict() for w in self.warnings],
            "questions_for_writer": list(self.questions_for_writer),
            "detected_positions": dict(self.detected_positions),
        }


# Universal questions surface for every combat/travel scene. The first
# three apply to any group-movement scene; the last two specialize
# when a protected/vulnerable character is present.
_BASE_QUESTIONS: tuple[str, ...] = (
    "Who scouts ahead?",
    "What is the formation if they need to break and run?",
    "Who has line-of-sight on whom when contact happens?",
    "What's the order of march if attacked from behind?",
    "Where does each character go to ground if shooting starts?",
)

_PROTECTED_QUESTION_TEMPLATE = "Who is closest to {name} at all times?"
_VULNERABLE_QUESTION_TEMPLATE = "{name} is most vulnerable — who is covering them?"


def _build_questions(profiles: list[TacticalProfile]) -> list[str]:
    questions: list[str] = []
    protected = [p for p in profiles if p.protected_role]
    if protected:
        # One specialized question per protected character (cap at 2 to
        # keep the brief readable).
        for p in protected[:2]:
            questions.append(_PROTECTED_QUESTION_TEMPLATE.format(name=p.name))
    most_vulnerable = _pick_most_vulnerable(profiles)
    if most_vulnerable is not None and not protected:
        questions.append(_VULNERABLE_QUESTION_TEMPLATE.format(name=most_vulnerable.name))
    # Backfill from the base list until we have at least 3 questions.
    for q in _BASE_QUESTIONS:
        if len(questions) >= 5:
            break
        if q not in questions:
            questions.append(q)
    return questions[:5]


def _pick_most_vulnerable(
    profiles: list[TacticalProfile],
) -> TacticalProfile | None:
    """Pick the lowest-skill / non-protector character for the
    'who covers them' question."""
    skill_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "elite": 4}
    candidates = [p for p in profiles if not p.protector_role]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda p: skill_rank.get(p.combat_skill, 5),
    )


def analyze_tactical_setup(
    scene_text: str,
    profiles: list[TacticalProfile],
) -> TacticalAnalysis:
    """Apply walking-order heuristics and return the analysis brief.

    Rules:

    * **Protected at rear** → warn. The unprotected human at the back
      of a protector formation is the named beta-feedback regression.
    * **Protected at lead** → warn. Scouts go up front; protected
      characters do not.
    * **Protectors absent or all at rear** when a protected character
      is present → warn.
    * **No tactical data on any present character** → warn (graceful
      degrade — the writer should still get the questions).

    Always returns at least three questions for the writer regardless
    of pass/fail.
    """
    warnings: list[TacticalWarning] = []
    positions = detect_positions(
        scene_text,
        character_names=[p.name for p in profiles],
    )

    protectors = [p for p in profiles if p.protector_role]
    protected = [p for p in profiles if p.protected_role]

    # R0: missing tactical data → info-severity. Graceful degrade so
    # the writer still gets the questions list, but with a nudge to
    # add tactical frontmatter on these characters.
    missing_data = [p for p in profiles if not p.has_tactical_data]
    if missing_data and not protectors and not protected:
        names = ", ".join(p.name for p in missing_data)
        warnings.append(
            TacticalWarning(
                severity="info",
                message=(
                    f"No tactical profile for: {names}. "
                    "Add a `tactical` block to each character's frontmatter "
                    "for richer formation checks."
                ),
            )
        )

    # R1: protected character at rear.
    for p in protected:
        if positions.get(p.name) == "rear" and protectors:
            others = ", ".join(pr.name for pr in protectors)
            warnings.append(
                TacticalWarning(
                    severity="warn",
                    message=(
                        f"{p.name} (protected_role: true, "
                        f"combat_skill: {p.combat_skill}) is in rear position. "
                        f"Protectors ({others}) should flank or trail."
                    ),
                )
            )

    # R2: protected character at lead.
    for p in protected:
        if positions.get(p.name) == "lead":
            warnings.append(
                TacticalWarning(
                    severity="warn",
                    message=(
                        f"{p.name} (protected_role: true) is at the lead. "
                        "Scouts/protectors take point — not the protected character."
                    ),
                )
            )

    # R3: protected present but no protector covers a forward or rear
    # position.
    if protected and protectors:
        protector_positions = {positions.get(pr.name, "unknown") for pr in protectors}
        if not (protector_positions & {"lead", "rear", "middle"}):
            warnings.append(
                TacticalWarning(
                    severity="warn",
                    message=(
                        "Protected character present but no protector has a "
                        "detectable position. Spell out who covers lead and rear."
                    ),
                )
            )

    # R4: lead position should match `movement_lead: true` when known.
    for name, pos in positions.items():
        if pos != "lead":
            continue
        profile = next((p for p in profiles if p.name == name), None)
        if profile is None or not profile.has_tactical_data:
            continue
        if not profile.movement_lead and not profile.protector_role:
            warnings.append(
                TacticalWarning(
                    severity="warn",
                    message=(
                        f"{name} is taking the lead but their profile has "
                        "movement_lead: false and protector_role: false. "
                        "Confirm this is intentional."
                    ),
                )
            )

    passes = not any(w.severity == "warn" for w in warnings)
    return TacticalAnalysis(
        passes=passes,
        warnings=warnings,
        questions_for_writer=_build_questions(profiles),
        detected_positions=positions,
    )


# ---------------------------------------------------------------------------
# MCP-facing orchestrator
# ---------------------------------------------------------------------------


def verify_tactical_setup(
    book_root: Path,
    scene_outline_text: str,
    characters_present: list[str],
) -> dict[str, Any]:
    """Load profiles + analyze + return JSON-ready dict.

    The MCP tool layer wraps this and wraps the result in
    ``json.dumps``. Returning a dict keeps unit tests cheap and lets
    the analyzer call this for assertion convenience.
    """
    profiles = load_tactical_profiles(book_root, characters_present)
    analysis = analyze_tactical_setup(scene_outline_text, profiles)
    return analysis.to_dict()
