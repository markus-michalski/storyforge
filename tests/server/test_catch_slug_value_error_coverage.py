"""Coverage sweep for the #523 fix.

catch_slug_value_error() (tools/shared/paths.py) converts an escaping
SlugValidationError from slug validation into this codebase's standard
{"error": ...} JSON response. It's applied by hand to individual MCP tool
functions across router modules — a mechanical, easy-to-silently-regress
wiring. This module is the safety net, in two layers:

1. DECORATED_FUNCTIONS: an explicit list, asserted (as a batch and
   individually-parametrized) to carry the decorator. Catches the decorator
   being REMOVED from a known call site — and names the exact function in
   a failure.

2. test_no_undecorated_resolver_call_site_exists: a source-derived AST scan
   of every router module, independent of the hardcoded list above. Finds
   every @mcp.tool function that calls a slug-validating resolve_*_path()
   helper — directly, or transitively through a same-module private
   helper — and asserts it's either decorated or explicitly listed in
   KNOWN_EXEMPT with a reason. Catches a call site that was MISSED by the
   original fix, or a brand-NEW call site added later without the
   decorator — neither of which layer 1 can detect, since it only knows
   about functions someone remembered to add to its list.

Not covered here: three routers/series.py functions
(`write_series_evolution_section`, `read_tracker_for_bootstrap`,
`create_character_tracker` — all three ARE in DECORATED_FUNCTIONS and
decorated for their `series_slug` param) whose separate `tracker_slug`/
`slug` parameter reaches Path construction with no validation at all
(issue #524, still open) — a different bug shape than what this decorator
addresses, since there's no SlugValidationError to catch until that
parameter is validated in the first place.

`get_idea`/`update_idea`/`promote_idea` (routers/ideas.py) are in
DECORATED_FUNCTIONS (layer 1) but NOT reachable by the layer-2 AST scan —
they validate via `_idea_path()`, a local helper, not one of the
`resolve_*_path()` names in RESOLVER_NAMES. Layer 1 still catches a
regression that removes their decorator; a brand-new undecorated call site
built the same way (a raw f-string Path join validated by something other
than a listed resolver) is covered by layer 3, below (issue #531).

Layer 3 (`test_no_unvalidated_slug_path_join_in_tool_body`, issue #531) is
a different AST sweep entirely — it doesn't care about RESOLVER_NAMES or
the decorator at all. It flags a raw `some_dir / slug` or `some_dir /
f"{slug}..."` Path-join expression built directly inside an @mcp.tool
function's own body, with no `_validate_slug()` call on that parameter
anywhere in the function. This is the bug shape #524 was (three
routers/series.py functions, since fixed — this sweep now stays green
there) and issue #538 partially is (routers/gates.py's validate_chapter;
see that test's own docstring for why it only catches one of #538's four
sites).

DECORATED_FUNCTIONS covers three merged commits: the memoir/idea
path-traversal security fix (read_character_for_harvest,
update_character_snapshot, get_idea, update_idea, promote_idea), the
41-site MCP rollout, and resolve_path (routers/state.py, issue #521 —
book_slug reached resolve_project_path() before this function's own
try/except, so an invalid book_slug raised unhandled instead of
returning a clean error).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from routers.authors import harvest_book_rules, update_author
from routers.books import count_words, get_book_progress, get_canon_brief
from routers.canon import add_canon_fact
from routers.chapters import (
    get_chapter_promises,
    get_chapter_writing_brief,
    get_continuity_brief,
    get_current_story_anchor,
    get_recent_chapter_timelines,
    get_review_brief,
    register_chapter_promises,
    start_chapter_draft,
    verify_tactical_setup,
)
from routers.claudemd import (
    get_book_claudemd,
    init_book_claudemd,
    lint_book_rules,
    list_book_rules,
    update_character_snapshot,
)
from routers.creation import create_chapter, create_character
from routers.gates import (
    analyze_plot_logic,
    check_memoir_consent,
    run_pre_export_gates,
    run_quality_gates,
    scan_manuscript,
    validate_book_structure,
    validate_chapter,
    validate_timeline_consistency,
    verify_callbacks,
)
from routers.ideas import get_idea, promote_idea, update_idea
from routers.memoir import create_person, set_memoir_structure_type
from routers.scenes import create_scene_list, update_scene
from routers.series import (
    add_book_to_series,
    bootstrap_character_for_new_book,
    copy_recurring_chars_to_new_book,
    create_character_tracker,
    list_series_trackers_for_book,
    read_character_for_harvest,
    read_tracker_for_bootstrap,
    write_series_evolution_section,
)
from routers.state import resolve_path

DECORATED_FUNCTIONS = [
    count_words,
    get_canon_brief,
    get_book_progress,
    get_recent_chapter_timelines,
    verify_tactical_setup,
    get_chapter_writing_brief,
    get_review_brief,
    get_continuity_brief,
    start_chapter_draft,
    register_chapter_promises,
    get_chapter_promises,
    get_current_story_anchor,
    scan_manuscript,
    validate_timeline_consistency,
    verify_callbacks,
    check_memoir_consent,
    analyze_plot_logic,
    validate_chapter,
    validate_book_structure,
    run_quality_gates,
    run_pre_export_gates,
    add_canon_fact,
    create_scene_list,
    update_scene,
    init_book_claudemd,
    get_book_claudemd,
    list_book_rules,
    lint_book_rules,
    update_character_snapshot,
    add_book_to_series,
    read_character_for_harvest,
    list_series_trackers_for_book,
    write_series_evolution_section,
    copy_recurring_chars_to_new_book,
    read_tracker_for_bootstrap,
    bootstrap_character_for_new_book,
    create_character_tracker,
    create_chapter,
    create_character,
    harvest_book_rules,
    update_author,
    create_person,
    set_memoir_structure_type,
    get_idea,
    update_idea,
    promote_idea,
    resolve_path,
]


class TestCatchSlugValueErrorCoverage:
    def test_all_intended_call_sites_are_decorated(self) -> None:
        undecorated = [
            fn.__qualname__ for fn in DECORATED_FUNCTIONS if not getattr(fn, "_catches_slug_value_error", False)
        ]
        assert not undecorated, f"Missing @catch_slug_value_error on: {undecorated}"

    def test_sweep_list_has_no_duplicates(self) -> None:
        names = [fn.__qualname__ for fn in DECORATED_FUNCTIONS]
        assert len(names) == len(set(names))

    @pytest.mark.parametrize("fn", DECORATED_FUNCTIONS, ids=lambda fn: fn.__qualname__)
    def test_each_function_individually(self, fn) -> None:
        """Parametrized so a failure names the exact function, not just the batch."""
        assert getattr(fn, "_catches_slug_value_error", False) is True


# ---------------------------------------------------------------------------
# Source-derived sweep — layer 2 (catches missed / new call sites)
# ---------------------------------------------------------------------------

ROUTERS_DIR = Path(__file__).resolve().parent.parent.parent / "servers" / "storyforge-server" / "routers"

# Resolvers that call _validate_slug() and can raise SlugValidationError.
# find_chapters() also validates (it calls resolve_project_path()
# internally) — included so a future tool calling only find_chapters,
# without going through one of the other resolvers too, doesn't evade
# this scan (issue #523 code review, finding N-4).
RESOLVER_NAMES = {
    "resolve_project_path",
    "resolve_chapter_path",
    "resolve_character_path",
    "resolve_person_path",
    "resolve_series_path",
    "resolve_author_path",
    "resolve_book_in_series_path",
    "find_chapters",
}

# (module_stem, function_name) -> reason it's safe without the decorator.
# Every entry here must have a concrete, checked reason — "seems fine" is
# not a reason. Re-verify each entry whenever this test starts failing on
# it, rather than reflexively adding more exemptions.
KNOWN_EXEMPT = {
    # Slug is produced by slugify() from arbitrary user text, which strips
    # every character _validate_slug() rejects (/, \, \x00, .., leading
    # dot) — the resolver call can structurally never raise.
    ("series", "create_series"): "slug is slugify()-derived, cannot fail validation",
    ("authors", "create_author"): "slug is slugify()-derived, cannot fail validation",
    # Already has its own manual try/except ValueError around the
    # resolve_series_path call (predates #523; confirmed in code review).
    ("creation", "create_book_structure"): "has its own try/except ValueError already",
    # These six already wrap resolve_author_path() in their own local
    # try/except (KeyError, ValueError), individually verified in code —
    # the AST scan can't see that (it only checks "does this function call
    # a resolver", not "is that specific call already caught locally"), so
    # it flags them as false positives. Matches issue #523's own audit,
    # which named this exact set of six as already-handled.
    ("authors", "delete_author"): "wraps resolve_author_path in local try/except (KeyError, ValueError)",
    ("authors", "write_author_discovery"): "wraps resolve_author_path in local try/except (KeyError, ValueError)",
    ("authors", "write_author_banned_phrase"): "wraps resolve_author_path in local try/except (KeyError, ValueError)",
    ("authors", "update_discovery_metadata"): "wraps resolve_author_path in local try/except (KeyError, ValueError)",
    ("authors", "add_vocabulary_entry"): "wraps resolve_author_path in local try/except (KeyError, ValueError)",
    ("authors", "delete_discovery"): "wraps resolve_author_path in local try/except (KeyError, ValueError)",
    # These five reach resolve_project_path() indirectly, through helper
    # functions in tools/claudemd/manager.py rather than a same-module
    # helper — the AST scan's transitive-call BFS only follows same-module
    # functions, so it can't see this route at all (a real blind spot,
    # tracked as issue #523 code review finding N-3). Each already wraps
    # its call to the manager helper in a local except clause that includes
    # ValueError, individually verified in code.
    ("claudemd", "append_book_rule"): "via manager.py, caught by local except (FileNotFoundError, ValueError)",
    ("claudemd", "update_book_rule"): "via manager.py, caught by local except ValueError (code: invalid_args)",
    ("claudemd", "append_book_workflow"): "via manager.py, caught by local except (FileNotFoundError, ValueError)",
    ("claudemd", "append_book_callback"): "via manager.py, caught by local except (FileNotFoundError, ValueError)",
    (
        "claudemd",
        "sync_book_claudemd_from_text",
    ): "via manager.py, caught by local except (FileNotFoundError, ValueError)",
}


def _router_modules() -> list[Path]:
    return sorted(p for p in ROUTERS_DIR.glob("*.py") if p.stem not in {"__init__", "_app"})


def _mcp_tool_functions_and_calls(
    tree: ast.Module,
) -> tuple[dict[str, ast.FunctionDef | ast.AsyncFunctionDef], dict[str, set[str]], dict[str, bool], dict[str, bool]]:
    """Return (name -> node) for @mcp.tool functions, (name -> called-names)
    for every top-level function (tool or private helper), (name ->
    already-decorated) for @mcp.tool functions, and (name -> order-correct)
    for @mcp.tool functions that carry both decorators."""
    tool_fns: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    calls: dict[str, set[str]] = {}
    decorated: dict[str, bool] = {}
    order_correct: dict[str, bool] = {}

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        called: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                fn = sub.func
                if isinstance(fn, ast.Name):
                    called.add(fn.id)
                elif isinstance(fn, ast.Attribute):
                    called.add(fn.attr)
        calls[node.name] = called

        is_mcp_tool = False
        has_catch_decorator = False
        # decorator_list is stored top-to-bottom in source order, but
        # decorators APPLY bottom-up (closest to `def` runs first). So the
        # correct wiring — @catch_slug_value_error runs first, wrapping the
        # raw function, before @mcp.tool() registers it — means "tool"
        # must appear BEFORE "catch_slug_value_error" in this list. Getting
        # this backwards registers the UNPROTECTED function with the MCP
        # server (mcp.tool() returns its argument unchanged), while every
        # test that imports the module-level name still sees the wrapper
        # and passes — a fix that looks complete and does nothing over the
        # actual transport (issue #523 code review, finding N-1).
        tool_index: int | None = None
        catch_index: int | None = None
        for i, dec in enumerate(node.decorator_list):
            dec_name = (
                dec.func.attr
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                else (dec.attr if isinstance(dec, ast.Attribute) else (dec.id if isinstance(dec, ast.Name) else None))
            )
            if dec_name == "tool":
                is_mcp_tool = True
                tool_index = i
            if dec_name == "catch_slug_value_error":
                has_catch_decorator = True
                catch_index = i
        if is_mcp_tool:
            tool_fns[node.name] = node
            decorated[node.name] = has_catch_decorator
            if has_catch_decorator:
                order_correct[node.name] = tool_index < catch_index  # type: ignore[operator]

    return tool_fns, calls, decorated, order_correct


def _reaches_resolver(fn_name: str, calls: dict[str, set[str]], seen: set[str] | None = None) -> bool:
    """BFS through same-module function calls to see if fn_name transitively
    calls one of RESOLVER_NAMES."""
    if seen is None:
        seen = set()
    if fn_name in seen:
        return False
    seen.add(fn_name)
    called = calls.get(fn_name, set())
    if called & RESOLVER_NAMES:
        return True
    return any(_reaches_resolver(callee, calls, seen) for callee in called if callee in calls)


def test_no_undecorated_resolver_call_site_exists() -> None:
    violations: list[str] = []
    for module_path in _router_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        tool_fns, calls, decorated, _order_correct = _mcp_tool_functions_and_calls(tree)
        for name in tool_fns:
            if not _reaches_resolver(name, calls):
                continue
            if decorated[name]:
                continue
            if (module_path.stem, name) in KNOWN_EXEMPT:
                continue
            violations.append(f"{module_path.stem}.{name}")

    assert not violations, (
        "MCP tool functions call a slug-validating resolver without "
        "@catch_slug_value_error and are not in KNOWN_EXEMPT: "
        f"{violations}. Either add the decorator or add a KNOWN_EXEMPT "
        "entry with a concrete, checked reason."
    )


def test_decorator_order_is_correct() -> None:
    """Issue #523 code review, finding N-1: MCPServer.tool() registers and
    returns the function UNCHANGED, so if @catch_slug_value_error is placed
    ABOVE @mcp.tool() instead of below it, the MCP server registers the raw,
    unprotected function while the module-level name (which every test
    imports) carries the wrapper — a completely inert fix that passes every
    functional test while leaving the real MCP tool call unprotected.
    Empirically confirmed: reversing the order on one function left it
    unprotected over mcp.call_tool() while its own test suite stayed green."""
    misordered: list[str] = []
    for module_path in _router_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        _tool_fns, _calls, _decorated, order_correct = _mcp_tool_functions_and_calls(tree)
        for name, correct in order_correct.items():
            if not correct:
                misordered.append(f"{module_path.stem}.{name}")

    assert not misordered, (
        f"@catch_slug_value_error is ABOVE @mcp.tool() (wrong order) on: {misordered}. "
        "It must be directly below @mcp.tool() so mcp.tool() registers the wrapped, "
        "not the raw, function."
    )


def test_known_exempt_functions_still_exist() -> None:
    """If a KNOWN_EXEMPT entry's function gets renamed or removed, the
    exemption should be cleaned up rather than silently doing nothing."""
    for module_stem, fn_name in KNOWN_EXEMPT:
        module_path = ROUTERS_DIR / f"{module_stem}.py"
        assert module_path.exists(), f"KNOWN_EXEMPT references missing module: {module_stem}"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert fn_name in names, f"KNOWN_EXEMPT references missing function: {module_stem}.{fn_name}"


def test_known_exempt_entries_are_still_needed() -> None:
    """test_no_undecorated_resolver_call_site_exists short-circuits on
    `if decorated[name]: continue` BEFORE consulting KNOWN_EXEMPT — so if a
    function in the exempt set later gains the decorator (e.g. someone
    tidies up and adds it defensively), its entry becomes dead weight and
    nothing flags it, the same silent-rot failure mode this module exists
    to prevent, one level up (issue #523 code review, finding L-4)."""
    stale: list[str] = []
    for module_path in _router_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        _tool_fns, _calls, decorated, _order_correct = _mcp_tool_functions_and_calls(tree)
        for name, is_decorated in decorated.items():
            if is_decorated and (module_path.stem, name) in KNOWN_EXEMPT:
                stale.append(f"{module_path.stem}.{name}")

    assert not stale, (
        f"KNOWN_EXEMPT entries no longer needed (function is now decorated): {stale}. "
        "Remove the entry."
    )


# ---------------------------------------------------------------------------
# Source-derived sweep — layer 3 (issue #531): raw Path-join bug SHAPE
# ---------------------------------------------------------------------------
#
# Layer 2 above only catches functions that call one of RESOLVER_NAMES —
# it's blind to a DIFFERENT bug shape: an @mcp.tool function that builds a
# Path directly, e.g. ``some_dir / f"{slug}.md"`` or ``some_dir / slug``,
# with no resolver call and no _validate_slug() call anywhere in sight.
# This was exactly issue #524 (three routers/series.py functions, since
# fixed) and issue #538 (routers/gates.py's validate_chapter, below).
#
# Scoped to functions whose raw join happens directly in their OWN body —
# it does not follow calls into helper functions in other modules (e.g.
# tools/state/*.py), which is a known, separate blind spot: see issue
# #538's own text on why those instances were "invisible to a search
# confined to routers/". Each of #538's four sites was fixed individually,
# with its own targeted test; this sweep only guards the one instance that
# lived directly in a router function body (validate_chapter).

# (module_stem, function_name) -> reason a real slug-param name reaching a
# Path join in this function is safe without _validate_slug(). Same
# discipline as KNOWN_EXEMPT above — a concrete, checked reason only.
SLUG_JOIN_KNOWN_EXEMPT: dict[tuple[str, str], str] = {}


def _is_slug_param_name(name: str) -> bool:
    return name == "slug" or name.endswith("_slug")


def _flatten_div_chain(node: ast.expr, out: list[ast.expr]) -> None:
    """A chained ``a / b / c`` parses as nested BinOp(Div) nodes. Flatten
    to the list of leaf operands so each can be checked independently."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        _flatten_div_chain(node.left, out)
        _flatten_div_chain(node.right, out)
    else:
        out.append(node)


def _single_name_in_join(node: ast.expr) -> str | None:
    """Return the parameter name referenced by a Path-join operand, if any.

    Matches two shapes: a bare ``Name`` (``chars_dir / slug``) and an
    f-string containing exactly one interpolated ``Name`` plus literal text
    (``chars_dir / f"{slug}.md"``). Anything else (a string literal, a
    method call, a multi-placeholder f-string) returns ``None``.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.JoinedStr):
        names = [
            v.value.id for v in node.values if isinstance(v, ast.FormattedValue) and isinstance(v.value, ast.Name)
        ]
        if len(names) == 1:
            return names[0]
    return None


