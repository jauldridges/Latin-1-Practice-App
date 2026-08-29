#!/bin/bash
# Latin I — one-click start (macOS: double-click this file, or run ./start.command)
#
# Finds Python, sets up a private virtual environment the first time so nothing
# on your system is touched, installs Flask + PyYAML, and launches the app.
# Safe to run over and over — after the first time it just starts.

cd "$(dirname "$0")" || exit 1

echo "Latin I — starting up"
echo

# 1. Find a usable Python 3.
PY=""
for candidate in python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' 2>/dev/null; then
      PY="$candidate"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "Python 3 was not found on this Mac."
  echo
  echo "Fix it with either of these, then run this file again:"
  echo "  1. In Terminal, run:  xcode-select --install"
  echo "  2. Or download Python from https://www.python.org/downloads/"
  echo
  read -r -p "Press return to close." _
  exit 1
fi

echo "Using Python: $($PY --version 2>&1)"

# 2. Private virtual environment, created once. Keeps this project's packages
#    to itself and sidesteps macOS's protected system Python.
if [ ! -d ".venv" ]; then
  echo "First run: setting up (about a minute)..."
  "$PY" -m venv .venv || {
    echo "Could not create the virtual environment."
    read -r -p "Press return to close." _
    exit 1
  }
fi

# 3. Install/refresh dependencies inside the venv.
./.venv/bin/python -m pip install --quiet --upgrade pip >/dev/null 2>&1
./.venv/bin/python -m pip install --quiet -r requirements.txt || {
  echo "Could not install Flask and PyYAML. Are you online?"
  read -r -p "Press return to close." _
  exit 1
}

# 4. Go.
echo
exec ./.venv/bin/python run.py
