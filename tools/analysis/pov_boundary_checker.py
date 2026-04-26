"""POV boundary checker — Issue #76.

Catches close-third POV violations: prose that attributes domain
expertise (forensics, tactical combat, ballistics, medicine, ...) to
a POV character whose ``knowledge`` profile says they have none or
only layperson awareness. The named beta-feedback case is *"blood
smells when it has been on the ground for a while in cold air"*
written from Theo's IT-guy POV.

Severity stays ``warn`` — POV calls are nuanced and the heuristic
will produce false positives. Books that want a hard gate can
extend the hook layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.state.parsers import parse_frontmatter


# ---------------------------------------------------------------------------
# Character knowledge profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CharacterKnowledge:
    """Per-character knowledge tiers.

    Tiers are exclusive: a domain belongs to exactly one of expert,
    competent, layperson, or none. ``has_knowledge_data`` is False for
    characters whose markdown carries no ``knowledge:`` block — the
    scanner skips those silently rather than producing noise.
    """

    name: str
    slug: str
    expert: tuple[str, ...] = ()
    competent: tuple[str, ...] = ()
    layperson: tuple[str, ...] = ()
    none: tuple[str, ...] = ()
    has_knowledge_data: bool = False

    def level_for(self, domain: str) -> str | None:
        """Return ``expert`` / ``competent`` / ``layperson`` / ``none``
        for ``domain``, or ``None`` if the character has no claim.

        Free-form domain names not assigned to any tier are treated as
        ``competent`` per the issue's design (``learned_from_kael``
        etc.) — but only when ``has_knowledge_data`` is True; otherwise
        we cannot validate anything.
        """
        if domain in self.none:
            return "none"
        if domain in self.layperson:
            return "layperson"
        if domain in self.competent:
            return "competent"
        if domain in self.expert:
            return "expert"
        return None


def _coerce_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(v).strip() for v in value if str(v).strip())
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    return ()


def parse_character_knowledge(path: Path) -> CharacterKnowledge | None:
    """Load a CharacterKnowledge from a character markdown file.

    Returns a profile with ``has_knowledge_data=False`` for characters
    that lack the ``knowledge:`` frontmatter block; returns None when
    the file is missing or unreadable.
    """
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, _body = parse_frontmatter(text)
    knowledge = meta.get("knowledge")
    has_data = isinstance(knowledge, dict) and bool(knowledge)
    if not isinstance(knowledge, dict):
        knowledge = {}

    return CharacterKnowledge(
        name=str(meta.get("name", path.stem)),
        slug=path.stem,
        expert=_coerce_tuple(knowledge.get("expert", ())),
        competent=_coerce_tuple(knowledge.get("competent", ())),
        layperson=_coerce_tuple(knowledge.get("layperson", ())),
        none=_coerce_tuple(knowledge.get("none", ())),
        has_knowledge_data=has_data,
    )


# ---------------------------------------------------------------------------
# Domain vocabulary loader
# ---------------------------------------------------------------------------

# Bullet-list lines: "- term" or "* term", possibly with leading whitespace.
_BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<term>[^#\n]+?)\s*$", re.MULTILINE)


def _parse_vocab_file(path: Path) -> list[str]:
    """Parse a markdown vocabulary file into a list of terms."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    terms: list[str] = []
    for match in _BULLET_RE.finditer(text):
        term = match.group("term").strip().lower()
        if term:
            terms.append(term)
    return terms


def load_domain_vocabularies(domain_dir: Path) -> dict[str, list[str]]:
    """Load all domain vocabularies from a directory of markdown files.

    Each ``.md`` file becomes one domain; the filename stem is the
    domain key. Bullet-list items are the terms. Empty / non-markdown
    files are skipped.
    """
    if not domain_dir.is_dir():
        return {}
    vocab: dict[str, list[str]] = {}
    for path in sorted(domain_dir.iterdir()):
        if path.suffix.lower() != ".md":
            continue
        terms = _parse_vocab_file(path)
        if terms:
            vocab[path.stem] = terms
    return vocab


# ---------------------------------------------------------------------------
# Dialog stripper
# ---------------------------------------------------------------------------

# Both straight and curly double quotes. ``re.DOTALL`` so multi-line
# dialog (a single quoted span broken across paragraphs) gets stripped
# in one pass.
_DIALOG_RE = re.compile(
    r'"[^"]*"|“[^”]*”',
    re.DOTALL,
)


