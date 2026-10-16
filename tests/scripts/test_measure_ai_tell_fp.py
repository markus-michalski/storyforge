"""scripts/measure_ai_tell_fp.py — Issue #685.

The corpus the real measurement runs on is copyrighted and kept outside the
repository; these tests pin the script's behaviour on a small public-domain
excerpt and on synthetic text with known catalog hits.
"""

from __future__ import annotations

from pathlib import Path

import scripts.measure_ai_tell_fp as m

FIXTURE = Path(__file__).parent / "fixtures" / "pride_and_prejudice_ch1.txt"


def _entry(report: dict, label: str) -> dict:
    return next(e for e in report["entries"] if e["label"].lower() == label.lower())


class TestCountWords:
    def test_counts_words_not_punctuation(self):
        assert m.count_words("It is a truth, universally acknowledged -- Mr. Bennet's wife.") == 9


class TestPublicDomainFixture:
    def test_human_prose_triggers_no_catalog_entry(self):
        report = m.measure_texts([FIXTURE.read_text(encoding="utf-8")])
        assert report["words"] > 300
        assert report["catalog_hits"] == 0
        assert report["overall_per_5k"] == 0.0
        assert m.flagged_entries(report, entry_bar=m.DEFAULT_ENTRY_BAR) == []
        assert not m.exceeds_bars(report, entry_bar=m.DEFAULT_ENTRY_BAR, overall_bar=m.DEFAULT_OVERALL_BAR)

    def test_every_loaded_entry_is_reported_even_without_hits(self):
        report = m.measure_texts([FIXTURE.read_text(encoding="utf-8")])
        categories = {e["category"] for e in report["entries"]}
        assert categories == {"shape", "vocabulary"}
        assert len(report["entries"]) > 50


class TestKnownHits:
    TEXT = (
        "She decided to delve into the archive. The tapestry hung on the far wall. "
        "Later they would delve deeper. A plain sentence about nothing at all."
    )

    def test_counts_and_rates_per_entry(self):
        report = m.measure_texts([self.TEXT])
        assert _entry(report, "Delve")["hits"] == 2
        assert _entry(report, "Tapestry")["hits"] == 1
        assert report["words"] == 26
        assert _entry(report, "Delve")["per_5k"] == round(2 / 26 * 5000, 3)

    def test_bars(self):
        report = m.measure_texts([self.TEXT])
        assert [e["label"] for e in m.flagged_entries(report, entry_bar=0.1)][0] == "Delve"
        assert m.exceeds_bars(report, entry_bar=0.1, overall_bar=1.0)
        assert not m.exceeds_bars(report, entry_bar=1e9, overall_bar=1e9)

    def test_rates_are_pooled_over_all_texts(self):
        report = m.measure_texts([self.TEXT, "Nothing to see here, just ordinary words and more of them."])
        assert _entry(report, "Delve")["hits"] == 2
        assert report["words"] == 26 + 11


class TestNarrowedEntries:
    def test_abstract_constructions_hit_but_literal_use_does_not(self):
        literal = "It was a long journey. She was rich. He felt the rich soil. The landscape was bare. He did embrace her."
        abstract = "A journey toward self-discovery. Rich with meaning. Embrace the change. The landscape of politics."
        assert m.measure_texts([literal])["catalog_hits"] == 0
        report = m.measure_texts([abstract])
        for label in ("Journey toward", "Rich with", "Embrace the", "Landscape of"):
            assert _entry(report, label)["hits"] == 1


class TestSceneSplitAndDensity:
    def test_split_scenes_cuts_at_paragraph_boundaries(self):
        text = "\n\n".join(["one two three four five"] * 10)
        pieces = m.split_scenes(text, target_words=12)
        assert len(pieces) == 4
        assert all("\n\n" in p or p.count("one") == 1 for p in pieces)
        assert "\n\n".join(pieces) == text

    def test_density_rules_are_reported_apart_from_the_catalog_figures(self):
        scene = "It seemed odd. It seemed late. It seemed over. It seemed done."
        report = m.measure_texts([scene])
        hedge = next(e for e in report["density_entries"] if e["label"].startswith("11.10"))
        assert hedge["hits"] > 0
        assert report["catalog_hits"] == 0
        assert not m.exceeds_bars(report, entry_bar=0.1, overall_bar=1.0)
        assert m.exceeds_bars(report, entry_bar=0.1, overall_bar=1.0, include_density=True)


class TestMain:
    def test_report_written_and_check_exit_codes(self, tmp_path):
        (tmp_path / "ok.txt").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        out = tmp_path / "report.md"
        assert m.main([str(tmp_path), "--output", str(out), "--check"]) == 0
        assert "# AI-tell catalog false-positive report" in out.read_text(encoding="utf-8")

        (tmp_path / "bad.txt").write_text(TestKnownHits.TEXT, encoding="utf-8")
        assert m.main([str(tmp_path), "--output", str(out), "--check"]) == 1
        assert m.main([str(tmp_path), "--output", str(out)]) == 0

    def test_language_without_catalog_is_an_error(self, tmp_path):
        (tmp_path / "a.txt").write_text("Ein Satz.", encoding="utf-8")
        assert m.main([str(tmp_path), "--language", "de"]) == 2

    def test_empty_corpus_is_an_error(self, tmp_path):
        assert m.main([str(tmp_path)]) == 2
