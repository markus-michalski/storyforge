"""Server-level smoke test for ``analyze_plot_logic`` MCP tool — Issue #150.

The deterministic logic is covered exhaustively in
``tests/analysis/test_plot_logic.py``. This file checks only the
MCP-tool envelope: argument plumbing, error JSON, and slug
normalization.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path):
    fake_config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en", "book_type": "novel"},
    }

    import routers._app as server_mod
    from tools.state import indexer as indexer_mod

    fake_state_path = content_root / "_cache" / "state.json"

    with (
        patch.object(server_mod, "load_config", return_value=fake_config),
        patch.object(server_mod, "get_content_root", return_value=content_root),
        patch.object(indexer_mod, "load_config", return_value=fake_config),
        patch.object(indexer_mod, "STATE_PATH", fake_state_path),
        patch.object(indexer_mod, "CACHE_DIR", fake_state_path.parent),
    ):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    import server as server_mod

    return server_mod


def _write_minimal_book(content_root: Path, slug: str = "demo") -> Path:
    project = content_root / "projects" / slug
    project.mkdir(parents=True)
    (project / "README.md").write_text(
        f'---\ntitle: "Demo"\nslug: "{slug}"\nbook_category: fiction\n---\n# Demo\n',
        encoding="utf-8",
    )
    (project / "plot").mkdir()
    (project / "chapters").mkdir()
    return project


class TestAnalyzePlotLogicTool:
    def test_returns_pass_for_book_with_no_data(self, server_module, content_root: Path):
        _write_minimal_book(content_root)
        result = json.loads(server_module.analyze_plot_logic("demo"))
        assert result["gate"]["status"] == "PASS"
        assert result["book_slug"] == "demo"
        assert result["scope"] == "manuscript"
        assert "knowledge_index" in result
        assert "findings" in result

    def test_book_slug_field_matches_input(self, server_module, content_root: Path):
        # Edge: project path may differ from input slug in real configs.
        # The wrapper must always echo back the input slug.
        _write_minimal_book(content_root, slug="firelight")
        result = json.loads(server_module.analyze_plot_logic("firelight"))
        assert result["book_slug"] == "firelight"

    def test_returns_error_for_missing_book(self, server_module):
        result = json.loads(server_module.analyze_plot_logic("does-not-exist"))
        assert "error" in result

    def test_chapter_scope_without_slug_returns_error(self, server_module, content_root: Path):
        _write_minimal_book(content_root)
        result = json.loads(server_module.analyze_plot_logic("demo", scope="chapter"))
        assert "error" in result
        assert "chapter_slug" in result["error"]

    def test_invalid_scope_returns_error(self, server_module, content_root: Path):
        _write_minimal_book(content_root)
        result = json.loads(server_module.analyze_plot_logic("demo", scope="bogus"))
        assert "error" in result

    def test_finds_causality_inversion_end_to_end(self, server_module, content_root: Path):
        project = _write_minimal_book(content_root)
        (project / "plot" / "timeline.md").write_text(
            textwrap.dedent(
                """\
                # Plot Timeline

                ## Anchor

                | Story Start | Real Date | DoW | Notes |
                |---|---|---|---|
                | Day 1 | Aug 3, 2026 | Monday | — |

                ## Event Calendar

                | Story Day | Real Date | Day of Week | Chapter | Location | Key Events | Characters |
                |---|---|---|---|---|---|---|
                | Day 1 | Aug 3, 2026 | Monday | Ch 01 | Cottage | Setup | Sarah |
                | Day 5 | Aug 7, 2026 | Friday | Ch 02 | Forest | Confession | Sarah, Tom |
                """
            ),
            encoding="utf-8",
        )
        (project / "plot" / "canon-log.md").write_text(
            textwrap.dedent(
                """\
                # Canon Log

                ## Established Facts

                ### Plot Facts

                | Fact | Established In | Status | Notes |
                |---|---|---|---|
                | Tom confesses everything | Ch 02 | ACTIVE | First confession |
                """
            ),
            encoding="utf-8",
        )
        ch1 = project / "chapters" / "01-setup"
        ch1.mkdir(parents=True)
        (ch1 / "README.md").write_text("# Ch 1\n", encoding="utf-8")
        (ch1 / "draft.md").write_text("Sarah remembered the confession all morning.\n", encoding="utf-8")
        ch2 = project / "chapters" / "02-confession"
        ch2.mkdir(parents=True)
        (ch2 / "README.md").write_text("# Ch 2\n", encoding="utf-8")
        (ch2 / "draft.md").write_text("Tom confessed.\n", encoding="utf-8")

        result = json.loads(server_module.analyze_plot_logic("demo"))
        assert result["gate"]["status"] == "FAIL"
        assert any(f["category"] == "causality_inversion" for f in result["findings"])
