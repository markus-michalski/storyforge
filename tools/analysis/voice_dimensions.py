"""Closed vocabulary of voice dimensions — Epic #663 / Issue #666.

The vocabulary lives in ``reference/craft/voice-dimensions.md`` (one fenced
``yaml`` block under ``## Vocabulary``) so the author-facing document and the
machine-readable key set cannot drift apart.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

DOC_RELATIVE = Path("reference") / "craft" / "voice-dimensions.md"
VALID_CATEGORIES: frozenset[str] = frozenset({"fiction", "memoir"})
MEMOIR_ONLY_DIMENSIONS: frozenset[str] = frozenset({
    "reflective_platitude",
    "looking_back_hinge",
    "tidy_lesson_ending",
    "hedging",
    "therapeutic_reframe",
    "explanation_after_image",
})

_BLOCK_RE = re.compile(
    r"^##\s+Vocabulary\s*$.*?^```yaml\s*\n(?P<body>.*?)^```\s*$",
    re.DOTALL | re.MULTILINE,
)
_cache: dict[Path, tuple[float, dict[str, dict[str, Any]]]] = {}


class VoiceDimensionError(ValueError):
    """Raised for a missing/invalid vocabulary or an invalid classification."""


def _default_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    return Path(env) if env else Path(__file__).resolve().parent.parent.parent


def load_voice_dimensions(plugin_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return ``{dimension: {definition, categories, directions, examples}}``."""
    root = Path(plugin_root) if plugin_root is not None else _default_root()
    path = root / DOC_RELATIVE
    if not path.is_file():
        raise VoiceDimensionError(f"voice-dimensions reference not found at {path}")

    mtime = path.stat().st_mtime
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]

    match = _BLOCK_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise VoiceDimensionError(
            f"{path} has no '## Vocabulary' section with a fenced yaml vocabulary block"
        )
    try:
        data = yaml.safe_load(match.group("body"))
    except yaml.YAMLError as exc:
        raise VoiceDimensionError(f"vocabulary block in {path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise VoiceDimensionError(f"vocabulary block in {path} is empty")

    _cache[path] = (mtime, data)
    return data


def allowed_dimensions(book_category: str, plugin_root: Path | None = None) -> list[str]:
    _check_category(book_category)
    return [
        slug
        for slug, dim in load_voice_dimensions(plugin_root).items()
        if book_category in dim["categories"]
    ]


def validate_classification(
    dimension: str,
    direction: str,
    book_category: str,
    plugin_root: Path | None = None,
) -> None:
    """Raise :class:`VoiceDimensionError` unless the pair is in the closed vocabulary."""
    _check_category(book_category)
    vocab = load_voice_dimensions(plugin_root)

    if dimension not in vocab:
        raise VoiceDimensionError(
            f"unknown dimension {dimension!r}; allowed for {book_category}: "
            f"{', '.join(allowed_dimensions(book_category, plugin_root))}"
        )
    dim = vocab[dimension]
    if book_category not in dim["categories"]:
        raise VoiceDimensionError(
            f"dimension {dimension!r} applies to {', '.join(dim['categories'])} books only, "
            f"not {book_category}"
        )
    if direction not in dim["directions"]:
        raise VoiceDimensionError(
            f"unknown direction {direction!r} for {dimension!r}; allowed: "
            f"{', '.join(dim['directions'])}"
        )


def direction_kind(dimension: str, direction: str, plugin_root: Path | None = None) -> str:
    """Return ``"prefer"`` or ``"avoid"`` for a direction."""
    return str(load_voice_dimensions(plugin_root)[dimension]["directions"][direction]["kind"])


def opposite_direction(
    dimension: str, direction: str, plugin_root: Path | None = None
) -> str | None:
    """Return the opposing direction within the same dimension, if one is defined."""
    spec = load_voice_dimensions(plugin_root)[dimension]["directions"][direction]
    opposite = spec.get("opposite")
    return str(opposite) if opposite else None


def _check_category(book_category: str) -> None:
    if book_category not in VALID_CATEGORIES:
        raise VoiceDimensionError(
            f"invalid book_category {book_category!r}; expected one of {sorted(VALID_CATEGORIES)}"
        )
