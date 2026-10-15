"""Draft baselines and manual-edit hunks — Epic #663 / Issue #671 (phase 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.db.connection as conn_mod
import tools.shared.config as config_mod
from tools.state import draft_snapshots as ds


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_dir = tmp_path / "home" / "db"
    db_dir.mkdir(parents=True)
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)
    monkeypatch.setattr(
        config_mod, "load_config",
        lambda: {"paths": {"content_root": str(tmp_path / "books"), "authors_root": str(tmp_path / "a")},
                 "defaults": {"review_handle": "Markus"}},
    )
    monkeypatch.delenv("STORYFORGE_SNAPSHOT_DIR", raising=False)
    return tmp_path / "home"


def chapter_file(tmp_path: Path, *, book="firelight", chapter="04-the-crossing",
                 readme: str | None = None, category: str | None = None) -> Path:
    book_dir = tmp_path / "books" / "projects" / book
    ch = book_dir / "chapters" / chapter
    ch.mkdir(parents=True, exist_ok=True)
    if readme is None:
        readme = f'---\ntitle: "{book}"\n' + (f'book_category: "{category}"\n' if category else "") + "---\n"
    if readme != "<none>":
        (book_dir / "README.md").write_text(readme, encoding="utf-8")
    path = ch / "draft.md"
    path.write_text("", encoding="utf-8")
    return path


BASE = (
    "The silence held the room like a held breath, and nobody dared to speak.\n\n"
    "Mara crossed the bridge without looking down.\n\n"
    "The river was loud."
)


def payload(path: Path, tool="Edit", response: dict | None = None, **tool_input) -> dict:
    out = {"tool_name": tool, "tool_input": {"file_path": str(path), **tool_input}}
    if response is not None:
        out["tool_response"] = response
    return out


class TestChapterRef:
    def test_extracts_book_and_chapter(self, tmp_path):
        assert ds.chapter_ref(chapter_file(tmp_path)) == ("firelight", "04-the-crossing")

    @pytest.mark.parametrize("p", ["/tmp/notes.md", "/tmp/chapters/draft.md", "/a/b/c/readme.md"])
    def test_non_draft_paths_are_ignored(self, p):
        assert ds.chapter_ref(p) is None

    def test_series_nested_book(self, tmp_path):
        ch = tmp_path / "series" / "saga" / "firelight" / "chapters" / "01-x"
        ch.mkdir(parents=True)
        assert ds.chapter_ref(ch / "draft.md") == ("firelight", "01-x")


class TestSnapshotStore:
    def test_roundtrip_outside_the_book_repo(self, home):
        ds.write_snapshot("firelight", "04", "hello ä")
        assert ds.read_snapshot("firelight", "04") == "hello ä"
        assert str(ds.snapshot_file("firelight", "04")).startswith(str(home / "snapshots"))

    def test_override_directory(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORYFORGE_SNAPSHOT_DIR", str(tmp_path / "elsewhere"))
        ds.write_snapshot("firelight", "04", "x")
        assert (tmp_path / "elsewhere" / "firelight" / "04.md").is_file()

    def test_umlaut_chapter_slug_is_accepted(self):
        ds.write_snapshot("firelight", "01-der-fuchs-zählen-wollte", "x")
        assert ds.read_snapshot("firelight", "01-der-fuchs-zählen-wollte") == "x"

    def test_stale_marker_blocks_until_baseline_is_rewritten(self):
        ds.write_snapshot("firelight", "04", "x")
        ds.mark_stale("firelight", "04")
        assert ds.is_stale("firelight", "04") is True
        assert ds.read_snapshot("firelight", "04") is None
        ds.write_snapshot("firelight", "04", "fresh")
        assert ds.is_stale("firelight", "04") is False

    @pytest.mark.parametrize("book,chapter", [("../evil", "04"), ("firelight", "../../x"),
                                              ("firelight", "a/b"), (".hidden", "04")])
    def test_slugs_cannot_escape_the_snapshot_dir(self, book, chapter):
        with pytest.raises(ValueError):
            ds.snapshot_file(book, chapter)


class TestMerge:
    def test_claude_edit_in_an_untouched_paragraph_is_taken_over(self):
        after = BASE.replace("Mara crossed", "Mara walked across")
        out = ds.merge_claude_change(BASE, BASE, after)
        assert "Mara walked across" in out

    def test_author_edit_stays_a_difference(self):
        manual = BASE.replace("The river was loud.", "The river roared under the planks.")
        after = manual.replace("Mara crossed", "Mara walked across")
        out = ds.merge_claude_change(BASE, manual, after)
        assert "Mara walked across" in out
        assert "The river was loud." in out
        assert "roared" not in out

    def test_claude_removing_the_authors_comment_keeps_the_baseline_clean(self):
        with_comment = BASE + "\n\nMarkus: zu verschwurbelt, bitte kürzer formulieren hier"
        out = ds.merge_claude_change(BASE, with_comment, BASE)
        assert out == BASE

    def test_author_edit_next_to_a_removed_comment_survives(self):
        manual = BASE.replace("The river was loud.", "The river roared under the planks.")
        before = manual + "\n\nMarkus: das ist noch zu lang und verschwurbelt, bitte kürzen"
        out = ds.merge_claude_change(BASE, before, manual)
        assert "The river was loud." in out and "roared" not in out

    def test_author_inserted_paragraph_is_not_in_the_baseline(self):
        before = BASE.replace("The river was loud.",
                              "She had not slept in two days.\n\nThe river was loud.")
        after = before.replace("Mara crossed", "Mara walked across")
        out = ds.merge_claude_change(BASE, before, after)
        assert "slept" not in out and "Mara walked across" in out

    def test_author_deleted_paragraph_stays_in_the_baseline(self):
        before = BASE.replace("Mara crossed the bridge without looking down.\n\n", "")
        after = before.replace("The river was loud.", "The river was very loud.")
        out = ds.merge_claude_change(BASE, before, after)
        assert "Mara crossed the bridge" in out and "very loud" in out

    def test_same_size_author_block_maps_one_to_one(self):
        base = "A one.\n\nB one.\n\nC one."
        before = "A one.\n\nB two.\n\nC two."
        after = "A one.\n\nB two.\n\nC claude."
        assert ds.merge_claude_change(base, before, after).split("\n\n") == ["A one.", "B one.", "C claude."]

    def test_author_split_paragraph_is_not_duplicated(self):
        base = "A one.\n\nBC two three.\n\nD one."
        before = "A one.\n\nB two.\n\nC three.\n\nD one."
        after = "A one.\n\nB two.\n\nC claude.\n\nD one."
        out = ds.merge_claude_change(base, before, after).split("\n\n")
        assert out.count("C claude.") == 1
        assert "C three." not in out and "BC two three." not in out

    def test_claude_editing_the_first_paragraph_of_an_unequal_block(self):
        base = "b0.\n\nb1.\n\nb2.\n\nb3."
        before = "a0.\n\na1.\n\nb2.\n\nb3."
        after = "c1.\n\na1.\n\nb2.\n\nb3."
        out = ds.merge_claude_change(base, before, after).split("\n\n")
        assert out[0] == "c1." and out[-1] == "b3."
        assert "b0." not in out and "a0." not in out

    def test_claude_rewriting_an_author_edited_paragraph_absorbs_it(self):
        manual = BASE.replace("The river was loud.", "The river roared under the planks.")
        after = manual.replace("The river roared under the planks.", "Water thundered below.")
        assert "Water thundered below." in ds.merge_claude_change(BASE, manual, after)


class TestRecordToolWrite:
    def _with_baseline(self, tmp_path, text=BASE):
        path = chapter_file(tmp_path)
        path.write_text(text, encoding="utf-8")
        ds.record_tool_write(payload(path, "Write", content=text))
        return path

    def claude_edit(self, path: Path, new_text: str, tool="Edit", **tool_input):
        """Run one Claude write the way the hooks see it: pre, write, post."""
        data = payload(path, tool, **tool_input)
        ds.record_pre_write(data)
        path.write_text(new_text, encoding="utf-8")
        ds.record_tool_write(data)

    def test_first_write_creates_the_baseline(self, tmp_path):
        path = chapter_file(tmp_path)
        path.write_text(BASE, encoding="utf-8")
        ds.record_tool_write(payload(path, "Write", content=BASE))
        assert ds.read_snapshot("firelight", "04-the-crossing") == BASE

    def test_edit_keeps_manual_changes_visible(self, tmp_path):
        path = self._with_baseline(tmp_path)
        manual = BASE.replace("The river was loud.", "The river roared under the planks.")
        path.write_text(manual, encoding="utf-8")
        self.claude_edit(path, manual.replace("Mara crossed", "Mara walked across"),
                         old_string="Mara crossed", new_string="Mara walked across")
        baseline = ds.read_snapshot("firelight", "04-the-crossing")
        assert "Mara walked across" in baseline
        assert "The river was loud." in baseline and "roared" not in baseline

    def test_removing_the_authors_comment_does_not_stale_the_baseline(self, tmp_path):
        path = self._with_baseline(tmp_path)
        comment = "Markus: das ist zu verschwurbelt, bitte kürzer und klarer formulieren"
        path.write_text(BASE + "\n\n" + comment, encoding="utf-8")
        self.claude_edit(path, BASE, old_string="\n\n" + comment, new_string="")
        assert ds.is_stale("firelight", "04-the-crossing") is False
        assert ds.read_snapshot("firelight", "04-the-crossing") == BASE

    def test_deleting_baseline_text_together_with_a_comment_is_not_an_author_deletion(self, tmp_path):
        path = self._with_baseline(tmp_path)
        comment = "Markus: streich den Satz davor, er trägt nichts zur Szene bei"
        with_comment = BASE.replace("Mara crossed the bridge without looking down.",
                                    "Mara crossed the bridge without looking down.\n" + comment)
        path.write_text(with_comment, encoding="utf-8")
        after = with_comment.replace(
            "Mara crossed the bridge without looking down.\n" + comment + "\n\n", "")
        self.claude_edit(path, after,
                         old_string="Mara crossed the bridge without looking down.\n" + comment + "\n\n",
                         new_string="")
        hunks = ds.compute_hunks(ds.read_snapshot("firelight", "04-the-crossing"), after,
                                 review_handle="Markus")
        assert hunks["hunks"] == []

    def test_deleting_an_author_tweaked_paragraph_is_clauds_deletion(self, tmp_path):
        path = self._with_baseline(tmp_path)
        tweaked = BASE.replace("without looking down", "without once looking down at the water")
        path.write_text(tweaked, encoding="utf-8")
        after = tweaked.replace("Mara crossed the bridge without once looking down at the water.\n\n", "")
        self.claude_edit(path, after, old_string=
                         "Mara crossed the bridge without once looking down at the water.\n\n",
                         new_string="")
        hunks = ds.compute_hunks(ds.read_snapshot("firelight", "04-the-crossing"), after)
        assert hunks["hunks"] == []

    def test_adjacent_author_edits_and_a_claude_edit_in_the_second_one(self, tmp_path):
        base = "Alpha one two three four.\n\nBeta one two three four.\n\nGamma one two three four."
        path = self._with_baseline(tmp_path, base)
        manual = base.replace("Beta one", "Beta uno").replace("Gamma one", "Gamma uno")
        path.write_text(manual, encoding="utf-8")
        after = manual.replace("Gamma uno two three four.", "Gamma completely rewritten by Claude here.")
        self.claude_edit(path, after, old_string="Gamma uno two three four.",
                         new_string="Gamma completely rewritten by Claude here.")
        baseline = ds.read_snapshot("firelight", "04-the-crossing")
        assert baseline.count("Gamma") == 1
        assert "Beta one" in baseline            # the author's other edit is still a difference
        assert "Gamma one two three four." not in baseline

    def test_crlf_files_survive_a_write_followed_by_a_deletion(self, tmp_path):
        crlf = BASE.replace("\n", "\r\n")
        path = chapter_file(tmp_path)
        path.write_bytes(crlf.encode("utf-8"))
        ds.record_tool_write(payload(path, "Write", content=crlf))
        after = crlf.replace("Mara crossed the bridge without looking down.\r\n\r\n", "")
        data = payload(path, "Edit", old_string="Mara crossed the bridge without looking down.\r\n\r\n",
                       new_string="")
        ds.record_pre_write(data)
        path.write_bytes(after.encode("utf-8"))
        ds.record_tool_write(data)
        hunks = ds.compute_hunks(ds.read_snapshot("firelight", "04-the-crossing"), after)
        assert hunks["hunks"] == []

    def test_write_takes_claudes_output_as_the_baseline(self, tmp_path):
        path = self._with_baseline(tmp_path)
        new = BASE.replace("Mara crossed", "Mara walked across")
        path.write_text(new, encoding="utf-8")
        ds.record_tool_write(payload(path, "Write", content=new))
        assert "Mara walked across" in ds.read_snapshot("firelight", "04-the-crossing")

    def test_original_file_in_the_response_replaces_a_missing_pre_copy(self, tmp_path):
        path = self._with_baseline(tmp_path)
        manual = BASE.replace("The river was loud.", "The river roared under the planks.")
        edited = manual.replace("Mara crossed", "Mara walked across")
        path.write_text(edited, encoding="utf-8")
        ds.record_tool_write(payload(path, "Edit", response={"originalFile": manual},
                                     old_string="Mara crossed", new_string="Mara walked across"))
        baseline = ds.read_snapshot("firelight", "04-the-crossing")
        assert "Mara walked across" in baseline and "roared" not in baseline

    def test_edit_without_any_view_of_the_file_before_marks_the_baseline_stale(self, tmp_path):
        path = self._with_baseline(tmp_path)
        path.write_text(BASE.replace("loud", "NEW"), encoding="utf-8")
        ds.record_tool_write(payload(path, "Edit", old_string="loud", new_string="NEW"))
        assert ds.is_stale("firelight", "04-the-crossing") is True
        path.write_text(BASE + "\n\nmore", encoding="utf-8")
        ds.record_tool_write(payload(path, "Write", content=BASE + "\n\nmore"))
        assert ds.read_snapshot("firelight", "04-the-crossing") is None

    def test_pre_copy_is_consumed_by_the_post_hook(self, tmp_path):
        path = self._with_baseline(tmp_path)
        data = payload(path, "Edit", old_string="loud", new_string="calm")
        ds.record_pre_write(data)
        pre = ds.snapshot_file("firelight", "04-the-crossing").with_suffix(".pre")
        assert pre.is_file()
        path.write_text(BASE.replace("loud", "calm"), encoding="utf-8")
        ds.record_tool_write(data)
        assert not pre.exists()

    def test_memoir_books_get_no_baseline_and_no_pre_copy(self, tmp_path):
        path = chapter_file(tmp_path, book="my-life", category="memoir")
        path.write_text("Anna ging.", encoding="utf-8")
        ds.record_pre_write(payload(path, "Write", content="Anna ging."))
        ds.record_tool_write(payload(path, "Write", content="Anna ging."))
        assert not (ds.snapshots_dir() / "my-life").exists()

    @pytest.mark.parametrize("readme", [
        '---\ntitle: "x"\nbook_category: memoir # note\n---\n',
        '---\ntitle: "A---B"\nbook_category: "memoir"\n---\n',
        '\ufeff---\ntitle: "x"\nbook_category: "memoir"\n---\n',
        '---\ntitle: Mein Leben: Teil 1\nbook_category: memoir\n---\n',
        '---\ntitle: "x"\nbook_category: " Memoir "\n---\n',
        "<none>",
        "# no frontmatter at all\n",
        '---\ntitle: "x"\nbook_category: "poetry"\n---\n',
        "---\n- just\n- a list\n---\n",
    ])
    def test_memoir_and_unparseable_readmes_fail_closed(self, tmp_path, readme):
        path = chapter_file(tmp_path, book="odd-book", readme=readme)
        path.write_text("Some text of the chapter.", encoding="utf-8")
        ds.record_tool_write(payload(path, "Write", content="Some text of the chapter."))
        assert ds.read_snapshot("odd-book", "04-the-crossing") is None

    def test_leftover_baselines_are_removed_when_a_book_turns_out_to_be_memoir(self, tmp_path):
        path = chapter_file(tmp_path, book="my-life", category="memoir")
        ds.write_snapshot("my-life", "04-the-crossing", "old copy")
        path.write_text("Anna ging.", encoding="utf-8")
        ds.record_tool_write(payload(path, "Write", content="Anna ging."))
        assert not (ds.snapshots_dir() / "my-life").exists()

    def test_files_outside_the_content_root_are_ignored(self, tmp_path):
        stray = tmp_path / "backup" / "firelight" / "chapters" / "04-the-crossing"
        stray.mkdir(parents=True)
        (stray / "draft.md").write_text("copy", encoding="utf-8")
        chapter_file(tmp_path)
        ds.record_tool_write(payload(stray / "draft.md", "Write", content="copy"))
        assert ds.read_snapshot("firelight", "04-the-crossing") is None

    def test_umlaut_chapter_slug_works_end_to_end(self, tmp_path):
        slug = "01-der-fuchs-der-schneeflocken-zählen-wollte"
        path = chapter_file(tmp_path, chapter=slug)
        path.write_text(BASE, encoding="utf-8")
        ds.record_tool_write(payload(path, "Write", content=BASE))
        assert ds.read_snapshot("firelight", slug) == BASE

    def test_never_raises(self, tmp_path):
        for fn in (ds.record_pre_write, ds.record_tool_write):
            fn({"tool_name": "Edit", "tool_input": None})
            fn({})
            fn(payload(tmp_path / "x" / "chapters" / "y" / "draft.md", "Edit",
                       old_string="a", new_string="b"))

    def test_remove_book_snapshots_refuses_an_empty_slug(self):
        with pytest.raises(ValueError):
            ds.remove_book_snapshots("")


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
        assert hunk["changed_words"] >= 4 and hunk["clipped"] is False

    def test_changes_up_to_three_words_are_ignored(self):
        result = ds.compute_hunks(BASE, BASE.replace("The river was loud.", "The river was quite loud."))
        assert result["hunks"] == [] and result["ignored_small"] == 1

    def test_four_word_change_counts(self):
        current = BASE.replace("The river was loud.", "The river was very loud and cold tonight.")
        assert ds.compute_hunks(BASE, current)["total"] == 1

    def test_whitespace_and_punctuation_only_changes_are_ignored(self):
        assert ds.compute_hunks(BASE, BASE.replace("The river was loud.", "The  river was loud!"))["hunks"] == []

    @pytest.mark.parametrize("comment", [
        "Markus: das ist zu verschwurbelt, bitte kürzer und klarer formulieren",
        "> Markus: das ist zu verschwurbelt, bitte kürzer und klarer formulieren",
        "**Markus:** das ist zu verschwurbelt, bitte kürzer und klarer formulieren",
        "Markus : das ist zu verschwurbelt, bitte kürzer und klarer formulieren",
        "Eine Zeile Prosa.\nMarkus: das ist zu verschwurbelt, bitte kürzer und klarer formulieren",
    ])
    def test_review_comment_blocks_are_not_edits(self, comment):
        result = ds.compute_hunks(BASE, BASE + "\n\n" + comment, review_handle="Markus")
        assert result["hunks"] == []

    def test_inserted_paragraph_is_an_insert_hunk(self):
        new = "She had not slept in two days and the bridge swayed beneath her."
        current = BASE.replace("The river was loud.", f"{new}\n\nThe river was loud.")
        hunk = ds.compute_hunks(BASE, current)["hunks"][0]
        assert (hunk["kind"], hunk["before"], hunk["after"]) == ("insert", "", new)

    def test_deleted_paragraph_is_a_delete_hunk(self):
        current = BASE.replace("Mara crossed the bridge without looking down.\n\n", "")
        hunk = ds.compute_hunks(BASE, current)["hunks"][0]
        assert hunk["kind"] == "delete" and hunk["after"] == ""

    def test_rewrite_next_to_an_insert_stays_a_separate_rewrite(self):
        base = "The silence held the room like a held breath, and nobody dared to speak."
        cur = ("A new paragraph about something else entirely, long enough to count here.\n\n"
               "Nobody dared to speak, and the silence held the room like a breath.")
        kinds = sorted(h["kind"] for h in ds.compute_hunks(base, cur)["hunks"])
        assert kinds == ["insert", "replace"]

    def test_hunk_list_is_paged_and_reports_truncation(self):
        base = "\n\n".join(f"Paragraph number {i} stays as it is." for i in range(30))
        cur = "\n\n".join(f"Paragraph number {i} was rewritten completely by the author today." for i in range(30))
        first = ds.compute_hunks(base, cur, max_hunks=20)
        assert first["total"] == 30 and len(first["hunks"]) == 20 and first["truncated"] is True
        second = ds.compute_hunks(base, cur, max_hunks=20, offset=20)
        assert len(second["hunks"]) == 10 and second["truncated"] is False
        assert second["hunks"][0]["index"] == 21

    def test_long_texts_are_clipped_and_flagged(self):
        result = ds.compute_hunks("short.", " ".join(["word"] * 3000), max_chars=500)
        hunk = result["hunks"][0]
        assert len(hunk["after"]) <= 520 and hunk["clipped"] is True

    def test_huge_blocks_do_not_run_the_word_matcher(self):
        import time

        big = " ".join(f"w{i}" for i in range(60_000))
        start = time.monotonic()
        result = ds.compute_hunks("small.", big)
        assert time.monotonic() - start < 5
        assert result["total"] == 1

    def test_indexes_are_sequential(self):
        base = "A one two three four five.\n\nB one two three four five.\n\nC one two three four five."
        cur = "A six seven eight nine ten.\n\nB one two three four five.\n\nC six seven eight nine ten."
        assert [h["index"] for h in ds.compute_hunks(base, cur)["hunks"]] == [1, 2]


def test_payload_is_json_serialisable_roundtrip():
    result = ds.compute_hunks(BASE, BASE.replace("The river was loud.", "x " * 10))
    assert json.loads(json.dumps(result))["total"] == 1
