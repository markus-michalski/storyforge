"""Tests for the per-file idea state management system (Issue #8).

Tests cover:
- 5 new MCP tools: create_idea, list_ideas, get_idea, update_idea, promote_idea
- New _scan_ideas_dir() indexer helper
- Filtering by status and genre
- Promotion workflow
- Frontmatter updates
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.state.indexer import _scan_ideas_dir
from tools.state.parsers import parse_frontmatter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    """Provide a temporary content root directory."""
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path):
    """Patch load_config in both server and indexer modules to point at tmp_path."""
    fake_config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en", "book_type": "novel"},
    }

    import routers._app as server_mod

    with patch.object(server_mod, "load_config", return_value=fake_config), \
         patch.object(server_mod, "get_content_root", return_value=content_root):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    """Return the storyforge server module with config mocked."""
    import server as server_mod
    return server_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_idea_file(
    ideas_dir: Path,
    slug: str,
    title: str,
    status: str = "raw",
    genres: list[str] | None = None,
    logline: str = "",
    body: str = "",
    promoted_to: str | None = None,
) -> Path:
    """Write a minimal idea file for tests."""
    ideas_dir.mkdir(parents=True, exist_ok=True)
    path = ideas_dir / f"{slug}.md"
    genres_yaml = "[" + ", ".join(f'"{g}"' for g in (genres or [])) + "]"
    promoted_line = f'"{promoted_to}"' if promoted_to else "null"
    content = (
        "---\n"
        f'title: "{title}"\n'
        f'slug: "{slug}"\n'
        f'status: "{status}"\n'
        f"genres: {genres_yaml}\n"
        f'logline: "{logline}"\n'
        f"created: {date.today().isoformat()}\n"
        f"last_touched: {date.today().isoformat()}\n"
        f"promoted_to: {promoted_line}\n"
        "---\n\n"
        f"{body}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# create_idea
# ---------------------------------------------------------------------------


class TestCreateIdea:
    def test_creates_file_with_frontmatter(self, server_module, content_root: Path):
        result = json.loads(
            server_module.create_idea(
                title="The Glass Clockmaker",
                genres="fantasy,mystery",
                logline="A clockmaker discovers his creations predict deaths.",
                concept="A dark tale of horology and fate.",
            )
        )

        assert result["slug"] == "the-glass-clockmaker"
        assert result["title"] == "The Glass Clockmaker"
        ideas_file = content_root / "ideas" / "the-glass-clockmaker.md"
        assert ideas_file.exists()
        assert result["file_path"] == str(ideas_file)

        text = ideas_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "The Glass Clockmaker"
        assert meta["slug"] == "the-glass-clockmaker"
        assert meta["status"] == "raw"
        assert meta["genres"] == ["fantasy", "mystery"]
        assert meta["logline"] == "A clockmaker discovers his creations predict deaths."
        assert meta["promoted_to"] is None
        assert "horology" in body

    def test_creates_ideas_dir_if_missing(self, server_module, content_root: Path):
        assert not (content_root / "ideas").exists()
        server_module.create_idea(title="Spark")
        assert (content_root / "ideas").is_dir()

    def test_empty_genres_and_logline_defaults(self, server_module, content_root: Path):
        server_module.create_idea(title="Bare Idea")
        path = content_root / "ideas" / "bare-idea.md"
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        assert meta["genres"] == []
        assert meta["logline"] == ""

    def test_slug_is_unique_stable(self, server_module, content_root: Path):
        result = json.loads(server_module.create_idea(title="Hello World"))
        assert result["slug"] == "hello-world"


# ---------------------------------------------------------------------------
# list_ideas
# ---------------------------------------------------------------------------


class TestListIdeas:
    def test_lists_all_ideas(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "one", "One", status="raw")
        _write_idea_file(ideas_dir, "two", "Two", status="explored")

        result = json.loads(server_module.list_ideas())
        assert result["count"] == 2
        slugs = {i["slug"] for i in result["ideas"]}
        assert slugs == {"one", "two"}

    def test_empty_when_no_ideas(self, server_module):
        result = json.loads(server_module.list_ideas())
        assert result["count"] == 0
        assert result["ideas"] == []

    def test_filter_by_status(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "raw-one", "Raw One", status="raw")
        _write_idea_file(ideas_dir, "raw-two", "Raw Two", status="raw")
        _write_idea_file(ideas_dir, "explored", "Explored", status="explored")

        result = json.loads(server_module.list_ideas(status="raw"))
        assert result["count"] == 2
        assert all(i["status"] == "raw" for i in result["ideas"])

    def test_filter_by_genre(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "a", "A", genres=["fantasy", "mystery"])
        _write_idea_file(ideas_dir, "b", "B", genres=["sci-fi"])
        _write_idea_file(ideas_dir, "c", "C", genres=["fantasy"])

        result = json.loads(server_module.list_ideas(genre="fantasy"))
        assert result["count"] == 2
        slugs = {i["slug"] for i in result["ideas"]}
        assert slugs == {"a", "c"}

    def test_excludes_archive(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        archive_dir = ideas_dir / "_archive"
        _write_idea_file(ideas_dir, "active", "Active")
        _write_idea_file(archive_dir, "shelved", "Shelved", status="shelved")

        result = json.loads(server_module.list_ideas())
        slugs = {i["slug"] for i in result["ideas"]}
        assert slugs == {"active"}


# ---------------------------------------------------------------------------
# get_idea
# ---------------------------------------------------------------------------


class TestGetIdea:
    def test_returns_full_idea(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(
            ideas_dir, "clockmaker", "The Clockmaker",
            status="explored", genres=["fantasy"],
            logline="Clocks predict deaths.",
            body="A rich body describing the concept.",
        )

        result = json.loads(server_module.get_idea("clockmaker"))
        assert result["slug"] == "clockmaker"
        assert result["title"] == "The Clockmaker"
        assert result["status"] == "explored"
        assert result["genres"] == ["fantasy"]
        assert result["logline"] == "Clocks predict deaths."
        assert "rich body" in result["body"]

    def test_unknown_slug_returns_error(self, server_module):
        result = json.loads(server_module.get_idea("does-not-exist"))
        assert "error" in result


# ---------------------------------------------------------------------------
# update_idea
# ---------------------------------------------------------------------------


class TestUpdateIdea:
    def test_updates_status(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "x", "X", status="raw")

        result = json.loads(server_module.update_idea("x", "status", "explored"))
        assert result["success"] is True

        meta, _ = parse_frontmatter(
            (ideas_dir / "x.md").read_text(encoding="utf-8")
        )
        assert meta["status"] == "explored"

    def test_updates_logline(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "x", "X", logline="old")

        server_module.update_idea("x", "logline", "new logline")
        meta, _ = parse_frontmatter(
            (ideas_dir / "x.md").read_text(encoding="utf-8")
        )
        assert meta["logline"] == "new logline"

    def test_preserves_body(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "x", "X", body="Body stays intact.")

        server_module.update_idea("x", "status", "developed")
        _, body = parse_frontmatter((ideas_dir / "x.md").read_text(encoding="utf-8"))
        assert "Body stays intact." in body

    def test_unknown_slug(self, server_module):
        result = json.loads(server_module.update_idea("nope", "status", "raw"))
        assert "error" in result


# ---------------------------------------------------------------------------
# promote_idea
# ---------------------------------------------------------------------------


class TestPromoteIdea:
    def test_sets_status_and_promoted_to(self, server_module, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "seed", "Seed", status="ready")

        result = json.loads(server_module.promote_idea("seed", "my-book"))
        assert result["success"] is True

        meta, _ = parse_frontmatter(
            (ideas_dir / "seed.md").read_text(encoding="utf-8")
        )
        assert meta["status"] == "promoted"
        assert meta["promoted_to"] == "my-book"

    def test_unknown_slug(self, server_module):
        result = json.loads(server_module.promote_idea("nope", "book"))
        assert "error" in result


# ---------------------------------------------------------------------------
# _scan_ideas_dir (indexer)
# ---------------------------------------------------------------------------


class TestScanIdeasDir:
    def test_scans_all_idea_files(self, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "one", "One", status="raw")
        _write_idea_file(ideas_dir, "two", "Two", status="explored", genres=["fantasy"])

        result = _scan_ideas_dir(ideas_dir)
        assert len(result) == 2
        by_slug = {i["slug"]: i for i in result}
        assert by_slug["one"]["status"] == "raw"
        assert by_slug["two"]["genres"] == ["fantasy"]

    def test_ignores_archive_subdir(self, content_root: Path):
        ideas_dir = content_root / "ideas"
        _write_idea_file(ideas_dir, "active", "Active")
        _write_idea_file(ideas_dir / "_archive", "shelved", "Shelved", status="shelved")

        result = _scan_ideas_dir(ideas_dir)
        slugs = {i["slug"] for i in result}
        assert slugs == {"active"}

    def test_returns_empty_list_for_missing_dir(self, content_root: Path):
        missing = content_root / "nonexistent"
        result = _scan_ideas_dir(missing)
        assert result == []

    def test_ignores_non_md_files(self, content_root: Path):
        ideas_dir = content_root / "ideas"
        ideas_dir.mkdir()
        (ideas_dir / "README.txt").write_text("not an idea", encoding="utf-8")
        _write_idea_file(ideas_dir, "valid", "Valid")

        result = _scan_ideas_dir(ideas_dir)
        assert len(result) == 1
        assert result[0]["slug"] == "valid"
