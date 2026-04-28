"""Banned-phrase aggregator for the chapter-writing brief (Issue #121).

Collects up to 50 deduplicated banned-phrase entries from three
sources, in priority order:

1. Book CLAUDE.md ``## Rules`` with backticked phrases (block severity).
2. Author ``vocabulary.md`` (block severity).
3. Global anti-AI tells from ``reference/craft/anti-ai-patterns.md``
   (warn severity).

Each entry is ``{"phrase": str, "source": str, "severity": str}``.
"""

from __future__ import annotations

from pathlib import Path


def collect_banned_phrases(
    book_root: Path, plugin_root: Path, *, cap: int = 50,
) -> list[dict[str, str]]:
    """Return up to ``cap`` deduplicated banned-phrase entries.

    Imports are lazy so the loader stays usable even when the optional
    banlist-loader chain is unavailable (tests that monkey-patch
    sub-modules, partial installs).
    """
    # ``manuscript_checker`` exposes the same private helpers the hook
    # uses; stay consistent with the linter's view of the rules.
    from tools.analysis.manuscript_checker import (
        _read_book_rules,
        _extract_patterns_from_rule,
    )
    from tools.banlist_loader import (
        author_slug_from_book,
        load_author_vocab,
        load_global_ai_tells,
    )

    seen: set[str] = set()
    out: list[dict[str, str]] = []

    for rule in _read_book_rules(book_root):
        for label, _pattern in _extract_patterns_from_rule(rule):
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "phrase": label,
                "source": "book CLAUDE.md ## Rules",
                "severity": "block",
            })

    author_slug = author_slug_from_book(book_root)
    if author_slug:
        # ``load_author_vocab`` accepts a ``storyforge_home`` override
        # so tests can redirect away from ``~/.storyforge``; production
        # uses the default home directory.
        try:
            patterns = load_author_vocab(author_slug)
        except Exception:  # pylint: disable=broad-except
            patterns = []
        for p in patterns:
            key = p.label.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "phrase": p.label,
                "source": "author vocabulary.md",
                "severity": p.severity,
            })

    try:
        global_tells = load_global_ai_tells(plugin_root)
    except Exception:  # pylint: disable=broad-except
        global_tells = []
    for p in global_tells:
        key = p.label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "phrase": p.label,
            "source": "anti-ai-patterns.md",
            "severity": p.severity,
        })
        if len(out) >= cap:
            break
    return out


__all__ = ["collect_banned_phrases"]
