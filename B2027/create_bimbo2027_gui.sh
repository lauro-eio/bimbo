#!/usr/bin/env bash
# GUI launcher — detach from file-manager / terminal (Linux).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
GUI="$ROOT/scripts/create_bimbo2027_gui.py"
LOG="$ROOT/var/logs/launcher.log"
ERR_LOG="$ROOT/var/logs/launcher-errors.log"

_show_error() {
  local msg="$1"
  mkdir -p "$ROOT/var/logs"
  printf '%s %s\n' "$(date -Iseconds)" "$msg" >>"$ERR_LOG"
  if [[ -t 1 ]]; then
    echo "$msg" >&2
    read -r -p "Press Enter to continue..." || true
  fi
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="B2027 Club factory" --text="$msg" 2>/dev/null || true
  elif command -v kdialog >/dev/null 2>&1; then
    kdialog --error "$msg" 2>/dev/null || true
  fi
}

if [[ ! -x "$PYTHON" ]]; then
  _show_error "Missing .venv — open a terminal in this folder and run:

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt"
  exit 1
fi

if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
  _show_error "Tkinter is not available for this Python.

On Fedora, install system Tk then recreate the venv, or run:
  sudo dnf install python3-tkinter"
  exit 1
fi

if [[ ! -f "$GUI" ]]; then
  _show_error "Missing GUI script: $GUI"
  exit 1
fi

mkdir -p "$ROOT/var/logs"
nohup "$PYTHON" "$GUI" "$@" >>"$LOG" 2>&1 &
pid=$!
sleep 0.5
if ! kill -0 "$pid" 2>/dev/null; then
  _show_error "B2027 GUI failed to start. See var/logs/launcher.log in the project folder."
  exit 1
fi
