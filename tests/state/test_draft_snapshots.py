"""Draft baselines and manual-edit hunks — Epic #663 / Issue #671 (phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

import tools.db.connection as conn_mod
from tools.state import draft_snapshots as ds


@pytest.fixture(autouse=True)
def snapshots_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_dir = tmp_path / "home" / "db"
    db_dir.mkdir(parents=True)
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)
    return tmp_path / "home"


def chapter_file(tmp_path: Path, *, book="firelight", chapter="04-the-crossing",
                 category: str | None = None) -> Path:
    book_dir = tmp_path / "books" / "projects" / book
    ch = book_dir / "chapters" / chapter
    ch.mkdir(parents=True)
    fm = f'---\ntitle: "{book}"\n' + (f'book_category: "{category}"\n' if category else "") + "---\n"
    (book_dir / "README.md").write_text(fm, encoding="utf-8")
    path = ch / "draft.md"
    path.write_text("", encoding="utf-8")
    return path


BASE = (
    "The silence held the room like a held breath, and nobody dared to speak.\n\n"
    "Mara crossed the bridge without looking down.\n\n"
    "The river was loud."
)


class TestChapterRef:
    def test_extracts_book_and_chapter(self, tmp_path):
        path = chapter_file(tmp_path)
        assert ds.chapter_ref(path) == ("firelight", "04-the-crossing")

    @pytest.mark.parametrize("p", ["/tmp/notes.md", "/tmp/chapters/draft.md", "/a/b/c/readme.md"])
    def test_non_draft_paths_are_ignored(self, p):
        assert ds.chapter_ref(p) is None

    def test_series_nested_book(self, tmp_path):
        ch = tmp_path / "series" / "saga" / "firelight" / "chapters" / "01-x"
        ch.mkdir(parents=True)
        assert ds.chapter_ref(ch / "draft.md") == ("firelight", "01-x")


class TestApplyToolEdit:
    def test_write_replaces_everything(self):
        assert ds.apply_tool_edit("old", "Write", {"content": "new"}) == "new"

    def test_edit_replaces_first_occurrence(self):
        out = ds.apply_tool_edit("a b a", "Edit", {"old_string": "a", "new_string": "c"})
        assert out == "c b a"

    def test_edit_replace_all(self):
        out = ds.apply_tool_edit("a b a", "Edit",
                                 {"old_string": "a", "new_string": "c", "replace_all": True})
        assert out == "c b c"

    def test_edit_on_text_the_baseline_does_not_contain_cannot_be_applied(self):
        assert ds.apply_tool_edit("a b", "Edit", {"old_string": "zzz", "new_string": "c"}) is None

    def test_multiedit_applies_in_order_and_fails_as_a_whole(self):
        ok = ds.apply_tool_edit("a b", "MultiEdit", {"edits": [
            {"old_string": "a", "new_string": "x"}, {"old_string": "x b", "new_string": "done"}]})
        assert ok == "done"
        bad = ds.apply_tool_edit("a b", "MultiEdit", {"edits": [
            {"old_string": "a", "new_string": "x"}, {"old_string": "nope", "new_string": "y"}]})
        assert bad is None

    def test_unknown_tool_is_not_applied(self):
        assert ds.apply_tool_edit("a", "Read", {}) is None


class TestSnapshotStore:
    def test_roundtrip_outside_the_book_repo(self, snapshots_home):
        ds.write_snapshot("firelight", "04", "hello ä")
        assert ds.read_snapshot("firelight", "04") == "hello ä"
        assert str(ds.snapshot_file("firelight", "04")).startswith(str(snapshots_home / "snapshots"))

    def test_missing_snapshot_is_none(self):
        assert ds.read_snapshot("firelight", "99") is None

    def test_stale_marker_blocks_until_baseline_is_rewritten(self):
        ds.write_snapshot("firelight", "04", "x")
        ds.mark_stale("firelight", "04")
        assert ds.is_stale("firelight", "04") is True
        assert ds.read_snapshot("firelight", "04") is None
        ds.write_snapshot("firelight", "04", "fresh")
        assert ds.is_stale("firelight", "04") is False
        assert ds.read_snapshot("firelight", "04") == "fresh"

    def test_slugs_cannot_escape_the_snapshot_dir(self):
        with pytest.raises(ValueError):
            ds.snapshot_file("../evil", "04")
        with pytest.raises(ValueError):
            ds.snapshot_file("firelight", "../../x")


class TestRecordToolWrite:
    def payload(self, path: Path, tool="Edit", **tool_input):
        return {"tool_name": tool, "tool_input": {"file_path": str(path), **tool_input}}

    def test_first_write_creates_the_baseline_from_the_file(self, tmp_path):
        path = chapter_file(tmp_path)
        path.write_text(BASE, encoding="utf-8")
        ds.record_tool_write(self.payload(path, "Write", content=BASE))
        assert ds.read_snapshot("firelight", "04-the-crossing") == BASE

    def test_edit_updates_the_baseline_without_absorbing_manual_changes(self, tmp_path):
        path = chapter_file(tmp_path)
        path.write_text(BASE, encoding="utf-8")
        ds.record_tool_write(self.payload(path, "Write", content=BASE))
        # the author edits another sentence by hand ...
        manual = BASE.replace("The river was loud.", "The river roared under the planks.")
        path.write_text(manual, encoding="utf-8")
        # ... then Claude edits a different sentence through the Edit tool
        edited = manual.replace("Mara crossed", "Mara walked across")
        path.write_text(edited, encoding="utf-8")
        ds.record_tool_write(self.payload(
            path, "Edit", old_string="Mara crossed", new_string="Mara walked across"))
        baseline = ds.read_snapshot("firelight", "04-the-crossing")
        assert "Mara walked across" in baseline
        assert "The river was loud." in baseline          # the manual change is still a diff
        assert "roared" not in baseline

    def test_edit_that_does_not_fit_the_baseline_marks_it_stale(self, tmp_path):
        path = chapter_file(tmp_path)
        path.write_text(BASE, encoding="utf-8")
        ds.record_tool_write(self.payload(path, "Write", content=BASE))
        ds.record_tool_write(self.payload(
            path, "Edit", old_string="text that is not there", new_string="x"))
        assert ds.is_stale("firelight", "04-the-crossing") is True
        # a further edit must not silently re-create a baseline
        path.write_text(BASE + "\n\nmore", encoding="utf-8")
        ds.record_tool_write(self.payload(path, "Write", content=BASE + "\n\nmore"))
        assert ds.read_snapshot("firelight", "04-the-crossing") is None

    def test_memoir_books_get_no_snapshot(self, tmp_path):
        path = chapter_file(tmp_path, book="my-life", category="memoir")
        path.write_text("Anna ging.", encoding="utf-8")
        ds.record_tool_write(self.payload(path, "Write", content="Anna ging."))
        assert ds.read_snapshot("my-life", "04-the-crossing") is None

    def test_other_files_are_ignored(self, tmp_path):
        other = tmp_path / "notes.md"
        other.write_text("x", encoding="utf-8")
        ds.record_tool_write(self.payload(other, "Write", content="x"))
        assert not (ds.snapshots_dir()).exists() or not any(ds.snapshots_dir().rglob("*"))

    def test_never_raises(self, tmp_path):
        ds.record_tool_write({"tool_name": "Edit", "tool_input": None})
        ds.record_tool_write({})
        ds.record_tool_write({"tool_name": "Edit", "tool_input": {"file_path": "/nope/chapters/x/draft.md",
                                                                  "old_string": "a", "new_string": "b"}})


class TestHunks:
    def test_unchanged_text_has_no_hunks(self):
        assert ds.compute_hunks(BASE, BASE)["hunks"] == []

    def test_replaced_paragraph_is_a_hunk_with_before_and_after(self):
        current = BASE.replace(
            "The silence held the room like a held breath, and nobody dared to speak.",
            "Nobody spoke, and the silence pressed down on the room until it hurt.",
        )
        result = ds.compute_hunks(BASE, current)
        assert result["total"] == 1
        hunk = result["hunks"][0]
        assert hunk["kind"] == "replace"
        assert hunk["before"].startswith("The silence held")
        assert hunk["after"].startswith("Nobody spoke")
        assert hunk["changed_words"] >= 4

    def test_changes_up_to_three_words_are_ignored(self):
        current = BASE.replace("The river was loud.", "The river was quite loud.")
        result = ds.compute_hunks(BASE, current)
        assert result["hunks"] == []
        assert result["ignored_small"] == 1

    def test_four_word_change_counts(self):
        current = BASE.replace("The river was loud.", "The river was very loud and cold tonight.")
        assert ds.compute_hunks(BASE, current)["total"] == 1

    def test_whitespace_and_punctuation_only_changes_are_ignored(self):
        current = BASE.replace("The river was loud.", "The  river was loud!")
        result = ds.compute_hunks(BASE, current)
        assert result["hunks"] == []

    def test_review_comment_blocks_are_not_edits(self):
        current = BASE + "\n\nMarkus: das ist zu verschwurbelt, bitte kürzer und klarer formulieren"
        result = ds.compute_hunks(BASE, current, review_handle="Markus")
        assert result["hunks"] == []

    def test_inserted_paragraph_is_an_insert_hunk(self):
        new = "She had not slept in two days and the bridge swayed beneath her."
        current = BASE.replace("The river was loud.", f"{new}\n\nThe river was loud.")
        hunk = ds.compute_hunks(BASE, current)["hunks"][0]
        assert hunk["kind"] == "insert"
        assert hunk["before"] == ""
        assert hunk["after"] == new

    def test_deleted_paragraph_is_a_delete_hunk(self):
        current = BASE.replace("Mara crossed the bridge without looking down.\n\n", "")
        hunk = ds.compute_hunks(BASE, current)["hunks"][0]
        assert hunk["kind"] == "delete"
        assert hunk["after"] == ""

    def test_hunk_list_is_capped_and_reports_truncation(self):
        base = "\n\n".join(f"Paragraph number {i} stays as it is." for i in range(30))
        cur = "\n\n".join(f"Paragraph number {i} was rewritten completely by the author today." for i in range(30))
        result = ds.compute_hunks(base, cur, max_hunks=20)
        assert result["total"] == 30
        assert len(result["hunks"]) == 20
        assert result["truncated"] is True

    def test_long_texts_are_clipped(self):
        long_new = " ".join(["word"] * 3000)
        result = ds.compute_hunks("short.", long_new, max_chars=500)
        assert len(result["hunks"][0]["after"]) <= 520

    def test_indexes_are_sequential_and_stable(self):
        base = "A one two three four five.\n\nB one two three four five.\n\nC one two three four five."
        cur = "A six seven eight nine ten.\n\nB one two three four five.\n\nC six seven eight nine ten."
        hunks = ds.compute_hunks(base, cur)["hunks"]
        assert [h["index"] for h in hunks] == [1, 2]
