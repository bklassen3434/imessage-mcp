"""Register this MCP server with whichever Claude apps are installed.

Run by install.sh. Safe to run repeatedly: it updates the entry in place and
leaves any other configured servers untouched.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SERVER_NAME = "imessage"
HERE = Path(__file__).resolve().parent

DESKTOP_CONFIG = Path(
    os.environ.get(
        "CLAUDE_DESKTOP_CONFIG",
        Path.home()
        / "Library/Application Support/Claude/claude_desktop_config.json",
    )
)


def find_uv() -> str:
    """Absolute path to uv. GUI apps do not inherit the shell PATH, so a bare
    'uv' in a config file fails even when it works in Terminal."""
    found = shutil.which("uv")
    if found:
        return found
    for candidate in (
        Path.home() / ".local/bin/uv",
        Path("/opt/homebrew/bin/uv"),
        Path("/usr/local/bin/uv"),
    ):
        if candidate.exists():
            return str(candidate)
    sys.exit("Could not find uv. Re-run install.sh.")


def claude_app_installed() -> bool:
    return any(
        p.exists()
        for p in (
            Path("/Applications/Claude.app"),
            Path.home() / "Applications/Claude.app",
        )
    )


def configure_desktop(uv: str) -> tuple[bool, str]:
    # The config folder only appears after Claude has been launched once, so a
    # freshly installed app needs the folder created rather than being skipped.
    if not DESKTOP_CONFIG.parent.exists() and not claude_app_installed():
        return False, "Claude app not found in Applications - skipped."

    config = {}
    if DESKTOP_CONFIG.exists() and DESKTOP_CONFIG.stat().st_size > 0:
        try:
            config = json.loads(DESKTOP_CONFIG.read_text())
        except json.JSONDecodeError:
            backup = DESKTOP_CONFIG.with_suffix(".json.broken")
            shutil.copy2(DESKTOP_CONFIG, backup)
            return False, (
                f"Existing config was not valid JSON. Left it alone (copy at {backup})."
            )

    if DESKTOP_CONFIG.exists():
        shutil.copy2(DESKTOP_CONFIG, DESKTOP_CONFIG.with_suffix(".json.backup"))

    servers = config.setdefault("mcpServers", {})
    servers[SERVER_NAME] = {
        "command": uv,
        "args": ["run", "--directory", str(HERE), "server.py"],
    }
    DESKTOP_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    DESKTOP_CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    return True, "Added to the Claude app (this is what Claude chat uses)."


def configure_claude_code(uv: str) -> tuple[bool, str]:
    if not shutil.which("claude"):
        return False, "Claude Code not installed - skipped (this is normal)."
    subprocess.run(
        ["claude", "mcp", "remove", SERVER_NAME, "-s", "user"],
        capture_output=True,
    )
    result = subprocess.run(
        ["claude", "mcp", "add", SERVER_NAME, "-s", "user", "--",
         uv, "run", "--directory", str(HERE), "server.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, f"Claude Code registration failed: {result.stderr.strip()}"
    return True, "Added to Claude Code."


def main() -> None:
    uv = find_uv()
    desktop = configure_desktop(uv)
    code = configure_claude_code(uv)
    print("  " + desktop[1])
    # Most people only have the Claude app; mentioning Claude Code when it is
    # absent is just noise, so only report it when it was actually configured.
    if code[0]:
        print("  " + code[1])
    results = [desktop, code]
    if not any(ok for ok, _ in results):
        sys.exit(
            "\n  PROBLEM: could not connect to any Claude app.\n"
            "  Make sure the Claude app is installed in your Applications\n"
            "  folder, then run this installer again."
        )


if __name__ == "__main__":
    main()
