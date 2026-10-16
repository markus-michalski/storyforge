#!/usr/bin/env python3
"""Measure how often the English AI-tell catalog fires on human-written prose.

Runs every enforced entry of ``reference/craft/anti-ai-patterns.md`` — the
Section 1 vocabulary (as compiled by ``load_global_ai_tells``), the Section 11
``**Banned shape:**`` regexes (``load_global_shape_bans``) and the scanner's
per-scene Section 11 density rules (11.5 near-miss, 11.9 negation loop, 11.10
hedge density, 11.13 repeated openers) — over a corpus of plain-text files
through the same ``scan_draft`` the chapter-humanizer uses, and reports hits
per 5,000 words, overall and per entry. The density rules are listed in their
own section and only count toward ``--check`` with ``--include-density``.

The density rules are per-scene, and a plain-text conversion has no scene
breaks, so each text is cut into scene-sized pieces (``SCENE_WORDS``, at
paragraph boundaries) before scanning; scanning a whole novel as one scene
would flag nearly everything. Shape lines the loader does not pick up (the
11.6 trust-split line has no ``**Banned shape:**`` marker) are not measured.

The corpus is supplied by the caller and stays outside the repository; convert
e-books first, e.g. ``pandoc book.epub -t plain --wrap=none -o book.txt``.
Re-run after editing the catalog::

    python scripts/measure_ai_tell_fp.py CORPUS_DIR [--entry-bar 0.1] [--overall-bar 1.0]

Exit code 1 means at least one bar was exceeded (``--check``); without it the
script only reports.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools.analysis.humanizer_scan import load_patterns, scan_draft  # noqa: E402

WORDS_PER_UNIT = 5000
DEFAULT_OVERALL_BAR = 1.0  # hits per 5,000 words, all catalog entries together
DEFAULT_ENTRY_BAR = 0.1  # hits per 5,000 words for a single entry (about one per 50,000 words)
SCENE_WORDS = 1200  # typical scene length the density rules are tuned for
CATALOG_CATEGORIES = ("shape", "vocabulary")
DENSITY_CATEGORIES = {
    "near_miss": "11.5 near-miss body language",
    "negation_loop": "11.9 negation-as-assertion loop",
    "hedge_density": "11.10 hedge-word density",
    "repeated_openers": "11.13 repeated sentence openers",
}

_WORD_RE = re.compile(r"[^\W_][\w'’-]*", re.UNICODE)


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def split_scenes(text: str, target_words: int = SCENE_WORDS) -> list[str]:
    """Cut ``text`` into pieces of about ``target_words`` words at paragraph boundaries."""
    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in re.split(r"\n\s*\n", text):
        current.append(paragraph)
        size += count_words(paragraph)
        if size >= target_words:
            pieces.append("\n\n".join(current))
            current, size = [], 0
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def corpus_files(corpus: Path) -> list[Path]:
    if corpus.is_file():
        return [corpus]
    return sorted(p for p in corpus.rglob("*.txt") if p.is_file())


def measure_texts(
    texts: list[str],
    *,
    plugin_root: Path = PLUGIN_ROOT,
    language: str = "en",
) -> dict[str, Any]:
    """Hit counts per catalog entry over ``texts``.

    Every loaded entry appears in ``entries`` — also those that never fired —
    keyed ``(category, label)`` and carrying ``hits`` plus ``per_5k``.
    """
    shapes, tells, _author = load_patterns(plugin_root, None, language=language)
    counts: Counter[tuple[str, str]] = Counter()
    other: Counter[str] = Counter()
    density: Counter[str] = Counter()
    total_words = 0
    for text in texts:
        total_words += count_words(text)
        for scene in split_scenes(text):
            result = scan_draft(scene, global_shapes=shapes, global_tells=tells, author_patterns=[], language=language)
            for hit in result["hits"]:
                if hit["category"] in CATALOG_CATEGORIES:
                    counts[(hit["category"], hit["label"])] += 1
                elif hit["category"] in DENSITY_CATEGORIES:
                    density[hit["category"]] += 1
                else:
                    other[hit["category"]] += 1

    def per_5k(hits: int) -> float:
        return round(hits / total_words * WORDS_PER_UNIT, 3) if total_words else 0.0

    entries = []
    for category, group in (("shape", shapes), ("vocabulary", tells)):
        for pattern in group:
            hits = counts.get((category, pattern.label), 0)
            entries.append({"category": category, "label": pattern.label, "hits": hits, "per_5k": per_5k(hits)})
    density_entries = []
    if shapes or tells:  # a language without a catalog has no density rules to report either
        for category, label in DENSITY_CATEGORIES.items():
            density_entries.append(
                {"category": "density", "label": label, "hits": density[category], "per_5k": per_5k(density[category])}
            )
    catalog_hits = sum(e["hits"] for e in entries)
    return {
        "words": total_words,
        "files": len(texts),
        "entries": entries,
        "density_entries": density_entries,
        "catalog_hits": catalog_hits,
        "overall_per_5k": per_5k(catalog_hits),
        "other_hits": dict(other),
    }


def flagged_entries(report: dict[str, Any], entry_bar: float, *, include_density: bool = False) -> list[dict[str, Any]]:
    pool = report["entries"] + (report["density_entries"] if include_density else [])
    return sorted(
        (e for e in pool if e["per_5k"] > entry_bar),
        key=lambda e: e["per_5k"],
        reverse=True,
    )


def format_report(report: dict[str, Any], *, entry_bar: float, overall_bar: float) -> str:
    flagged = flagged_entries(report, entry_bar)
    density_total = sum(e["hits"] for e in report["density_entries"])
    lines = [
        "# AI-tell catalog false-positive report",
        "",
        f"- Corpus: {report['files']} files, {report['words']:,} words",
        f"- Catalog hits: {report['catalog_hits']} "
        f"({report['overall_per_5k']} per {WORDS_PER_UNIT:,} words; overall bar {overall_bar})",
        f"- Entries: {len(report['entries'])}, above the per-entry bar ({entry_bar} per "
        f"{WORDS_PER_UNIT:,} words): {len(flagged)}",
    ]
    if report["other_hits"]:
        other = ", ".join(f"{k}: {v}" for k, v in sorted(report["other_hits"].items()))
        lines.append(f"- Non-catalog scanner categories (e.g. invisible characters; not part of this report): {other}")
    lines.append(
        f"- Per-scene density rules (reported separately, not in the figures above): {density_total} hits "
        f"({round(density_total / report['words'] * WORDS_PER_UNIT, 3) if report['words'] else 0.0} per "
        f"{WORDS_PER_UNIT:,} words)"
    )
    lines += ["", "## Entries above the bar", ""]
    if flagged:
        lines += ["| Category | Entry | Hits | Per 5k words |", "|---|---|---:|---:|"]
        lines += [f"| {e['category']} | `{e['label']}` | {e['hits']} | {e['per_5k']} |" for e in flagged]
    else:
        lines.append("None.")
    lines += ["", "## All entries", "", "| Category | Entry | Hits | Per 5k words |", "|---|---|---:|---:|"]
    ranked = sorted(report["entries"], key=lambda e: (-e["hits"], e["category"], e["label"]))
    lines += [f"| {e['category']} | `{e['label']}` | {e['hits']} | {e['per_5k']} |" for e in ranked]
    lines += [
        "",
        f"## Per-scene density rules (scenes of about {SCENE_WORDS} words)",
        "",
        "| Rule | Hits | Per 5k words |",
        "|---|---:|---:|",
    ]
    lines += [f"| {e['label']} | {e['hits']} | {e['per_5k']} |" for e in report["density_entries"]]
    return "\n".join(lines) + "\n"


def exceeds_bars(
    report: dict[str, Any], *, entry_bar: float, overall_bar: float, include_density: bool = False,
) -> bool:
    return report["overall_per_5k"] > overall_bar or bool(
        flagged_entries(report, entry_bar, include_density=include_density)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure AI-tell catalog hits on human-written prose")
    parser.add_argument("corpus", type=Path, help="directory of .txt files (or one file) of human-written prose")
    parser.add_argument("--entry-bar", type=float, default=DEFAULT_ENTRY_BAR)
    parser.add_argument("--overall-bar", type=float, default=DEFAULT_OVERALL_BAR)
    parser.add_argument("--language", default="en")
    parser.add_argument("--output", type=Path, help="write the report here instead of stdout")
    parser.add_argument("--check", action="store_true", help="exit 1 when a bar is exceeded")
    parser.add_argument(
        "--include-density", action="store_true", help="also hold the per-scene density rules to --entry-bar"
    )
    args = parser.parse_args(argv)

    files = corpus_files(args.corpus)
    if not files:
        print(f"No .txt files found under {args.corpus}", file=sys.stderr)
        return 2
    if not any(load_patterns(PLUGIN_ROOT, None, language=args.language)[:2]):
        print(f"No AI-tell catalog for language {args.language!r}", file=sys.stderr)
        return 2
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in files]
    report = measure_texts(texts, language=args.language)
    out = format_report(report, entry_bar=args.entry_bar, overall_bar=args.overall_bar)
    if args.output:
        args.output.write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
    if args.check and exceeds_bars(
        report, entry_bar=args.entry_bar, overall_bar=args.overall_bar, include_density=args.include_density
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
