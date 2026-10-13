"""Drift guard: every finding `category` the manuscript-checker scanners can
emit must have a row in the matching SKILL.md's "## Detection categories"
table (Issue #642).

#642 found five categories emitted by `tools/analysis/manuscript/rules.py` —
`author_rule_violation`, `author_vocab_violation`, `writing_discovery_violation`,
`global_shape_violation`, `ai_tell_violation` — present in the scanner but
absent from both `skills/manuscript-checker/SKILL.md` and
`skills/manuscript-checker-memoir/SKILL.md`'s category tables and priority
lists, left undocumented with no severity rule, sort position, or fix
guidance for the interactive walkthrough. The table-row guard below is
general (any future new category needs a row, in whichever skill(s) its
scanner actually runs for). The interactive-walkthrough priority-list check
is intentionally scoped to just these 5 categories, not a general "every
category needs an explicit priority-list mention" guard — see
`test_642_categories_in_fiction_priority_list`'s docstring for why.

Design notes:

- Category extraction uses the ``ast`` module, not text regexes, so docstrings
  and comments that happen to contain ``category='...'`` (several scanner
  functions document their own category in prose) never count as an
  emission, and a category literal containing a digit isn't silently
  skipped by a hand-rolled charset.
- The source-file set is discovered via ``glob("*.py")`` over the scanner
  package, not a hand-maintained list — a new scanner module is picked up
  automatically instead of silently bypassing this guard (the same
  "detection over lists" principle this plugin's own tooling follows
  elsewhere).
- Which scanners are memoir-only is derived from `__init__.py`'s own
  ``if book_category == "memoir":`` block — the actual gate — rather than
  hard-coded as "whatever's in memoir_patterns.py". A function called from
  that block whose defining module isn't on the known-memoir-module
  allowlist fails loudly, rather than being silently miscategorized.
- The emitted-category set is cross-checked against
  ``renderer.CATEGORY_LABELS`` — a second, independently hand-maintained
  registry already required for every category to render with a real
  heading instead of a fallback — so this test also catches a new category
  that has a doc row but no render label, or vice versa.
- "Documented" means "has its own first-column table cell", not "any
  backtick-wrapped word anywhere in the section" — the table's second
  column (free prose) mentions plenty of other backtick-wrapped identifiers
  (`source_rule`, `occurrences`, a `plot_hole` sub-category like
  `chekhov_gun`) that must NOT count as a documented top-level category.
- A non-vacuity floor asserts a known baseline is still found, so a future
  refactor that breaks the AST walk (e.g. categories moved behind a
  lookup table or a shared constant) fails this test immediately instead of
  this guard quietly starting to pass everything.
"""

from __future__ import annotations

import ast
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
MANUSCRIPT_DIR = PLUGIN_ROOT / "tools" / "analysis" / "manuscript"
FICTION_SKILL = PLUGIN_ROOT / "skills" / "manuscript-checker" / "SKILL.md"
MEMOIR_SKILL = PLUGIN_ROOT / "skills" / "manuscript-checker-memoir" / "SKILL.md"

