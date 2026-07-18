"""Smoke: Windows/POSIX MCP server + hook launch — regression guard for Windows support."""
import json
import os
import re
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


def test_run_server_wrapper_actually_launches_python():
    """Real subprocess spawn through the OS-appropriate wrapper — proves shebang
    execution / %USERPROFILE%-%*-quoting actually work, not just that the files exist."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        if sys.platform == "win32":
            venv_scripts = home / ".storyforge" / "venv" / "Scripts"
            venv_scripts.mkdir(parents=True)
            (venv_scripts / "python.exe").write_bytes(Path(sys.executable).read_bytes())
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
            venv_scripts = home / ".storyforge" / "venv" / "Scripts"
            venv_scripts.mkdir(parents=True)
            (venv_scripts / "python.exe").write_bytes(Path(sys.executable).read_bytes())
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
                if "encoding=" not in call and "'rb'" not in call and '"rb"' not in call and "'wb'" not in call and '"wb"' not in call:
                    lineno = source.count("\n", 0, match.start()) + 1
                    violations.append(f"{path.relative_to(ROOT)}:{lineno}: {match.group(0)}")
    assert not violations, 'Missing encoding="utf-8":\n' + "\n".join(violations)
