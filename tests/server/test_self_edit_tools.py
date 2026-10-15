"""MCP tools and hook for manual-edit capture — Epic #663 / Issue #671."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import routers._app as _app
import tools.db.connection as conn_mod
from routers.feedback import get_self_edit_hunks, refresh_draft_baseline
from tools.state import draft_snapshots as ds

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent

BASE = (
    "The silence held the room like a held breath, and nobody dared to speak.\n\n"
    "Mara crossed the bridge without looking down.\n\n"
    "The river was loud."
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content_root = tmp_path / "books"
    chapters = {}
    for slug, category in (("firelight", "fiction"), ("my-life", "memoir")):
        ch = content_root / "projects" / slug / "chapters" / "01-x"
        ch.mkdir(parents=True)
        (content_root / "projects" / slug / "README.md").write_text(
            f'---\ntitle: "{slug}"\nauthor: "ethan-cole"\nbook_category: "{category}"\n---\n',
            encoding="utf-8",
        )
        (ch / "draft.md").write_text(BASE, encoding="utf-8")
        chapters[slug] = ch / "draft.md"

    config = {"paths": {"content_root": str(content_root), "authors_root": str(tmp_path / "a")},
              "defaults": {"review_handle": "Markus"}}
    monkeypatch.setattr(_app, "load_config", lambda: config)
    books = {
        "firelight": {"author": "ethan-cole", "book_category": "fiction", "genres": ["drama"],
                      "chapters_data": {"01-x": {"number": 1}}, "people": {}},
        "my-life": {"author": "ethan-cole", "book_category": "memoir", "genres": [],
                    "chapters_data": {"01-x": {"number": 1}}, "people": {}},
    }
    monkeypatch.setattr(_app._cache, "get", lambda: {"books": books, "authors": {}})
    db_dir = tmp_path / "home" / "db"
    db_dir.mkdir(parents=True)
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)
    return {"chapters": chapters, "home": tmp_path / "home", "content_root": content_root}


def _call(fn, *a, **k) -> dict:
    return json.loads(fn(*a, **k))


class TestGetSelfEditHunks:
    def test_no_baseline_is_reported(self, env):
        result = _call(get_self_edit_hunks, "firelight", "01-x")
        assert result["status"] == "no_baseline"

    def test_returns_the_authors_edits(self, env):
        draft = env["chapters"]["firelight"]
        ds.write_snapshot("firelight", "01-x", BASE)
        draft.write_text(
            BASE.replace("The river was loud.",
                         "The river roared under the planks until she stopped hearing it."),
            encoding="utf-8",
        )
        result = _call(get_self_edit_hunks, "firelight", "01-x")
        assert result["status"] == "ok"
        assert result["total"] == 1
        assert result["hunks"][0]["before"] == "The river was loud."
        assert "roared" in result["hunks"][0]["after"]

    def test_small_edits_and_review_comments_are_not_hunks(self, env):
        draft = env["chapters"]["firelight"]
        ds.write_snapshot("firelight", "01-x", BASE)
        draft.write_text(
            BASE.replace("loud.", "loud!") + "\n\nMarkus: bitte kürzer und klarer formulieren hier",
            encoding="utf-8",
        )
        result = _call(get_self_edit_hunks, "firelight", "01-x")
        assert result["status"] == "ok" and result["hunks"] == []

    def test_stale_baseline_is_reported(self, env):
        ds.mark_stale("firelight", "01-x")
        assert _call(get_self_edit_hunks, "firelight", "01-x")["status"] == "stale"

    def test_memoir_is_not_supported_and_reads_nothing(self, env):
        result = _call(get_self_edit_hunks, "my-life", "01-x")
        assert result["status"] == "memoir_unsupported"
        assert "hunks" not in result

    def test_unknown_book_chapter_and_slug_are_errors(self, env):
        assert "error" in _call(get_self_edit_hunks, "ghost", "01-x")
        assert "error" in _call(get_self_edit_hunks, "firelight", "99-nope")
        assert "error" in _call(get_self_edit_hunks, "firelight", "../x")


class TestPagingAndPrivacy:
    def test_offset_pages_through_hunks(self, env):
        base = "\n\n".join(f"Paragraph number {i} stays as it is." for i in range(30))
        cur = "\n\n".join(f"Paragraph number {i} was rewritten completely by the author today."
                          for i in range(30))
        env["chapters"]["firelight"].write_text(cur, encoding="utf-8")
        ds.write_snapshot("firelight", "01-x", base)
        first = _call(get_self_edit_hunks, "firelight", "01-x")
        assert len(first["hunks"]) == 20 and first["truncated"] is True
        second = _call(get_self_edit_hunks, "firelight", "01-x", offset=20)
        assert len(second["hunks"]) == 10 and second["truncated"] is False

    @pytest.mark.parametrize("bad", [-1, True, "2"])
    def test_bad_offset_is_an_error(self, env, bad):
        ds.write_snapshot("firelight", "01-x", BASE)
        assert "error" in _call(get_self_edit_hunks, "firelight", "01-x", offset=bad)

    def test_memoir_call_removes_leftover_baselines(self, env):
        ds.write_snapshot("my-life", "01-x", "old copy of a memoir chapter")
        assert _call(get_self_edit_hunks, "my-life", "01-x")["status"] == "memoir_unsupported"
        assert ds.read_snapshot("my-life", "01-x") is None

    def test_umlaut_chapter_slug_passes_the_tools(self, env, monkeypatch):
        slug = "01-der-fuchs-zählen"
        ch = env["chapters"]["firelight"].parent.parent / slug
        ch.mkdir()
        (ch / "draft.md").write_text(BASE, encoding="utf-8")
        books = {"firelight": {"author": "ethan-cole", "book_category": "fiction", "genres": [],
                               "chapters_data": {slug: {"number": 2}}, "people": {}}}
        monkeypatch.setattr(_app._cache, "get", lambda: {"books": books, "authors": {}})
        assert _call(refresh_draft_baseline, "firelight", slug)["refreshed"] is True
        assert _call(get_self_edit_hunks, "firelight", slug)["status"] == "ok"


class TestRefreshDraftBaseline:
    def test_stores_the_current_draft_and_clears_stale(self, env):
        ds.mark_stale("firelight", "01-x")
        result = _call(refresh_draft_baseline, "firelight", "01-x")
        assert result["refreshed"] is True
        assert ds.read_snapshot("firelight", "01-x") == BASE
        assert ds.is_stale("firelight", "01-x") is False

    def test_after_refresh_the_same_edits_are_not_reported_again(self, env):
        draft = env["chapters"]["firelight"]
        ds.write_snapshot("firelight", "01-x", BASE)
        draft.write_text(BASE.replace("Mara crossed the bridge without looking down.",
                                      "Mara did not look down while she crossed the swaying bridge."),
                         encoding="utf-8")
        assert _call(get_self_edit_hunks, "firelight", "01-x")["total"] == 1
        _call(refresh_draft_baseline, "firelight", "01-x")
        assert _call(get_self_edit_hunks, "firelight", "01-x")["total"] == 0

    def test_memoir_never_gets_a_baseline(self, env):
        result = _call(refresh_draft_baseline, "my-life", "01-x")
        assert result["status"] == "memoir_unsupported"
        assert ds.read_snapshot("my-life", "01-x") is None


class TestHookScript:
    def run_hook(self, env, payload: dict) -> subprocess.CompletedProcess:
        import os

        home = env["home"]
        (home / ".storyforge").mkdir(exist_ok=True)
        (home / ".storyforge" / "config.yaml").write_text(
            f"paths:\n  content_root: {env['content_root']}\n", encoding="utf-8")
        envs = {**os.environ, "STORYFORGE_DB_DIR": str(home / "db"), "HOME": str(home),
                "USERPROFILE": str(home), "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)}
        return subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "hooks" / "snapshot_draft.py")],
            input=json.dumps(payload), capture_output=True, text=True, env=envs, timeout=30,
        )

    def test_hook_writes_the_baseline_and_never_blocks(self, env):
        draft = env["chapters"]["firelight"]
        result = self.run_hook(env, {
            "tool_name": "Write",
            "tool_input": {"file_path": str(draft), "content": BASE},
        })
        assert result.returncode == 0
        assert result.stdout == "" and result.stderr == ""
        snapshot = env["home"] / "snapshots" / "firelight" / "01-x.md"
        assert snapshot.read_text(encoding="utf-8") == BASE

    def test_hook_ignores_garbage_input(self, env):
        import os

        envs = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)}
        for raw in ("", "not json", "[]"):
            proc = subprocess.run(
                [sys.executable, str(PLUGIN_ROOT / "hooks" / "snapshot_draft.py")],
                input=raw, capture_output=True, text=True, env=envs, timeout=30,
            )
            assert proc.returncode == 0

    def test_hook_is_registered_for_write_edit_multiedit(self):
        hooks = json.loads((PLUGIN_ROOT / ".claude-plugin" / "hooks.json").read_text(encoding="utf-8"))
        post = hooks["hooks"]["PostToolUse"]
        commands = [h["command"] for block in post for h in block["hooks"]]
        assert any("snapshot_draft.py" in c for c in commands)
        for block in post:
            if any("snapshot_draft.py" in h["command"] for h in block["hooks"]):
                assert block["matcher"] == "Write|Edit|MultiEdit"