def strip_dialog(text: str) -> str:
    """Remove quoted dialog from prose so the scanner only sees narration.

    POV-boundary checks fire on what the *narrator* knows, not on what
    a character says aloud. Stripping dialog before the scan is the
    minimal correct preprocessing — it's also what makes the
    "Kael said the blood smelled different" acceptance case pass.
    """
    return _DIALOG_RE.sub(" ", text)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PovBoundaryHit:
    """One POV-boundary violation."""

    severity: str  # "warn"
    domain: str
    knowledge_level: str  # "none" | "layperson"
    phrase: str
    pov_character: str
    line: int
    options: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "domain": self.domain,
            "knowledge_level": self.knowledge_level,
            "phrase": self.phrase,
            "pov_character": self.pov_character,
            "line": self.line,
            "options": list(self.options),
        }


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _build_options(
    phrase: str,
    domain: str,
    knowledge_level: str,
    pov_name: str,
) -> list[str]:
    """Three remediation options per finding.

    The options follow the issue's template: move into dialog by a
    character who would know, reframe as a lay observation, or cut.
    """
    return [
        f"(a) Move into dialog by a character who would know "
        f"({domain} expert).",
        f"(b) Reframe as {pov_name}'s lay observation — what would they "
        "actually notice without the technical vocabulary?",
        "(c) Cut entirely if it does not earn its place.",
    ]


def scan_pov_boundary(
    text: str,
    pov_knowledge: CharacterKnowledge,
    domain_vocab: dict[str, list[str]],
) -> list[PovBoundaryHit]:
    """Scan narration (dialog stripped) for domain vocabulary the POV
    character has ``none`` or ``layperson`` knowledge of.

    Multiple occurrences of the same phrase in the same paragraph
    collapse to one hit — the writer needs to know the phrase fired,
    not how many times.
    """
    if not pov_knowledge.has_knowledge_data:
        return []
    if not text or not domain_vocab:
        return []

    narration = strip_dialog(text)
    paragraphs = _paragraph_spans(narration)

    hits: list[PovBoundaryHit] = []
    seen_in_paragraph: set[tuple[int, str]] = set()

    for domain, terms in domain_vocab.items():
        level = pov_knowledge.level_for(domain)
        if level not in ("none", "layperson"):
            continue
        for term in terms:
            # Word-boundary match so "pea" (medical abbrev) doesn't fire
            # inside "appeared", "speak", "ahead", etc. Multi-word terms
            # like "blood smells when" still anchor on word boundaries
            # at both ends.
            pattern = re.compile(
                r"\b" + re.escape(term.lower()) + r"\b",
            )
            for match in pattern.finditer(narration.lower()):
                paragraph_idx = _paragraph_index(match.start(), paragraphs)
                key = (paragraph_idx, term)
                if key in seen_in_paragraph:
                    continue
                seen_in_paragraph.add(key)
                hits.append(PovBoundaryHit(
                    severity="warn",
                    domain=domain,
                    knowledge_level=level,
                    phrase=term,
                    pov_character=pov_knowledge.name,
                    line=_line_for_offset(text, _map_to_original(text, narration, match.start())),
                    options=_build_options(
                        term, domain, level, pov_knowledge.name,
                    ),
                ))
    hits.sort(key=lambda h: h.line)
    return hits


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets for each paragraph in ``text``.

    Paragraphs are separated by one or more blank lines.
    """
    spans: list[tuple[int, int]] = []
    last = 0
    for match in re.finditer(r"\n\s*\n", text):
        spans.append((last, match.start()))
        last = match.end()
    if last < len(text):
        spans.append((last, len(text)))
    return spans


def _paragraph_index(offset: int, spans: list[tuple[int, int]]) -> int:
    for idx, (start, end) in enumerate(spans):
        if start <= offset <= end:
            return idx
    return -1


def _map_to_original(
    original: str, narration: str, narration_offset: int,
) -> int:
    """Map a narration offset back into the original text.

    Dialog stripping replaces quoted spans with single spaces, so the
    narration is shorter than ``original``. We approximate the
    original offset by walking the original text and skipping
    dialog spans, matching narration character-by-character.
    """
    if narration_offset <= 0:
        return 0
    consumed = 0
    i = 0
    while i < len(original):
        # Detect dialog start at this position.
        match = _DIALOG_RE.match(original, i)
        if match is not None:
            # The stripper replaces this with a single space; that
            # space takes one slot in the narration string.
            if consumed >= narration_offset:
                return i
            consumed += 1
            i = match.end()
            continue
        if consumed >= narration_offset:
            return i
        consumed += 1
        i += 1
    return min(narration_offset, len(original) - 1)
