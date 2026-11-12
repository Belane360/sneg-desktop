#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade --only-binary=:all: 'pip<26'
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
exec .venv/bin/python main.py
