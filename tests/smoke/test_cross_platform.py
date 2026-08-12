"""Smoke: Windows/POSIX MCP server + hook launch — regression guard for Windows support."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_DIRS = [ROOT / "tools", ROOT / "servers", ROOT / "hooks"]
MCP_JSON = ROOT / ".mcp.json"
HOOKS_JSON = ROOT / ".claude-plugin" / "hooks.json"
RUN_SERVER = ROOT / "bin" / "run-server"
RUN_SERVER_CMD = ROOT / "bin" / "run-server.cmd"
GITATTRIBUTES = ROOT / ".gitattributes"
RUN_PY = ROOT / "servers" / "storyforge-server" / "run.py"
SETUP_SKILL = ROOT / "skills" / "setup" / "SKILL.md"
VALIDATE_CHAPTER_HOOK = ROOT / "hooks" / "validate_chapter.py"


def test_mcp_json_is_valid_json():
    json.loads(MCP_JSON.read_text(encoding="utf-8"))


def test_mcp_json_command_has_no_hardcoded_venv_subpath():
    """command must go through the OS-agnostic bin/run-server wrapper, not hardcode
    venv/bin (POSIX) or venv\\Scripts (Windows) directly."""
    config = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    command = config["mcpServers"]["storyforge-mcp"]["command"]
    assert "venv/bin" not in command
    assert "venv\\Scripts" not in command and "venv/Scripts" not in command
    assert command.endswith("bin/run-server")


def test_mcp_json_schema():
    """A dropped/typo'd field here silently breaks the MCP server for every user."""
    config = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    server = config["mcpServers"]["storyforge-mcp"]
    assert server["type"] == "stdio"
    assert isinstance(server["args"], list) and len(server["args"]) == 1


def test_mcp_json_has_no_env_override():
    """Claude Code passes MCP env values as literal strings, not shell-expanded —
    an env.CLAUDE_PLUGIN_ROOT override here breaks the server for every user
    (see run.py's __file__-based fallback, which is the correct, OS-agnostic
    way to resolve the plugin root)."""
    config = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    server = config["mcpServers"]["storyforge-mcp"]
    assert "env" not in server


def test_run_server_wrapper_exists_and_is_executable():
    assert RUN_SERVER.exists(), "bin/run-server not found"
    assert os.access(RUN_SERVER, os.X_OK), "bin/run-server must have the executable bit set"
    first_line = RUN_SERVER.read_text(encoding="utf-8").splitlines()[0]
    assert first_line in ("#!/bin/sh", "#!/bin/bash"), f"unexpected shebang: {first_line}"


def test_run_server_cmd_wrapper_targets_windows_venv():
    assert RUN_SERVER_CMD.exists(), "bin/run-server.cmd not found"
    content = RUN_SERVER_CMD.read_text(encoding="utf-8")
    assert "%USERPROFILE%" in content
    assert "Scripts\\python.exe" in content


def _build_fake_windows_venv(home: Path) -> None:
    """Build a runnable fake venv Scripts/ dir for the run-server.cmd wrapper tests.

    Issue #541: copying only python.exe's bytes into an isolated temp
    directory drops the files a full Windows Python install's python.exe
    depends on (python3xx.dll and friends), which live alongside it in the
    real install directory — the copy can't start at all
    (STATUS_DLL_NOT_FOUND). Copy the whole directory containing
    sys.executable instead, so any same-directory dependency travels
    with it.

    Issue #545: an unrestricted copytree() is fine for a small venv
    Scripts/ dir, but if sys.executable is a system/standalone install
    (e.g. ``C:\\Program Files\\Python313\\``, exactly what Windows CI runs
    via actions/setup-python with no venv) this copies the ENTIRE install —
    Lib/, DLLs, tcl/, Doc/, include/, hundreds of MB and thousands of
    files, twice per test run.

    Excluding those directories with ``shutil.ignore_patterns()`` (an
    earlier version of this fix) is NOT a safe middle ground: CPython
    locates its standard library at startup by looking for a ``Lib``
    landmark next to the interpreter (or a ``pyvenv.cfg``) — drop ``Lib``
    from the copy with no ``pyvenv.cfg`` to compensate and the copied
    interpreter fails to initialize on exactly the full-install
    configuration this fix targets.

    Copy only the files that sit directly next to python.exe (its DLL
    dependencies — #541's concern) and write a ``pyvenv.cfg`` whose
    ``home`` points back at the real install directory — the same
    redirection mechanism ``python -m venv`` itself relies on, so the
    stdlib is found without copying it. No directory ever gets copied, by
    construction (only ``is_file()`` entries), so this needs no exclusion
    list to keep pace with what a Python install happens to ship.
    """
    venv_dir = home / ".storyforge" / "venv"
    venv_scripts = venv_dir / "Scripts"
    src_exe = Path(sys.executable)
    src_dir = src_exe.parent
    venv_scripts.mkdir(parents=True)
    # Always name the copy python.exe — run-server.cmd invokes exactly that
    # filename, but sys.executable's own basename isn't guaranteed to match
    # (e.g. a venv interpreter on POSIX is typically "python3").
    shutil.copy2(src_exe, venv_scripts / "python.exe")
    for item in src_dir.iterdir():
        if item.is_file() and item != src_exe:
            shutil.copy2(item, venv_scripts / item.name)
    (venv_dir / "pyvenv.cfg").write_text(f"home = {src_dir}\n", encoding="utf-8")


