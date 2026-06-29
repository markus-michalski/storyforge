"""Tests for get_author() — vocabulary.md must NOT appear in response (Issue #339).

PR #303 migrated all vocabulary data to author_discoveries SQLite. The get_author()
read path still loaded vocabulary.md raw text, creating a ~13K duplicate payload
on every call. After the fix, get_author() must omit the "vocabulary" key entirely;
donts and style_principles are already in writing_discoveries.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import routers._app as _app
from routers.authors import get_author


@pytest.fixture
def authors_root(tmp_path: Path) -> Path:
    root = tmp_path / "authors"
    root.mkdir()
    return root


def _make_author_dir(authors_root: Path, slug: str, with_vocabulary_md: bool = True) -> Path:
    author_dir = authors_root / slug
    author_dir.mkdir(parents=True)
    (author_dir / "profile.md").write_text(
        "---\nname: Test Author\nprimary_genres: []\ntone: []\n---\n\n"
        "## Voice\nDistinctive voice.\n\n## Writing Discoveries\n(managed by DB)\n",
        encoding="utf-8",
    )
    if with_vocabulary_md:
        (author_dir / "vocabulary.md").write_text(
            "# Vocabulary\n\n## Banned Words\n- egregious\n- utilize\n",
            encoding="utf-8",
        )
    return author_dir


def _fake_state(slug: str, authors_root: Path) -> dict:
    """Build a minimal state dict with one author entry."""
    return {
        "authors": {
            slug: {
                "slug": slug,
                "name": "Test Author",
                "style_notes": "## Voice\nDistinctive voice.",
                "primary_genres": [],
                "tone": [],
            }
        },
        "books": {},
        "series": {},
    }


def _mock_discoveries():
    """Return empty discoveries list (no DB entries needed for these tests)."""
    return []


class TestGetAuthorVocabularyRemoved:
    def test_get_author_does_not_include_vocabulary_key(self, authors_root: Path):
        """get_author() must not include a 'vocabulary' key — data is in writing_discoveries."""
        _make_author_dir(authors_root, "test-author", with_vocabulary_md=True)

        cfg = {"paths": {"authors_root": str(authors_root), "content_root": str(authors_root.parent)}}

        with (
            patch.object(_app, "load_config", return_value=cfg),
            patch.object(_app._cache, "get", return_value=_fake_state("test-author", authors_root)),
            patch("routers.authors.open_authors_db", return_value=MagicMock()),
            patch("routers.authors.get_discoveries", return_value=_mock_discoveries()),
            patch("routers.authors.discoveries_as_writing_discoveries", return_value={}),
        ):
            result = json.loads(get_author("test-author"))

        assert "vocabulary" not in result, (
            "get_author() still returns raw vocabulary.md text — remove the vocab_path "
            "load block from routers/authors.py (Issue #339)"
        )

    def test_get_author_without_vocabulary_md_works(self, authors_root: Path):
        """get_author() must work cleanly when vocabulary.md does not exist."""
        _make_author_dir(authors_root, "test-author", with_vocabulary_md=False)

        cfg = {"paths": {"authors_root": str(authors_root), "content_root": str(authors_root.parent)}}

        with (
            patch.object(_app, "load_config", return_value=cfg),
            patch.object(_app._cache, "get", return_value=_fake_state("test-author", authors_root)),
            patch("routers.authors.open_authors_db", return_value=MagicMock()),
            patch("routers.authors.get_discoveries", return_value=_mock_discoveries()),
            patch("routers.authors.discoveries_as_writing_discoveries", return_value={}),
        ):
            result = json.loads(get_author("test-author"))

        assert "error" not in result
        assert result["slug"] == "test-author"

    def test_get_author_writing_discoveries_present(self, authors_root: Path):
        """writing_discoveries must still be present (from DB) after vocabulary removal."""
        _make_author_dir(authors_root, "test-author", with_vocabulary_md=True)

        cfg = {"paths": {"authors_root": str(authors_root), "content_root": str(authors_root.parent)}}
        discoveries = {"donts": ["egregious", "utilize"], "style_principles": [], "recurring_tics": []}

        with (
            patch.object(_app, "load_config", return_value=cfg),
            patch.object(_app._cache, "get", return_value=_fake_state("test-author", authors_root)),
            patch("routers.authors.open_authors_db", return_value=MagicMock()),
            patch("routers.authors.get_discoveries", return_value=_mock_discoveries()),
            patch("routers.authors.discoveries_as_writing_discoveries", return_value=discoveries),
        ):
            result = json.loads(get_author("test-author"))

        assert "writing_discoveries" in result
        assert result["writing_discoveries"]["donts"] == ["egregious", "utilize"]

    def test_get_author_style_notes_present(self, authors_root: Path):
        """style_notes must still be present (from profile.md body via state cache)."""
        _make_author_dir(authors_root, "test-author", with_vocabulary_md=True)

        cfg = {"paths": {"authors_root": str(authors_root), "content_root": str(authors_root.parent)}}

        with (
            patch.object(_app, "load_config", return_value=cfg),
            patch.object(_app._cache, "get", return_value=_fake_state("test-author", authors_root)),
            patch("routers.authors.open_authors_db", return_value=MagicMock()),
            patch("routers.authors.get_discoveries", return_value=_mock_discoveries()),
            patch("routers.authors.discoveries_as_writing_discoveries", return_value={}),
        ):
            result = json.loads(get_author("test-author"))

        assert "style_notes" in result
