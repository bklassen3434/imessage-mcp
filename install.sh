#!/bin/bash
# Sets up the iMessage MCP server. Safe to run more than once.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo ""
echo "Setting up the iMessage server for Claude"
echo "========================================="
echo ""

# Step 1: uv runs the server and manages its Python version for us.
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  echo "[1/3] Installing uv (a small tool that runs the server)..."
  echo "      Downloading from astral.sh, the official source."
  curl -LsSf https://astral.sh/uv/install.sh | sh
else
  echo "[1/3] uv is already installed."
fi
export PATH="$HOME/.local/bin:$PATH"

# Step 2: fetch Python and the MCP library into a local folder.
echo "[2/3] Downloading what the server needs (this can take a minute)..."
uv sync --quiet

# Step 3: tell the Claude apps where to find the server.
echo "[3/3] Connecting it to Claude..."
uv run --quiet python configure_client.py

cat <<'MSG'

-------------------------------------------------------
Almost done. One step left, and you must do it by hand.
-------------------------------------------------------

Your Mac keeps messages private, so you have to give
Claude permission to read them.

  1. Open  System Settings
  2. Go to  Privacy & Security  >  Full Disk Access
  3. Turn ON the switch next to  Claude
     (if Claude is not listed, click + and pick it
      from your Applications folder)
  4. QUIT CLAUDE COMPLETELY and open it again.
     Press Command-Q. Just closing the window is not enough.

Then ask Claude:  "who have I not texted in a while?"

MSG
