#!/bin/zsh
set -e
cd "${0:A:h}"
trap 'echo "Setup or launch failed. See README.md for Terminal instructions."; read "?Press Return to close…"' ZERR
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if [[ ! -f .venv/movie-roulette-ready ]]; then
  echo 'Setting up Movie Roulette…'
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/movie-roulette-ready
fi
exec .venv/bin/python app.py
