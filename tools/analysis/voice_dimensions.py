"""Closed vocabulary of voice dimensions — Epic #663 / Issue #666.

The vocabulary lives in ``reference/craft/voice-dimensions.md`` (one fenced
``yaml`` block under ``## Vocabulary``) so the author-facing document and the
machine-readable key set cannot drift apart.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

from tools.shared.config import get_plugin_root

DOC_RELATIVE = Path("reference") / "craft" / "voice-dimensions.md"
VALID_CATEGORIES: frozenset[str] = frozenset({"fiction", "memoir"})
VALID_KINDS: frozenset[str] = frozenset({"prefer", "avoid"})

# The fence must belong to the Vocabulary section: the lazy body may not cross
# another "## " heading.
_BLOCK_RE = re.compile(
    r"^##[ \t]+Vocabulary[ \t]*$(?:(?!^##[ \t]).)*?^```yaml[ \t]*\n(?P<body>.*?)^```[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
_cache: dict[Path, tuple[tuple[int, int], dict[str, dict[str, Any]]]] = {}


class VoiceDimensionError(ValueError):
    """Raised for a missing/invalid vocabulary or an invalid classification."""


def load_voice_dimensions(plugin_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return ``{dimension: {definition, categories, directions, examples}}``.

    The result is a private deep copy; callers may mutate it freely.
    """
    root = Path(plugin_root) if plugin_root is not None else get_plugin_root()
    path = root / DOC_RELATIVE
    if not path.is_file():
        raise VoiceDimensionError(f"voice-dimensions reference not found at {path}")

    stat = path.stat()
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _cache.get(path)
    if cached and cached[0] == key:
        return copy.deepcopy(cached[1])

    match = _BLOCK_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise VoiceDimensionError(
            f"{path} has no '## Vocabulary' section with a fenced yaml vocabulary block"
        )
    try:
        data = yaml.safe_load(match.group("body"))
    except yaml.YAMLError as exc:
        raise VoiceDimensionError(f"vocabulary block in {path} is not valid YAML: {exc}") from exc
    _validate_schema(data, path)

    _cache[path] = (key, data)
    return copy.deepcopy(data)


def _validate_schema(data: Any, path: Path) -> None:
    if not isinstance(data, dict) or not data:
        raise VoiceDimensionError(f"vocabulary block in {path} is empty or not a mapping")

    for slug, dim in data.items():
        where = f"dimension {slug!r} in {path}"
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", slug):
            raise VoiceDimensionError(f"invalid dimension slug {slug!r} in {path}")
        if not isinstance(dim, dict):
            raise VoiceDimensionError(f"{where} must be a mapping")

        definition = dim.get("definition")
        if not isinstance(definition, str) or not definition.strip():
            raise VoiceDimensionError(f"{where}: 'definition' must be a non-empty string")

        categories = dim.get("categories")
        if (
            not isinstance(categories, list)
            or not categories
            or not all(isinstance(c, str) and c in VALID_CATEGORIES for c in categories)
        ):
            raise VoiceDimensionError(
                f"{where}: 'categories' must be a non-empty list drawn from "
                f"{sorted(VALID_CATEGORIES)}"
            )

        examples = dim.get("examples")
        if (
            not isinstance(examples, list)
            or len(examples) < 2
            or not all(isinstance(e, str) and e.strip() for e in examples)
        ):
            raise VoiceDimensionError(f"{where}: 'examples' needs at least two non-empty strings")

        directions = dim.get("directions")
        if not isinstance(directions, dict) or not directions:
            raise VoiceDimensionError(f"{where}: 'directions' must be a non-empty mapping")
        for name, spec in directions.items():
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise VoiceDimensionError(
                    f"{where}: invalid direction name {name!r} in 'directions' "
                    f"(quote YAML booleans such as 'no'/'on')"
                )
            if not isinstance(spec, dict) or spec.get("kind") not in VALID_KINDS:
                raise VoiceDimensionError(
                    f"{where}: direction {name!r} needs a 'kind' of {sorted(VALID_KINDS)}"
                )
            opposite = spec.get("opposite")
            if opposite is None:
                continue
            back = directions.get(opposite) if isinstance(opposite, str) else None
            if not isinstance(back, dict) or back.get("opposite") != name:
                raise VoiceDimensionError(
                    f"{where}: direction {name!r} declares opposite {opposite!r}, which "
                    f"must exist in the same dimension and point back"
                )


def _direction_spec(
    dimension: str, direction: str, plugin_root: Path | None
) -> dict[str, Any]:
    vocab = load_voice_dimensions(plugin_root)
    if not isinstance(dimension, str) or dimension not in vocab:
        raise VoiceDimensionError(f"unknown dimension {dimension!r}")
    directions = vocab[dimension]["directions"]
    if not isinstance(direction, str) or direction not in directions:
        raise VoiceDimensionError(
            f"unknown direction {direction!r} for {dimension!r}; allowed: "
            f"{', '.join(directions)}"
        )
    return dict(directions[direction])


def allowed_dimensions(book_category: str, plugin_root: Path | None = None) -> list[str]:
    _check_category(book_category)
    return [
        slug
        for slug, dim in load_voice_dimensions(plugin_root).items()
        if book_category in dim["categories"]
    ]


def memoir_only_dimensions(plugin_root: Path | None = None) -> list[str]:
    """Dimensions that apply to memoir books only, derived from the vocabulary."""
    return [
        slug
        for slug, dim in load_voice_dimensions(plugin_root).items()
        if dim["categories"] == ["memoir"]
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

    if not isinstance(dimension, str) or dimension not in vocab:
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
    if not isinstance(direction, str) or direction not in dim["directions"]:
        raise VoiceDimensionError(
            f"unknown direction {direction!r} for {dimension!r}; allowed: "
            f"{', '.join(dim['directions'])}"
        )


def direction_kind(dimension: str, direction: str, plugin_root: Path | None = None) -> str:
    """Return ``"prefer"`` or ``"avoid"`` for a direction."""
    return str(_direction_spec(dimension, direction, plugin_root)["kind"])


def opposite_direction(
    dimension: str, direction: str, plugin_root: Path | None = None
) -> str | None:
    """Return the opposing direction within the same dimension, if one is defined."""
    opposite = _direction_spec(dimension, direction, plugin_root).get("opposite")
    return str(opposite) if opposite else None


def _check_category(book_category: str) -> None:
    if not isinstance(book_category, str) or book_category not in VALID_CATEGORIES:
        raise VoiceDimensionError(
            f"invalid book_category {book_category!r}; expected one of {sorted(VALID_CATEGORIES)}"
        )
