"""Detect names of real people in free text — Epic #663.

Used wherever text derived from a memoir book is about to reach a store that
is read across books (review feedback rules, author discoveries).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Name parts that carry no identity: relationship terms and name particles.
_NOT_NAMES = frozenset({
    "mom", "mum", "mama", "mommy", "mother", "dad", "papa", "daddy", "father",
    "oma", "opa", "omi", "mutti", "vati", "uncle", "aunt", "auntie", "onkel", "tante",
    "grandma", "grandpa", "sister", "brother", "schwester", "bruder",
    "de", "la", "le", "van", "von", "der", "den", "di", "da", "du", "el", "al",
})


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[\W_]+", _fold(text)) if t]


def _person_tokens(people: dict[str, Any]) -> set[str]:
    """Identity-bearing name parts of the real people in a memoir book."""
    found: set[str] = set()
    for key, person in (people or {}).items():
        sources = [str(person.get("name") or ""), str(person.get("real_name") or ""),
                   str(person.get("slug") or key)]
        for source in sources:
            found.update(t for t in _tokens(source) if len(t) >= 2 and t not in _NOT_NAMES)
    return found


def person_name_hit(text: str, people: dict[str, Any]) -> str | None:
    """Return the first name token of ``people`` found in ``text``, else None."""
    names = _person_tokens(people)
    for token in _tokens(text):
        if token in names:
            return token
        for suffix in ("s", "es"):
            if token.endswith(suffix) and token[: -len(suffix)] in names:
                return token[: -len(suffix)]
    return None