def test_build_fake_windows_venv_skips_large_install_dirs(monkeypatch, tmp_path):
    """Issue #545: copying the whole directory containing sys.executable
    with no exclusion copies an ENTIRE system Python install (Lib/, DLLs,
    tcl/, Doc/, include/, hundreds of MB) when sys.executable isn't a
    small venv interpreter — slow and flaky on the Windows CI job this
    helper exists for. Only files colocated with python.exe (its DLL
    dependencies) should copy; every subdirectory must be skipped, by
    construction rather than by naming each one that happens to exist."""
    fake_install = tmp_path / "fake_python_install"
    (fake_install / "Lib" / "site-packages").mkdir(parents=True)
    (fake_install / "Lib" / "site-packages" / "big.txt").write_text("x" * 1000, encoding="utf-8")
    (fake_install / "tcl" / "tcl8.6").mkdir(parents=True)
    (fake_install / "tcl" / "tcl8.6" / "init.tcl").write_text("", encoding="utf-8")
    (fake_install / "Doc").mkdir()
    (fake_install / "Doc" / "python.chm").write_text("", encoding="utf-8")
    (fake_install / "include").mkdir()
    (fake_install / "include" / "Python.h").write_text("", encoding="utf-8")
    (fake_install / "Scripts").mkdir()
    (fake_install / "Scripts" / "pip.exe").write_text("", encoding="utf-8")
    (fake_install / "python.exe").write_text("", encoding="utf-8")
    (fake_install / "python313.dll").write_text("", encoding="utf-8")
    (fake_install / "vcruntime140.dll").write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "executable", str(fake_install / "python.exe"))
    home = tmp_path / "home"
    _build_fake_windows_venv(home)

    venv_scripts = home / ".storyforge" / "venv" / "Scripts"
    assert (venv_scripts / "python.exe").exists()
    assert (venv_scripts / "python313.dll").exists()
    assert (venv_scripts / "vcruntime140.dll").exists()
    assert not (venv_scripts / "Lib").exists()
    assert not (venv_scripts / "tcl").exists()
    assert not (venv_scripts / "Doc").exists()
    assert not (venv_scripts / "include").exists()
    assert not (venv_scripts / "Scripts").exists()

    pyvenv_cfg = home / ".storyforge" / "venv" / "pyvenv.cfg"
    assert pyvenv_cfg.exists()
    assert f"home = {fake_install}" in pyvenv_cfg.read_text(encoding="utf-8")


