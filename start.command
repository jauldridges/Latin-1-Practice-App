#!/bin/bash
# Latin I — one-click start (macOS: double-click this file, or run ./start.command)
#
# Finds Python, pulls the latest version, sets up a private virtual environment
# the first time so nothing on your system is touched, installs what it needs,
# and launches the app. Safe to run over and over — after the first time it
# updates and starts.

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

# 3. Pick up the latest version, if this is a git checkout and nothing local
#    is half-finished. Never fatal: no network, or a repo with local edits,
#    just means starting the version already on disk.
if [ -d .git ] && command -v git >/dev/null 2>&1; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
    echo "Checking for updates..."
    BEFORE=$(git rev-parse HEAD 2>/dev/null)
    if git pull --ff-only --quiet 2>/dev/null; then
      AFTER=$(git rev-parse HEAD 2>/dev/null)
      if [ "$BEFORE" != "$AFTER" ]; then
        echo "Updated: $(git log --oneline "$BEFORE..$AFTER" 2>/dev/null | wc -l | tr -d ' ') new change(s)."
      else
        echo "Already up to date."
      fi
    else
      echo "(couldn't check for updates — starting the version already here)"
    fi
  else
    echo "(local changes present — leaving them alone, not updating)"
  fi
  # Say which version this is. "Already up to date" on the wrong branch is the
  # worst kind of wrong: it sounds like success and starts the old app.
  echo "Branch: $BRANCH  ·  $(git log --oneline -1 2>/dev/null)"
fi

# 4. Install/refresh dependencies inside the venv.
./.venv/bin/python -m pip install --quiet --upgrade pip >/dev/null 2>&1
./.venv/bin/python -m pip install --quiet -r requirements.txt || {
  echo "Could not install Flask and PyYAML. Are you online?"
  read -r -p "Press return to close." _
  exit 1
}

# 5. Go.
echo
exec ./.venv/bin/python run.py
