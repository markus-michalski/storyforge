"""Per-source loaders for chapter_writing_brief (Issue #121).

Each loader exposes a small, independently-testable function (or a
handful of them) that the orchestrator in
``tools/state/chapter_writing_brief.py`` calls once and dispatches the
result into the brief.

Loaders never reach beyond the book root or the plugin root, never call
each other, and surface failures as exceptions — the orchestrator wraps
them in a try/except recorder so a single failure cannot break the
whole brief.
"""