def test_build_fake_windows_venv_produces_a_runnable_interpreter(tmp_path):
    """Issue #545 code review: excluding Lib/ from the copy is only safe if
    the pyvenv.cfg redirection actually works — otherwise the fix trades a
    slow-but-working helper for a fast-but-broken one on precisely the
    full-install configuration it targets (Windows CI via
    actions/setup-python, no venv). Verifiable on any platform: the copied
    "python.exe" is a real, executable copy of the current interpreter
    regardless of its Windows-flavored name, so this spawns it for real
    rather than just asserting the directory shape."""
    home = tmp_path / "home"
    _build_fake_windows_venv(home)
    python_copy = home / ".storyforge" / "venv" / "Scripts" / "python.exe"

    result = subprocess.run([str(python_copy), "-c", "print('OK')"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"copied interpreter failed to start: {result.stderr}"
    assert "OK" in result.stdout


def test_run_server_wrapper_actually_launches_python():
    """Real subprocess spawn through the OS-appropriate wrapper — proves shebang
    execution / %USERPROFILE%-%*-quoting actually work, not just that the files exist."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        if sys.platform == "win32":
            _build_fake_windows_venv(home)
            env = {**os.environ, "USERPROFILE": str(home)}
            cmd = [str(RUN_SERVER_CMD), "-c", "print('OK')"]
        else:
            venv_bin = home / ".storyforge" / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python3").symlink_to(sys.executable)
            env = {**os.environ, "HOME": str(home)}
            cmd = [str(RUN_SERVER), "-c", "print('OK')"]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"wrapper failed: {result.stderr}"
        assert "OK" in result.stdout


def test_run_server_wrapper_launches_a_real_hook_script():
    """The MCP server path gets exercised by test_run_server_wrapper_actually_launches_python,
    but hooks.json routes through the same wrapper to invoke actual hook scripts — that path
    needs its own real subprocess check, not just a string assertion that the config mentions
    bin/run-server. Uses the current interpreter (which already has the plugin's deps
    installed, same as the wrapper test above) via a fake-HOME venv symlink."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        if sys.platform == "win32":
            _build_fake_windows_venv(home)
            env = {**os.environ, "USERPROFILE": str(home)}
            cmd = [str(RUN_SERVER_CMD), str(VALIDATE_CHAPTER_HOOK)]
        else:
            venv_bin = home / ".storyforge" / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python3").symlink_to(sys.executable)
            env = {**os.environ, "HOME": str(home)}
            cmd = [str(RUN_SERVER), str(VALIDATE_CHAPTER_HOOK)]

        result = subprocess.run(cmd, input="", env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"hook launch via wrapper failed: {result.stderr}"


def test_gitattributes_pins_wrapper_eol():
    """A corrupted shebang (CRLF) or a batch file with LF line endings both fail
    silently on their respective platform — EOL must be pinned in git."""
    content = GITATTRIBUTES.read_text(encoding="utf-8") if GITATTRIBUTES.exists() else ""
    assert "bin/run-server text eol=lf" in content
    assert "bin/run-server.cmd text eol=crlf" in content


def test_hooks_json_is_valid_json():
    json.loads(HOOKS_JSON.read_text(encoding="utf-8"))


def test_hooks_json_commands_have_no_hardcoded_venv_subpath():
    """PreCompact/PostToolUse hook commands must route through bin/run-server too —
    same class of bug as the MCP command, just a different config file."""
    config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    commands = []
    for hook_events in config["hooks"].values():
        for entry in hook_events:
            for hook in entry["hooks"]:
                commands.append(hook["command"])
    assert commands, "no hook commands found in hooks.json"
    for command in commands:
        assert "venv/bin" not in command
        assert "venv\\Scripts" not in command and "venv/Scripts" not in command
        assert "bin/run-server" in command


def test_run_py_has_no_hardcoded_posix_venv_path():
    """run.py's own launch logic must not re-hardcode a venv/bin/python3 lookup —
    interpreter selection is bin/run-server's job; run.py can assume it's already
    running under the correct interpreter. Matches actual code patterns, not prose
    mentions of "venv" in comments/docstrings explaining that assumption."""
    body = RUN_PY.read_text(encoding="utf-8")
    venv_path_patterns = [
        r'["\']venv["\']\s*/\s*["\']bin["\']',  # Path.home() / "venv" / "bin"
        r"venv[/\\]bin[/\\]python3?",  # literal "venv/bin/python3" string
    ]
    for pattern in venv_path_patterns:
        assert not re.search(pattern, body), (
            f"run.py still contains its own venv/bin resolution logic (matched {pattern!r}) — "
            "this duplicates (and can diverge from) bin/run-server"
        )


def test_run_py_derives_plugin_root_when_env_var_unset():
    """The only untested happy-path branch in run.py: when CLAUDE_PLUGIN_ROOT isn't
    injected into the environment (e.g. local dev testing outside the harness), main()
    must fall back to a __file__-derived root instead of leaving it unset or wrong."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_run_py_under_test", RUN_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    saved_env = os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
    saved_path = list(sys.path)
    try:
        module.runpy.run_path = lambda *a, **kw: None  # skip the actual server launch
        module.main()
        assert os.environ["CLAUDE_PLUGIN_ROOT"] == str(RUN_PY.parent.parent.parent)
        assert os.environ["CLAUDE_PLUGIN_ROOT"] in sys.path
    finally:
        sys.path[:] = saved_path
        if saved_env is not None:
            os.environ["CLAUDE_PLUGIN_ROOT"] = saved_env
        else:
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)


def test_setup_skill_documents_both_platforms():
    """Regression guard: a file that documents only the POSIX venv path (venv/bin/python3)
    without a Windows equivalent (venv\\Scripts\\python.exe) is the root bug — check
    both markers are present together."""
    body = SETUP_SKILL.read_text(encoding="utf-8")
    assert "venv/bin/python3" in body or "venv/bin/pip" in body, "missing POSIX venv interpreter path"
    assert "Scripts\\python.exe" in body or "Scripts\\pip.exe" in body, (
        "missing Windows venv interpreter path — likely not yet OS-branched"
    )


def test_setup_skill_documents_py_launcher_fallback():
    """Regression guard: on managed Windows devices, bare `python`/`python3` can resolve
    to the Microsoft Store app-execution-alias stub. `py -3` must be documented as a
    fallback, or setup silently tells a managed-device user to install Python they
    already have."""
    body = SETUP_SKILL.read_text(encoding="utf-8")
    assert "py -3" in body, "missing `py -3` fallback for Windows Store-alias detection failures"


def test_setup_skill_uses_write_then_run_for_multiline_python_not_inline_c():
    """Regression guard: a `-c "..."` argument that spans multiple lines parses
    differently across bash/PowerShell/cmd and reliably breaks under PowerShell."""
    multiline_c_pattern = re.compile(r'-c\s+"\s*\n')
    body = SETUP_SKILL.read_text(encoding="utf-8")
    assert not multiline_c_pattern.search(body), (
        "found a multi-line `-c \"...` invocation — breaks under PowerShell, "
        "use the write-then-run pattern instead"
    )


UNENCODED_FILE_IO = re.compile(r"(?<![\w.])(?:\w+\.)?(?:open|write_text|read_text)\(")
NON_PATH_OPEN_RECEIVERS = ("fitz.open(", "zipfile.open(", "tarfile.open(")
# Any binary-mode literal ('rb', 'wb', 'xb', 'ab', 'rb+', 'r+b', ...) — binary
# mode never takes encoding= (Python raises ValueError if you try), so any
# open() call carrying one of these is exempt by construction, not just the
# 'rb'/'wb' literals originally special-cased here. Expressed as a pattern
# rather than an enumerated literal list so it doesn't need re-widening the
# next time a new binary-mode spelling shows up (#555).
BINARY_OPEN_MODE = re.compile(r"""['"][rwxa]\+?b\+?['"]""")


def _call_span(source: str, open_paren_index: int) -> str:
    """Return the full text of a call starting at the given `(`, tracking paren depth."""
    depth = 0
    for i in range(open_paren_index, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return source[open_paren_index : i + 1]
    return source[open_paren_index:]


def test_no_unencoded_file_io_in_source():
    """Regression guard: on a non-UTF-8-locale Windows host, Path.open()/write_text()/
    read_text() without an explicit encoding falls back to the locale codepage (cp1252
    on German Windows), which cannot represent characters like em-dashes or checkmarks
    and raises UnicodeEncodeError/UnicodeDecodeError. Every call site under tools/,
    servers/, and hooks/ must pass encoding="utf-8" explicitly.

    Tracks paren depth to find the true end of each call, however many lines it spans,
    rather than guessing a fixed window size.
    """
    violations = []
    for source_dir in SOURCE_DIRS:
        for path in source_dir.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            for match in UNENCODED_FILE_IO.finditer(source):
                if any(source[match.start() :].startswith(r) for r in NON_PATH_OPEN_RECEIVERS):
                    continue
                call = _call_span(source, match.end() - 1)
                # The binary-mode exemption only applies to open(...) — write_text()/
                # read_text() take no mode argument, so a literal like 'ab' appearing
                # in their arguments for unrelated reasons (e.g. an actual two-char
                # string payload) must not be mistaken for a binary-mode marker.
                is_open_call = match.group(0).endswith("open(")
                if "encoding=" not in call and not (is_open_call and BINARY_OPEN_MODE.search(call)):
                    lineno = source.count("\n", 0, match.start()) + 1
                    violations.append(f"{path.relative_to(ROOT)}:{lineno}: {match.group(0)}")
    assert not violations, 'Missing encoding="utf-8":\n' + "\n".join(violations)
