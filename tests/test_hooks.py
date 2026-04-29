"""Tests for StoryForge PostToolUse hooks."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

from hooks import validate_chapter as vc
from hooks.validate_character import validate_character
from tools import banlist_loader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path, claudemd_body: str | None = None) -> Path:
    """Create a minimal book scaffold and return the book root."""
    book = tmp_path / "blood-and-binary"
    (book / "chapters" / "01-intro").mkdir(parents=True)
    (book / "README.md").write_text("# Blood & Binary\n", encoding="utf-8")
    if claudemd_body is not None:
        (book / "CLAUDE.md").write_text(claudemd_body, encoding="utf-8")
    return book


def _install_author_vocab(tmp_path: Path, author_slug: str, banned_words: list[str]) -> Path:
    """Place a fake ~/.storyforge/authors/{slug}/vocabulary.md and patch
    the loader to read from this temp home for the duration of the test."""
    home = tmp_path / "_storyforge_home"
    vocab_dir = home / "authors" / author_slug
    vocab_dir.mkdir(parents=True)
    body = "## Banned Words\n\n### Absolutely Forbidden\n"
    for w in banned_words:
        body += f"- {w}\n"
    (vocab_dir / "vocabulary.md").write_text(body, encoding="utf-8")
    return home


def _write_draft(book: Path, body: str, chapter: str = "01-intro") -> Path:
    draft = book / "chapters" / chapter / "draft.md"
    draft.write_text(body, encoding="utf-8")
    return draft


def _write_chapter_readme(
    book: Path,
    target_words: int | str,
    chapter: str = "01-intro",
) -> Path:
    """Write a chapter README with a Target Words cell. Accepts int (3200)
    or string ("~3,200") to test parser tolerance."""
    readme = book / "chapters" / chapter / "README.md"
    body = f"# Chapter\n\n## Overview\n| Field | Value |\n|-------|-------|\n| Target Words | {target_words} |\n"
    readme.write_text(body, encoding="utf-8")
    return readme


# ---------------------------------------------------------------------------
# validate_chapter() — pure-function behavior
# ---------------------------------------------------------------------------


class TestValidateChapter:
    def test_ignores_non_chapter_files(self):
        assert vc.validate_chapter("/some/other/file.md") == []

    def test_ignores_readme(self):
        assert vc.validate_chapter("/project/chapters/01-intro/README.md") == []

    def test_detects_ai_tells(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "She delved into the tapestry of nuanced experiences, "
                "each thread a vibrant testament to the intricate myriad "
                "of unprecedented journeys she had embarked upon. "
                "The beacon of hope resonated with a pivotal force. " * 3
            ),
        )

        findings = vc.validate_chapter(str(draft))
        ai_warns = [f for f in findings if f.category == "ai_tell"]
        assert len(ai_warns) > 3
        assert all(f.severity == vc.SEVERITY_WARN for f in ai_warns)

    def test_clean_prose_passes(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "The door slammed. She froze, one hand on the railing, "
                "the other clutching a paper bag from the Korean grocery "
                "on Seventh. The stairs smelled like wet concrete and old "
                "cigarettes. Three flights up, apartment 4B, the deadbolt "
                "she'd been meaning to replace since February. "
                "Her keys jangled. Too loud in the silence. "
                "Something was wrong. She could feel it — that prickle "
                "at the back of her neck, the one her mother called "
                "'the animal knowing.' Twenty-eight years of ignoring it. "
                "Tonight she listened." * 3
            ),
        )

        findings = vc.validate_chapter(str(draft))
        ai_warns = [f for f in findings if f.category == "ai_tell"]
        assert ai_warns == []

    def test_skips_short_drafts(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# Chapter 1\n\n")
        assert vc.validate_chapter(str(draft)) == []

    def test_blocks_book_rule_violation(self, tmp_path):
        # Book CLAUDE.md with a backtick-wrapped banned literal — the same
        # syntax the existing manuscript-checker already understands.
        book = _make_book(
            tmp_path,
            claudemd_body=(
                "# Blood & Binary\n\n"
                "## Rules\n"
                "- Do not use `clocked` as a verb for noticing/realizing — "
                "reader dislikes the word.\n"
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the door from across the room. The handle "
                "looked wrong. He shifted his weight, kept the bag tight "
                "against his ribs, and waited for the next breath. " * 5
            ),
        )

        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert len(blocking) >= 1
        assert any(f.category == "book_rule_violation" for f in blocking)
        assert any("clocked" in f.message for f in blocking)
        assert all(f.line is not None for f in blocking)

    def test_clean_prose_with_book_claudemd_passes(self, tmp_path):
        book = _make_book(
            tmp_path,
            claudemd_body=("# Blood & Binary\n\n## Rules\n- Do not use `clocked` as a verb.\n"),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo noticed the door from across the room. The handle "
                "looked wrong. He shifted his weight, kept the bag tight "
                "against his ribs, and waited for the next breath. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert blocking == []

    def test_double_quoted_phrases_do_not_trigger_block(self, tmp_path):
        """Hook only honors backtick patterns. Double-quoted phrases in
        rules are advisory text only — typically positive examples or
        replacement suggestions — and must not produce hard-block
        findings (see #87)."""
        book = _make_book(
            tmp_path,
            claudemd_body=(
                '# Book\n\n## Rules\n- Avoid "clocked" as a verb. Replace with "noticed" or "registered".\n'
            ),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the room and let his shoulders drop. "
                "The bag slid off the bench. He counted three breaths "
                "before he turned to face the door. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        # Quoted phrases are not block patterns — only backticks are.
        assert blocking == []

    def test_backtick_regex_pattern_with_alternation(self, tmp_path):
        """Backticks containing regex metacharacters compile as regex."""
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Rules\n- Avoid `the (specific|particular|certain) [a-z]+ that` as filler.\n"),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + ("She noticed the specific quietude that follows a slammed door. The room held its breath. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert len(blocking) >= 1

    def test_blocks_meta_narrative_callback_phrase(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 22\n\n"
            + (
                "He stepped into the corridor. The Ch 15 callback was, "
                "technically, funny. The wallpaper smelled like rain. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        # Both "Ch 15" and "callback" should fire.
        assert len(meta) >= 2
        assert all(f.severity == vc.SEVERITY_BLOCK for f in meta)

    def test_blocks_foreshadow_in_prose(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 4\n\n"
            + ("The lamp on the table foreshadowed the long night ahead. She watched it without thinking. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert any("foreshadow" in f.message.lower() for f in meta)

    def test_blocks_calls_back_to(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 6\n\n"
            + ("The smell of pine calls back to the cabin scene in chapter three. He felt his shoulders drop. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert any("calls back to" in f.message.lower() for f in meta)

    def test_blocks_parallels_her_earlier(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 7\n\n"
            + ("Her hand on the door parallels her earlier reluctance, the one she had carried into the cottage. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert any("parallels" in f.message.lower() for f in meta)

    def test_html_comment_is_ignored(self, tmp_path):
        """Outline scaffolding inside HTML comments may use structural
        language without triggering the hook."""
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 5\n\n"
            "<!-- Ch 4 callback: the cabin pine smell. Foreshadow the trail. -->\n\n"
            + ("He stepped into the corridor. The wallpaper smelled like rain on cedar. She had not slept. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert meta == []

    def test_html_comment_does_not_shield_following_prose(self, tmp_path):
        """Multi-line HTML comment should end before later prose, so a
        meta-narrative phrase after the comment still fires."""
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 8\n\n"
            "<!--\n"
            "Ch 6 callback: the deferred-beer deal.\n"
            "-->\n\n"
            + ("The Ch 6 callback was funny in retrospect. He turned the page. The book smelled like dust. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert any("Ch 6" in f.message for f in meta)
        # And callback also fires.
        assert any("callback" in f.message.lower() for f in meta)

    def test_clean_prose_no_meta_narrative(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 9\n\n"
            + (
                "She turned the corner and the smell of bread reached her "
                "before the lamplight did. The kitchen door was open. "
                "Her brother had been baking again. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert meta == []

    def test_word_boundaries_avoid_false_positives(self, tmp_path):
        """'called' must not match 'calls back to', 'channel' must not
        match 'Ch \\d+', etc."""
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 10\n\n"
            + (
                "She called him back later. The channel was rough. "
                "He paralleled her stride down the dock without thinking. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        meta = [f for f in findings if f.category == "meta_narrative"]
        assert meta == []

    def test_block_via_main_for_meta_narrative(self, tmp_path, monkeypatch, capsys):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 22\n\n"
            + (
                "She crossed the room. The Ch 15 callback was, technically, "
                "funny. The wallpaper smelled like rain. " * 5
            ),
        )
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 2
        err = capsys.readouterr().err
        assert "meta-narrative" in err.lower() or "callback" in err.lower()

    def test_backtick_regex_does_not_match_unrelated_text(self, tmp_path):
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Rules\n- Avoid `the (specific|particular|certain) [a-z]+ that` as filler.\n"),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "The door slammed. She held her breath, counted to four, "
                "then exhaled into the fabric of her sleeve. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert blocking == []


# ---------------------------------------------------------------------------
# Author vocabulary banlist (block-severity)
# ---------------------------------------------------------------------------


class TestAuthorVocabBanlist:
    """Verify that words listed in ~/.storyforge/authors/{slug}/vocabulary.md
    block writes when found in prose."""

    def _patch_storyforge_home(self, monkeypatch, fake_home: Path) -> None:
        """Patch Path.home() so the loader reads from fake_home."""
        monkeypatch.setattr(
            banlist_loader,
            "_author_vocab_path",
            lambda slug, storyforge_home=None: fake_home / "authors" / slug / "vocabulary.md",
        )

    def test_author_vocab_word_blocks_write(self, tmp_path, monkeypatch):
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Book Facts\n\n- **Author:** Alice Author\n"),
        )
        home = _install_author_vocab(tmp_path, "alice-author", ["delve", "tapestry"])
        self._patch_storyforge_home(monkeypatch, home)

        draft = _write_draft(
            book,
            "# Chapter 1\n\n" + ("She delved into the tapestry of memory. The room was warm. She had not slept. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        author_blocks = [f for f in findings if f.category == "author_vocab_violation"]
        assert len(author_blocks) >= 2
        assert all(f.severity == vc.SEVERITY_BLOCK for f in author_blocks)
        labels = " ".join(f.message for f in author_blocks)
        assert "delve" in labels.lower() or "tapestry" in labels.lower()

    def test_author_vocab_clean_prose_passes(self, tmp_path, monkeypatch):
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Book Facts\n\n- **Author:** Alice Author\n"),
        )
        home = _install_author_vocab(tmp_path, "alice-author", ["delve"])
        self._patch_storyforge_home(monkeypatch, home)

        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + ("She investigated the box. The room was warm. The kettle had cooled. She had not slept. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        author_blocks = [f for f in findings if f.category == "author_vocab_violation"]
        assert author_blocks == []

    def test_no_author_in_book_skips_check(self, tmp_path, monkeypatch):
        book = _make_book(
            tmp_path,
            claudemd_body="# Book\n\n## Book Facts\n\n- **Genre:** test\n",
        )
        # Even with vocab installed for "alice-author", the book does not
        # name an author → skip.
        home = _install_author_vocab(tmp_path, "alice-author", ["delve"])
        self._patch_storyforge_home(monkeypatch, home)

        draft = _write_draft(
            book,
            "# Chapter 1\n\n" + ("She delved into the tapestry. " * 30),
        )
        findings = vc.validate_chapter(str(draft))
        author_blocks = [f for f in findings if f.category == "author_vocab_violation"]
        assert author_blocks == []

    def test_author_without_vocab_file_does_not_error(self, tmp_path, monkeypatch):
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Book Facts\n\n- **Author:** Bob Bookwright\n"),
        )
        # No vocab.md installed for bob-bookwright. Loader should return [].
        home = tmp_path / "_storyforge_home"
        (home / "authors" / "bob-bookwright").mkdir(parents=True)
        self._patch_storyforge_home(monkeypatch, home)

        draft = _write_draft(
            book,
            "# Chapter 1\n\n" + ("She delved into the tapestry. " * 30),
        )
        findings = vc.validate_chapter(str(draft))
        author_blocks = [f for f in findings if f.category == "author_vocab_violation"]
        assert author_blocks == []

    def test_block_message_attributes_source(self, tmp_path, monkeypatch):
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Book Facts\n\n- **Author:** Alice Author\n"),
        )
        home = _install_author_vocab(tmp_path, "alice-author", ["delve"])
        self._patch_storyforge_home(monkeypatch, home)

        draft = _write_draft(
            book,
            "# Chapter 1\n\n" + ("She delved into the box. " * 30),
        )
        findings = vc.validate_chapter(str(draft))
        author_blocks = [f for f in findings if f.category == "author_vocab_violation"]
        assert author_blocks
        assert "author voice" in author_blocks[0].message.lower()
        assert "author-vocab" in author_blocks[0].message.lower()
        assert "absolutely forbidden" in author_blocks[0].message.lower()


# ---------------------------------------------------------------------------
# Global AI-tells loaded from anti-ai-patterns.md
# ---------------------------------------------------------------------------


class TestTimeAnchorScanner:
    """End-to-end: chapter README has a Chapter Timeline → relative
    phrases in prose surface as warn-severity findings annotated with
    the implied story date."""

    def _setup_chapter(self, tmp_path: Path) -> Path:
        book = _make_book(tmp_path)
        chapter_dir = book / "chapters" / "01-intro"
        (chapter_dir / "README.md").write_text(
            "# Chapter\n\n"
            "## Chapter Timeline\n\n"
            "**Start:** Tue Dec 24 ~19:30 (library)\n"
            "**End:** Wed Dec 25 ~07:00 (trailhead)\n",
            encoding="utf-8",
        )
        return book

    def test_yesterday_in_prose_triggers_warn(self, tmp_path):
        book = self._setup_chapter(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 22\n\n"
            + (
                "Yesterday felt like a different country, the kind he could "
                "not return to. He sat at the window and watched the snow. "
                "The room was cold. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        time_warns = [f for f in findings if f.category == "time_anchor"]
        assert time_warns
        assert all(f.severity == vc.SEVERITY_WARN for f in time_warns)
        # Annotation should point at the implied date.
        msg = time_warns[0].message
        assert "Mon Dec 23" in msg
        assert "yesterday" in msg.lower()

    def test_an_hour_ago_resolves_to_specific_time(self, tmp_path):
        book = self._setup_chapter(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 22\n\n"
            + ("An hour ago he had still believed the message would come. Now the silence had its own gravity. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        time_warns = [f for f in findings if f.category == "time_anchor"]
        assert any("18:30" in f.message for f in time_warns)

    def test_no_chapter_timeline_skips_scan(self, tmp_path):
        book = _make_book(tmp_path)
        # No README written for the chapter → scanner has no anchor.
        draft = _write_draft(
            book,
            "# Chapter 1\n\n" + ("Yesterday felt distant. He sat at the window and watched. The room was cold. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        time_warns = [f for f in findings if f.category == "time_anchor"]
        assert time_warns == []

    def test_unrelated_phrases_do_not_match(self, tmp_path):
        book = self._setup_chapter(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 22\n\n"
            + (
                "He had not slept. The kettle had cooled. The book on the "
                "table was still open. The hour was hard to read. " * 5
            ),
        )
        findings = vc.validate_chapter(str(draft))
        time_warns = [f for f in findings if f.category == "time_anchor"]
        assert time_warns == []

    def test_block_in_strict_mode_does_not_fire(self, tmp_path, monkeypatch, capsys):
        """Time-anchor findings are warn-only — even in strict mode they
        must not trigger exit code 2 (#72 keeps semantics conservative
        until block-on-conflict is added in a follow-up)."""
        book = self._setup_chapter(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 22\n\n"
            + ("Yesterday already felt like a different country. He sat at the window and watched the snow. " * 5),
        )
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        # No block — only warn.
        assert rc == 0


class TestPovBoundaryHookIntegration:
    """Wire-up test for the POV-boundary scan in validate_chapter (#76)."""

    def _setup(
        self,
        tmp_path: Path,
        *,
        pov_name: str,
        pov_knowledge: dict[str, list[str]],
    ) -> Path:
        book = _make_book(tmp_path)
        chapter_dir = book / "chapters" / "01-intro"
        # chapter README must carry the POV character.
        readme_body = (
            f'---\ntitle: "Intro"\nnumber: 1\nstatus: "draft"\npov_character: "{pov_name}"\n---\n# Chapter 1\n'
        )
        (chapter_dir / "README.md").write_text(readme_body, encoding="utf-8")
        # Character file with knowledge profile.
        chars = book / "characters"
        chars.mkdir(parents=True, exist_ok=True)
        from tools.shared.paths import slugify

        slug = slugify(pov_name)
        knowledge_lines = ""
        for tier, terms in pov_knowledge.items():
            knowledge_lines += f"  {tier}: {terms}\n"
        char_body = f'---\nname: "{pov_name}"\nknowledge:\n{knowledge_lines}---\n# {pov_name}\n'
        (chars / f"{slug}.md").write_text(char_body, encoding="utf-8")
        return book

    def test_flags_forensics_term_in_lay_pov(self, tmp_path):
        book = self._setup(
            tmp_path,
            pov_name="Theo Wilkons",
            pov_knowledge={
                "expert": ["it"],
                "competent": [],
                "layperson": [],
                "none": ["forensics"],
            },
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo crouched. The blood smells when it has been on the "
                "ground for a while in cold air. He swallowed. " * 6
            ),
        )
        findings = vc.validate_chapter(str(draft))
        pov = [f for f in findings if f.category == "pov_boundary"]
        assert pov, "expected at least one POV-boundary finding"
        assert all(f.severity == vc.SEVERITY_WARN for f in pov)
        assert any("blood smells when" in f.message for f in pov)

    def test_does_not_flag_when_pov_is_expert(self, tmp_path):
        book = self._setup(
            tmp_path,
            pov_name="Kael",
            pov_knowledge={
                "expert": ["forensics"],
                "competent": [],
                "layperson": [],
                "none": [],
            },
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Kael crouched. The blood smells when it has been on the "
                "ground for a while in cold air. He nodded. " * 6
            ),
        )
        findings = vc.validate_chapter(str(draft))
        pov = [f for f in findings if f.category == "pov_boundary"]
        assert pov == []

    def test_dialog_does_not_flag(self, tmp_path):
        book = self._setup(
            tmp_path,
            pov_name="Theo Wilkons",
            pov_knowledge={
                "expert": ["it"],
                "competent": [],
                "layperson": [],
                "none": ["forensics"],
            },
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                'Kael crouched. "Blood smells when it has been on the '
                'ground for a while in cold air," he said. Theo watched. ' * 6
            ),
        )
        findings = vc.validate_chapter(str(draft))
        pov = [f for f in findings if f.category == "pov_boundary"]
        assert pov == []


class TestGlobalAITellsLoading:
    """The hook now reads its AI-tells from
    ``reference/craft/anti-ai-patterns.md`` via the loader, not from a
    hardcoded list. Verify the wiring still produces warnings on the
    previously-hardcoded set."""

    def test_delve_still_produces_warn(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + ("She delved into the tapestry of vibrant memory. The room was warm. The kettle had cooled. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        ai_tells = [f for f in findings if f.category == "ai_tell"]
        assert ai_tells
        assert all(f.severity == vc.SEVERITY_WARN for f in ai_tells)
        labels = " ".join(f.message.lower() for f in ai_tells)
        assert "delve" in labels


# ---------------------------------------------------------------------------
# Per-chapter limit parsing
# ---------------------------------------------------------------------------


class TestExtractChapterLimit:
    def test_no_limit_returns_zero(self):
        assert vc._extract_chapter_limit("Avoid `clocked` as a verb") == 0

    def test_max_n_per_chapter(self):
        rule = "Limit `kind of X that Y` — max 3 per chapter."
        assert vc._extract_chapter_limit(rule) == 3

    def test_max_n_per_chapter_german(self):
        rule = "Limit `kind of X that Y` — max 3 per kapitel."
        assert vc._extract_chapter_limit(rule) == 3

    def test_max_range_takes_upper_bound(self):
        rule = "Limit the `specific kind of X that Y` construction — max 2-3 per chapter."
        assert vc._extract_chapter_limit(rule) == 3

    def test_maximum_word(self):
        rule = "Use `felt like` sparingly — maximum 2 per chapter."
        assert vc._extract_chapter_limit(rule) == 2

    def test_limit_to_n_per_chapter(self):
        rule = "Limit to 4 per chapter for the construction `the way`."
        assert vc._extract_chapter_limit(rule) == 4

    def test_per_book_limit_is_not_per_chapter(self):
        rule = "Max one use of `opened his mouth. Closed it.` per book."
        assert vc._extract_chapter_limit(rule) == 0

    def test_max_of_n_per_chapter(self):
        rule = "Avoid `pulsed` — max of 2 per chapter."
        assert vc._extract_chapter_limit(rule) == 2


# ---------------------------------------------------------------------------
# Chapter target-words loader
# ---------------------------------------------------------------------------


class TestChapterTargetWords:
    def test_default_when_no_readme(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# Chapter 1\n")
        assert vc._chapter_target_words(draft) == vc.DEFAULT_CHAPTER_TARGET_WORDS

    def test_default_when_readme_has_no_target(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# Chapter 1\n")
        readme = book / "chapters" / "01-intro" / "README.md"
        readme.write_text("# Chapter 1\n\nNo overview.\n", encoding="utf-8")
        assert vc._chapter_target_words(draft) == vc.DEFAULT_CHAPTER_TARGET_WORDS

    def test_parses_simple_integer(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# Chapter 1\n")
        _write_chapter_readme(book, 2500)
        assert vc._chapter_target_words(draft) == 2500

    def test_parses_tilde_and_comma(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# Chapter 1\n")
        _write_chapter_readme(book, "~3,200")
        assert vc._chapter_target_words(draft) == 3200

    def test_parses_dot_thousand_separator(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# Chapter 1\n")
        _write_chapter_readme(book, "3.200")
        assert vc._chapter_target_words(draft) == 3200

    def test_zero_falls_back_to_default(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# Chapter 1\n")
        _write_chapter_readme(book, 0)
        assert vc._chapter_target_words(draft) == vc.DEFAULT_CHAPTER_TARGET_WORDS


# ---------------------------------------------------------------------------
# Scaled per-scene limit math
# ---------------------------------------------------------------------------


class TestScaledSceneLimit:
    def test_zero_chapter_limit_returns_zero(self):
        assert vc._scaled_scene_limit(0, 900, 3200) == 0

    def test_900_of_3200_with_chapter_3_floors_at_one(self):
        # 3 * 900/3200 = 0.84 → ceil → 1
        assert vc._scaled_scene_limit(3, 900, 3200) == 1

    def test_1800_of_3200_with_chapter_3_returns_two(self):
        # 3 * 1800/3200 = 1.69 → ceil → 2
        assert vc._scaled_scene_limit(3, 1800, 3200) == 2

    def test_full_chapter_returns_full_limit(self):
        assert vc._scaled_scene_limit(3, 3200, 3200) == 3

    def test_over_target_caps_at_chapter_limit(self):
        # Going over the word target does not unlock more banned-phrase
        # budget. The chapter cap is a hard ceiling.
        assert vc._scaled_scene_limit(3, 4000, 3200) == 3
        assert vc._scaled_scene_limit(3, 6400, 3200) == 3

    def test_zero_target_returns_chapter_limit(self):
        assert vc._scaled_scene_limit(3, 900, 0) == 3


# ---------------------------------------------------------------------------
# Per-scene counter integration
# ---------------------------------------------------------------------------


class TestPerSceneCounter:
    """End-to-end tests: rule with limit + draft with hits → block when
    the scaled scene budget is exceeded, allow otherwise."""

    def _book_with_limit_rule(self, tmp_path: Path) -> Path:
        # Backtick contains regex metacharacters (\w), so it compiles as a
        # regex — matches "kind of corridor that", "kind of silence that",
        # etc.
        return _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Rules\n- Limit the `kind of \\w+ that` construction — max 3 per chapter.\n"),
        )

    def test_no_limit_pattern_still_blocks_on_first_hit(self, tmp_path):
        """Backwards compat: rules without 'max N per chapter' keep
        block-on-first-hit behavior."""
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Rules\n- Avoid `clocked` as a verb.\n"),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n" + ("Theo clocked the room. The bag slid off the bench. He counted three breaths. " * 5),
        )
        findings = vc.validate_chapter(str(draft))
        blocking = [f for f in findings if f.severity == vc.SEVERITY_BLOCK]
        assert any(f.category == "book_rule_violation" for f in blocking)

    def test_one_hit_in_short_scene_passes(self, tmp_path):
        """900 words toward 3200 target, max 3 per chapter → scaled to 1.
        One hit is allowed."""
        book = self._book_with_limit_rule(tmp_path)
        _write_chapter_readme(book, 3200)
        # Build ~900-word draft with exactly 1 banned hit.
        body = "# Chapter 1\n\n"
        body += "She walked the kind of corridor that smelled like rain. "
        body += "The door was open. She walked inside. " * 175
        draft = _write_draft(book, body)
        findings = vc.validate_chapter(str(draft))
        violations = [f for f in findings if f.category == "book_rule_violation"]
        assert violations == []

    def test_five_hits_in_short_scene_blocks(self, tmp_path):
        """Beta-feedback case: 5 hits in 900-word scene must block."""
        book = self._book_with_limit_rule(tmp_path)
        _write_chapter_readme(book, 3200)
        body = "# Chapter 1\n\n"
        body += (
            "She walked the kind of corridor that smelled like rain. "
            "He noticed the kind of silence that follows a slam. "
            "The lamp threw the kind of yellow that makes you tired. "
            "The book smelled the kind of musty that only old paper has. "
            "She turned the kind of slow that means thinking. "
        )
        # Pad to reach roughly 900 words.
        body += "The room was warm. The kettle had cooled. " * 175
        draft = _write_draft(book, body)
        findings = vc.validate_chapter(str(draft))
        violations = [f for f in findings if f.category == "book_rule_violation"]
        assert len(violations) >= 1
        msg = violations[0].message
        assert "5 times" in msg or "appears 5" in msg
        assert "Cut at least" in msg

    def test_three_hits_at_full_chapter_passes(self, tmp_path):
        """At full chapter target (3200 words), the per-chapter cap of 3
        applies directly. Three hits is the limit, not a violation."""
        book = self._book_with_limit_rule(tmp_path)
        _write_chapter_readme(book, 3200)
        body = "# Chapter 1\n\n"
        body += (
            "She walked the kind of corridor that smelled like rain. "
            "He noticed the kind of silence that follows a slam. "
            "The lamp threw the kind of yellow that makes you tired. "
        )
        # Fill to ~3200 words.
        body += "The room was warm. The kettle had cooled. " * 600
        draft = _write_draft(book, body)
        findings = vc.validate_chapter(str(draft))
        violations = [f for f in findings if f.category == "book_rule_violation"]
        assert violations == []

    def test_four_hits_at_full_chapter_blocks(self, tmp_path):
        book = self._book_with_limit_rule(tmp_path)
        _write_chapter_readme(book, 3200)
        body = "# Chapter 1\n\n"
        body += (
            "She walked the kind of corridor that smelled like rain. "
            "He noticed the kind of silence that follows a slam. "
            "The lamp threw the kind of yellow that makes you tired. "
            "The book smelled the kind of musty that old paper has. "
        )
        body += "The room was warm. The kettle had cooled. " * 600
        draft = _write_draft(book, body)
        findings = vc.validate_chapter(str(draft))
        violations = [f for f in findings if f.category == "book_rule_violation"]
        assert len(violations) >= 1

    def test_message_includes_occurrence_lines(self, tmp_path):
        """Block message should list line numbers + snippets so the user
        sees exactly which hits to cut."""
        book = self._book_with_limit_rule(tmp_path)
        _write_chapter_readme(book, 3200)
        body = "# Chapter 1\n\n"
        body += "She walked the kind of corridor that smelled like rain.\n\n"
        body += "He noticed the kind of silence that follows a slam.\n\n"
        body += "The lamp threw the kind of yellow that makes you tired.\n\n"
        body += "The book smelled the kind of musty that old paper has.\n\n"
        body += "The room was warm. The kettle had cooled. " * 175
        draft = _write_draft(book, body)
        findings = vc.validate_chapter(str(draft))
        violations = [f for f in findings if f.category == "book_rule_violation"]
        assert violations, "expected at least one violation"
        msg = violations[0].message
        assert "line 3" in msg
        assert "line 5" in msg or "line 7" in msg


# ---------------------------------------------------------------------------
# Mode resolution (strict vs warn)
# ---------------------------------------------------------------------------


class TestResolveMode:
    def test_default_is_strict_when_no_book_root(self, tmp_path):
        path = tmp_path / "loose-file.md"
        path.write_text("nothing", encoding="utf-8")
        assert vc._resolve_mode(path) == "strict"

    def test_default_is_strict_without_claudemd(self, tmp_path):
        book = _make_book(tmp_path)
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "strict"

    def test_default_is_strict_without_frontmatter(self, tmp_path):
        book = _make_book(tmp_path, claudemd_body="# Book\n\nNo frontmatter.\n")
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "strict"

    def test_warn_mode_via_frontmatter(self, tmp_path):
        body = "---\nlinter_mode: warn\n---\n\n# Book\n\n## Rules\n- Avoid `clocked`.\n"
        book = _make_book(tmp_path, claudemd_body=body)
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "warn"

    def test_strict_mode_explicit(self, tmp_path):
        body = '---\nlinter_mode: "strict"\n---\n\n# Book\n'
        book = _make_book(tmp_path, claudemd_body=body)
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "strict"

    def test_invalid_mode_falls_back_to_strict(self, tmp_path):
        body = "---\nlinter_mode: chaotic\n---\n\n# Book\n"
        book = _make_book(tmp_path, claudemd_body=body)
        draft = _write_draft(book, "# x\n")
        assert vc._resolve_mode(draft) == "strict"


# ---------------------------------------------------------------------------
# Hook entry point — JSON stdin protocol + exit codes
# ---------------------------------------------------------------------------


def _run_hook(payload: dict | None, monkeypatch, capsys) -> int:
    """Invoke vc.main() with a faked stdin/argv, return exit code."""
    if payload is None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    else:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    # Force isatty=False so _read_payload reads stdin
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(sys, "argv", ["validate_chapter.py"])
    return vc.main()


class TestMainEntryPoint:
    def test_no_payload_no_argv_returns_zero(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
        monkeypatch.setattr(sys, "argv", ["validate_chapter.py"])
        assert vc.main() == 0

    def test_unwatched_tool_is_ignored(self, monkeypatch, capsys):
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/anything/draft.md"},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_write_to_unrelated_file_is_ignored(self, monkeypatch, capsys):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/notes.md"},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_block_exit_2_in_strict_mode(self, tmp_path, monkeypatch, capsys):
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Rules\n- Avoid `clocked` as a verb.\n"),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the room and let his shoulders drop. "
                "The bag slid off the bench. He counted three breaths "
                "before he turned to face the door. " * 5
            ),
        )
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        captured = capsys.readouterr()
        assert rc == 2
        assert "blocked this write" in captured.err.lower()
        assert "clocked" in captured.err

    def test_warn_mode_does_not_block(self, tmp_path, monkeypatch, capsys):
        body = "---\nlinter_mode: warn\n---\n\n# Book\n\n## Rules\n- Avoid `clocked` as a verb.\n"
        book = _make_book(tmp_path, claudemd_body=body)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the room and let his shoulders drop. "
                "The bag slid off the bench. He counted three breaths "
                "before he turned to face the door. " * 5
            ),
        )
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 0

    def test_clean_prose_returns_zero(self, tmp_path, monkeypatch, capsys):
        book = _make_book(tmp_path)
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "The door slammed. She froze, one hand on the railing, "
                "the other clutching a paper bag from the Korean grocery "
                "on Seventh. Twenty-eight years of ignoring the prickle "
                "at the back of her neck. Tonight she listened. " * 5
            ),
        )
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(draft)},
        }
        rc = _run_hook(payload, monkeypatch, capsys)
        assert rc == 0


# ---------------------------------------------------------------------------
# Integration: invoke the hook script as a subprocess
# ---------------------------------------------------------------------------


class TestHookSubprocess:
    """Run the hook as Claude Code would — fresh process, JSON on stdin."""

    def _hook_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "hooks" / "validate_chapter.py"

    def test_strict_block_via_subprocess(self, tmp_path):
        book = _make_book(
            tmp_path,
            claudemd_body=("# Book\n\n## Rules\n- Avoid `clocked` as a verb.\n"),
        )
        draft = _write_draft(
            book,
            "# Chapter 1\n\n"
            + (
                "Theo clocked the room and let his shoulders drop. "
                "The bag slid off the bench. He counted three breaths "
                "before he turned to face the door. " * 5
            ),
        )
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(draft)}})
        result = subprocess.run(
            [sys.executable, str(self._hook_path())],
            input=payload,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 2, result.stderr
        assert "clocked" in result.stderr

    def test_unwatched_tool_subprocess(self, tmp_path):
        payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/x/draft.md"}})
        result = subprocess.run(
            [sys.executable, str(self._hook_path())],
            input=payload,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# validate_character — preserved from prior suite
# ---------------------------------------------------------------------------


class TestValidateCharacter:
    def test_ignores_non_character_files(self):
        assert validate_character("/some/other/file.md") == []

    def test_ignores_index(self):
        assert validate_character("/project/characters/INDEX.md") == []

    def test_valid_character(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text(
            '---\nname: "Alex"\nrole: "protagonist"\nstatus: "Concept"\n---\n\n'
            "# Alex\n\n## Want vs. Need\n\nContent.\n\n## Fatal Flaw\n\nContent.\n\n"
            "## The Ghost\n\nContent.\n\n## Motivation Chain\n\nContent.\n",
            encoding="utf-8",
        )
        assert validate_character(str(char_file)) == []

    def test_missing_frontmatter(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text("# Alex\n\nNo frontmatter here.\n", encoding="utf-8")
        issues = validate_character(str(char_file))
        assert any("Missing YAML frontmatter" in i for i in issues)

    def test_missing_required_sections(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "alex.md"
        char_file.write_text(
            '---\nname: "Alex"\nrole: "protagonist"\nstatus: "Concept"\n---\n\n# Alex\n\nNo required sections.\n',
            encoding="utf-8",
        )
        issues = validate_character(str(char_file))
        assert any("Want vs. Need" in i for i in issues)
        assert any("Fatal Flaw" in i for i in issues)

    def test_minor_characters_skip_sections(self, tmp_path):
        chars_dir = tmp_path / "project" / "characters"
        chars_dir.mkdir(parents=True)
        char_file = chars_dir / "barista.md"
        char_file.write_text(
            '---\nname: "Barista"\nrole: "minor"\nstatus: "Concept"\n---\n\n# Barista\n\nJust a minor character.\n',
            encoding="utf-8",
        )
        issues = validate_character(str(char_file))
        assert not any("Want vs. Need" in i for i in issues)