# Scanner modules allowed to feed the memoir-only branch of __init__.py's
# `if book_category == "memoir":` gate. A function called from that branch
# whose defining module isn't here fails the test loudly (see
# `_discover_memoir_only_categories`), instead of this guard silently
# misclassifying a new memoir scanner as "shared".
_KNOWN_MEMOIR_MODULES = {"memoir_patterns.py"}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _str_constant(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _categories_from_finding_calls(node: ast.AST) -> set[str]:
    """Every string-literal `category=` keyword on a `Finding(...)` call
    anywhere under `node` (a module, or a single FunctionDef to scope the
    search to one scanner).
    """
    cats: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "Finding":
            for kw in sub.keywords:
                if kw.arg == "category":
                    val = _str_constant(kw.value)
                    if val:
                        cats.add(val)
    return cats


def _categories_from_classify(tree: ast.Module) -> set[str]:
    """`types._classify()` builds its result via `return "<category>"`, not
    a `category=` keyword, so it flows into `Finding(category=category, ...)`
    in `__init__.py` as a dynamic value the function-call walk above can't
    see. Collect its literal returns directly, scoped to that one function so
    an unrelated `return "..."` elsewhere in the module can't leak in.
    """
    cats: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_classify":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return):
                    val = _str_constant(sub.value)
                    if val:
                        cats.add(val)
    return cats


def _top_level_function_names(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def _discover_memoir_only_categories() -> set[str]:
    """Walk `__init__.py`'s own `if book_category == "memoir":` block to find
    which `_scan_*` calls it gates, verify each is defined in a module on the
    known-memoir allowlist, then return the categories those specific
    functions emit.
    """
    init_tree = _parse(MANUSCRIPT_DIR / "__init__.py")

    memoir_if: ast.If | None = None
    for node in ast.walk(init_tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            comparators = [c for c in node.test.comparators if _str_constant(c) == "memoir"]
            if comparators:
                memoir_if = node
                break
    assert memoir_if is not None, (
        '__init__.py no longer has an `if book_category == "memoir":` gate — '
        "this test's memoir/shared split depends on finding it there."
    )

    called_names: set[str] = set()
    for sub in ast.walk(memoir_if):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            called_names.add(sub.func.id)
    assert called_names, "found the memoir gate but no _scan_* calls inside it"

    owner_module: dict[str, str] = {}
    function_nodes: dict[str, ast.FunctionDef] = {}
    for py_file in MANUSCRIPT_DIR.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        tree = _parse(py_file)
        for name, node in _top_level_function_names(tree).items():
            owner_module[name] = py_file.name
            function_nodes[name] = node

    memoir_only_categories: set[str] = set()
    for name in called_names:
        owner = owner_module.get(name)
        assert owner in _KNOWN_MEMOIR_MODULES, (
            f"__init__.py's memoir gate now calls `{name}`, defined in "
            f"`{owner}` — not on the known-memoir-module allowlist "
            f"({sorted(_KNOWN_MEMOIR_MODULES)}). Either this is a genuinely "
            f"new memoir-only scanner module (add it to that allowlist) or "
            f"this test's discovery logic needs a second look."
        )
        memoir_only_categories |= _categories_from_finding_calls(function_nodes[name])

    return memoir_only_categories


def _emitted_categories() -> tuple[set[str], set[str]]:
    """Returns (shared_categories, memoir_only_categories)."""
    memoir_only = _discover_memoir_only_categories()

    all_emitted: set[str] = set()
    for py_file in MANUSCRIPT_DIR.glob("*.py"):
        tree = _parse(py_file)
        all_emitted |= _categories_from_finding_calls(tree)
        if py_file.name == "types.py":
            all_emitted |= _categories_from_classify(tree)

    return all_emitted - memoir_only, memoir_only


def _table_row_categories(section_text: str) -> set[str]:
    """Backtick-wrapped tokens from the FIRST column only of each `|`-table
    row — not the whole section — so prose in the "What it catches" column
    (`source_rule`, `occurrences`, a `plot_hole` sub-category like
    `chekhov_gun`) never counts as its own documented category.
    """
    cats: set[str] = set()
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = stripped.split("|")
        if len(cells) < 2:
            continue
        first_cell = cells[1]
        if set(first_cell.strip()) <= {"-"}:  # the `|---|---|` separator row
            continue
        cats |= {tok for tok in _find_backtick_tokens(first_cell)}
    return cats


def _find_backtick_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    parts = text.split("`")
    # split("`") on "`a` / `b`" -> ['', 'a', ' / ', 'b', ''] — odd indices are
    # the backtick-wrapped content.
    for i in range(1, len(parts), 2):
        token = parts[i].strip()
        if token and all(c.isalnum() or c == "_" for c in token):
            tokens.add(token)
    return tokens


def _detection_categories_section(skill_md_path: Path) -> str:
    text = skill_md_path.read_text(encoding="utf-8")
    start = text.find("## Detection categories")
    assert start != -1, f"{skill_md_path} has no '## Detection categories' section"
    end = text.find("\n## ", start + len("## Detection categories"))
    assert end != -1, f"{skill_md_path}: '## Detection categories' section never ends (no following '## ')"
    return text[start:end]


def _documented_categories(skill_md_path: Path) -> set[str]:
    return _table_row_categories(_detection_categories_section(skill_md_path))


def _priority_list_categories(skill_md_path: Path) -> set[str]:
    text = skill_md_path.read_text(encoding="utf-8")
    marker = "Process findings in **category priority order**:"
    start = text.find(marker)
    assert start != -1, f"{skill_md_path} has no 'category priority order' walkthrough list"
    body_start = start + len(marker)
    lines = text[body_start:].splitlines()
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":  # blank line(s) before the list starts
        idx += 1
    block_lines: list[str] = []
    for line in lines[idx:]:
        if line.strip() == "":
            break
        block_lines.append(line)
    return _find_backtick_tokens("\n".join(block_lines))


class TestManuscriptCheckerCategoryCoverage:
    def test_emitted_categories_match_renderer_labels(self) -> None:
        """Independent second source: renderer.CATEGORY_LABELS is already a
        hand-maintained, exhaustive category registry — every emitted
        category needs a label there to render with a real heading instead
        of a fallback. Any mismatch here means either a scanner category has
        no render label, or a render label exists for a category nothing
        emits any more.
        """
        from tools.analysis.manuscript.renderer import CATEGORY_LABELS

        shared, memoir_only = _emitted_categories()
        emitted = shared | memoir_only
        labeled = set(CATEGORY_LABELS.keys())
        assert emitted == labeled, (
            f"emitted-but-unlabeled: {sorted(emitted - labeled)}; "
            f"labeled-but-never-emitted: {sorted(labeled - emitted)}"
        )

    def test_non_vacuity_floor(self) -> None:
        """If a refactor ever breaks the AST walk above (e.g. categories
        moved behind a shared constant or a lookup table instead of a
        literal `category=` keyword), `shared`/`memoir_only` would silently
        shrink and every assertion below would start passing vacuously. Pin
        a known baseline so that failure mode is loud instead of quiet.
        """
        shared, memoir_only = _emitted_categories()
        known_shared_baseline = {
            "book_rule_violation",
            "author_rule_violation",
            "author_vocab_violation",
            "writing_discovery_violation",
            "global_shape_violation",
            "ai_tell_violation",
            "plot_hole",
            "cliche",
            "simile",
            "character_tell",
            "blocking_tic",
            "sensory",
            "structural",
            "signature_phrase",
        }
        assert known_shared_baseline <= shared, (
            f"missing from shared-category extraction: {sorted(known_shared_baseline - shared)} "
            f"— category extraction may have regressed"
        )
        assert memoir_only, "memoir-only category extraction returned nothing — likely broken"

    def test_shared_categories_documented_in_fiction_skill(self) -> None:
        shared, _ = _emitted_categories()
        documented = _documented_categories(FICTION_SKILL)
        missing = shared - documented
        assert not missing, (
            f"skills/manuscript-checker/SKILL.md's Detection categories table is "
            f"missing a row for: {sorted(missing)} (Issue #642)."
        )

    def test_shared_categories_documented_in_memoir_skill(self) -> None:
        shared, _ = _emitted_categories()
        documented = _documented_categories(MEMOIR_SKILL)
        missing = shared - documented
        assert not missing, (
            f"skills/manuscript-checker-memoir/SKILL.md's Detection categories "
            f"table is missing a row for: {sorted(missing)} — these scanners run "
            f"unconditionally (before the book_category == 'memoir' branch in "
            f"tools/analysis/manuscript/__init__.py), so they apply to memoir "
            f"books too (Issue #642)."
        )

    def test_memoir_only_categories_documented_in_memoir_skill(self) -> None:
        _, memoir_only = _emitted_categories()
        documented = _documented_categories(MEMOIR_SKILL)
        missing = memoir_only - documented
        assert not missing, (
            f"skills/manuscript-checker-memoir/SKILL.md is missing a row for memoir-only categories: {sorted(missing)}"
        )

    def test_memoir_only_categories_absent_from_fiction_skill(self) -> None:
        """memoir_patterns.py scanners never run for a fiction book (gated on
        book_category == "memoir" in __init__.py), so the fiction skill
        documenting one of these would itself be a drift bug in the other
        direction — it would promise behavior that Step 0's fiction-mode
        gate never delivers.
        """
        _, memoir_only = _emitted_categories()
        documented = _documented_categories(FICTION_SKILL)
        stray = memoir_only & documented
        assert not stray, (
            f"skills/manuscript-checker/SKILL.md documents memoir-only "
            f"categories that never fire for a fiction book: {sorted(stray)}"
        )

    def test_642_categories_in_fiction_priority_list(self) -> None:
        """Scoped to the 5 categories #642 was actually filed about, not a
        general "every category must have an explicit priority-list
        mention" guard: the walkthrough's existing "Repetition categories
        (`simile`, `character_tell`, etc.)" convention deliberately lumps
        several n-gram categories under one "etc." entry, and several other
        pre-existing categories (`plot_hole`, the callback categories,
        `snapshot`, `sentence_repetition`) were never individually listed
        there either — a separate, pre-existing documentation gap outside
        #642's scope, not something this fix should silently paper over by
        either fixing unrelated gaps or weakening this guard to tolerate
        "etc." everywhere.
        """
        new_categories = {
            "author_rule_violation",
            "author_vocab_violation",
            "writing_discovery_violation",
            "global_shape_violation",
            "ai_tell_violation",
        }
        listed = _priority_list_categories(FICTION_SKILL)
        missing = new_categories - listed
        assert not missing, (
            f"skills/manuscript-checker/SKILL.md's interactive-walkthrough "
            f"'category priority order' list is missing: {sorted(missing)} "
            f"(Issue #642's suggested fix direction asked for priority "
            f"placement, not just a table row)."
        )

    def test_642_categories_in_memoir_priority_list(self) -> None:
        """See test_642_categories_in_fiction_priority_list — same scoping
        rationale applies to the memoir skill's walkthrough list.
        """
        new_categories = {
            "author_rule_violation",
            "author_vocab_violation",
            "writing_discovery_violation",
            "global_shape_violation",
            "ai_tell_violation",
        }
        listed = _priority_list_categories(MEMOIR_SKILL)
        missing = new_categories - listed
        assert not missing, (
            f"skills/manuscript-checker-memoir/SKILL.md's interactive-walkthrough "
            f"'category priority order' list is missing: {sorted(missing)}"
        )
