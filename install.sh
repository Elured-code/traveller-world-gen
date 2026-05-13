#!/usr/bin/env bash
# =============================================================================
# Traveller World Generator — Quick Install (macOS / Linux)
# =============================================================================
# Creates a Python virtual environment, installs the GUI library (PySide6),
# and generates launcher scripts for the desktop app and command-line tools.
#
# Usage:
#   bash install.sh
#
# Requirements:
#   Python 3.9 or later  — https://www.python.org/downloads/
# =============================================================================

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
else
    GREEN=''; YELLOW=''; RED=''; CYAN=''; NC=''
fi

info()  { echo -e "${GREEN}[install]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warning]${NC} $*"; }
fail()  { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${CYAN}Traveller World Generator — Installation${NC}"
echo "========================================="
echo ""

# ── 1. Locate Python 3.9+ ─────────────────────────────────────────────────────
info "Checking Python..."

PYTHON=""
for cmd in python3 python python3.11 python3.10 python3.9; do
    if command -v "$cmd" &>/dev/null; then
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
        if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 9 ]; }; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.9 or later is required but was not found.
       Download from: https://www.python.org/downloads/
       After installing, re-run this script."
fi

PY_VER=$("$PYTHON" -c "import sys; print('%d.%d' % sys.version_info[:2])")
info "Found Python $PY_VER  ($PYTHON)"

# ── 2. Create virtual environment ─────────────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv"

if [ -d "$VENV_DIR" ]; then
    info "Virtual environment already exists — will update packages."
else
    info "Creating virtual environment in .venv/ ..."
    "$PYTHON" -m venv "$VENV_DIR" || fail "Could not create virtual environment."
fi

VENV_PYTHON="$VENV_DIR/bin/python3"

# ── 3. Install PySide6 ────────────────────────────────────────────────────────
info "Upgrading pip..."
"$VENV_PYTHON" -m pip install --quiet --upgrade pip

info "Installing PySide6 (desktop GUI library) — this may take a few minutes..."
"$VENV_PYTHON" -m pip install --quiet "PySide6>=6.4.0" \
    || fail "Failed to install PySide6. Check your internet connection and try again."
info "PySide6 installed."

# ── 4. Create launcher scripts ────────────────────────────────────────────────
info "Creating launcher scripts..."

# -- Desktop GUI (.command = double-clickable in Finder on macOS) -------------
cat > "$SCRIPT_DIR/run-gui.command" << 'LAUNCHER'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/gen-ui/app.py"
LAUNCHER
chmod +x "$SCRIPT_DIR/run-gui.command"

# -- World generator CLI -------------------------------------------------------
cat > "$SCRIPT_DIR/run-world.sh" << 'LAUNCHER'
#!/usr/bin/env bash
# Generate one or more Traveller mainworlds.
#
# Options:
#   --name NAME       World name (default: auto-numbered)
#   --count N         Number of worlds to generate (default: 1)
#   --seed N          RNG seed for reproducible results
#   --json            Output as JSON instead of text
#   --html            Output as an HTML card
#
# Examples:
#   bash run-world.sh
#   bash run-world.sh --name "New Terra" --count 3
#   bash run-world.sh --name Zhodane --seed 42 --json
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/traveller_world_gen.py" "$@"
LAUNCHER
chmod +x "$SCRIPT_DIR/run-world.sh"

# -- TravellerMap lookup CLI ---------------------------------------------------
cat > "$SCRIPT_DIR/run-mapfetch.sh" << 'LAUNCHER'
#!/usr/bin/env bash
# Fetch a world from TravellerMap and generate a full star system.
# Requires an internet connection.
#
# Options (--sector is always required):
#   --sector SECTOR   Sector name, e.g. "Spinward Marches"
#   --name NAME       World name within the sector
#   --hex NNNN        4-digit hex position (alternative to --name)
#   --seed N          RNG seed for reproducible results
#   --detail          Include secondary world and moon profiles
#   --json            Output as JSON
#   --html            Output as an HTML card
#
# Examples:
#   bash run-mapfetch.sh --sector "Spinward Marches" --name Regina
#   bash run-mapfetch.sh --sector "Spinward Marches" --hex 1910 --detail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/traveller_map_fetch.py" "$@"
LAUNCHER
chmod +x "$SCRIPT_DIR/run-mapfetch.sh"

# ── 5. Done ───────────────────────────────────────────────────────────────────
echo ""
info "Installation complete!"
echo ""
echo -e "${CYAN}  ┌──────────────────────────────────────────────────────────────┐${NC}"
echo -e "${CYAN}  │  Desktop app                                                 │${NC}"
echo -e "${CYAN}  │    macOS:  double-click  run-gui.command  in Finder          │${NC}"
echo -e "${CYAN}  │    Linux:  bash run-gui.command                              │${NC}"
echo -e "${CYAN}  │                                                              │${NC}"
echo -e "${CYAN}  │  World generator (command line)                              │${NC}"
echo -e "${CYAN}  │    bash run-world.sh [--name NAME] [--count N]              │${NC}"
echo -e "${CYAN}  │                                                              │${NC}"
echo -e "${CYAN}  │  TravellerMap lookup (command line, needs internet)          │${NC}"
echo -e "${CYAN}  │    bash run-mapfetch.sh --sector SECTOR --name NAME         │${NC}"
echo -e "${CYAN}  └──────────────────────────────────────────────────────────────┘${NC}"
echo ""
echo "  Examples:"
echo "    bash run-world.sh"
echo "    bash run-world.sh --name \"New Terra\" --count 5"
echo "    bash run-mapfetch.sh --sector \"Spinward Marches\" --name Regina"
echo ""
echo -e "  ${YELLOW}macOS note:${NC} If Finder shows a security warning when opening"
echo "  run-gui.command, right-click it and choose Open, then click Open."
echo ""