def _validated_param_names(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names passed as the first positional arg to a _validate_slug() call
    anywhere in the function body."""
    validated: set[str] = set()
    for sub in ast.walk(fn_node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        fn_name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
        if fn_name == "_validate_slug" and sub.args and isinstance(sub.args[0], ast.Name):
            validated.add(sub.args[0].id)
    return validated


def _unvalidated_slug_join_params(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Slug-named parameters of ``fn_node`` that reach a Path-join operand
    (bare Name or single-placeholder f-string) with no matching
    _validate_slug() call anywhere in the function body."""
    params = {a.arg for a in fn_node.args.args} | {a.arg for a in fn_node.args.kwonlyargs}
    slug_params = {p for p in params if _is_slug_param_name(p)}
    if not slug_params:
        return set()

    validated = _validated_param_names(fn_node)
    hits: set[str] = set()
    for sub in ast.walk(fn_node):
        if not (isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div)):
            continue
        operands: list[ast.expr] = []
        _flatten_div_chain(sub, operands)
        for operand in operands:
            name = _single_name_in_join(operand)
            if name and name in slug_params and name not in validated:
                hits.add(name)
    return hits


def test_no_unvalidated_slug_path_join_in_tool_body() -> None:
    violations: list[str] = []
    for module_path in _router_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        tool_fns, _calls, _decorated, _order_correct = _mcp_tool_functions_and_calls(tree)
        for name, node in tool_fns.items():
            if (module_path.stem, name) in SLUG_JOIN_KNOWN_EXEMPT:
                continue
            for param in _unvalidated_slug_join_params(node):
                violations.append(f"{module_path.stem}.{name} (param: {param})")

    assert not violations, (
        "MCP tool functions build a Path directly from a slug-named parameter "
        "(no resolver, no _validate_slug()) with no validation: "
        f"{violations}. Either call _validate_slug(param, ...) before the join, "
        "route through a resolve_*_path() helper, or add a SLUG_JOIN_KNOWN_EXEMPT "
        "entry with a concrete, checked reason."
    )
