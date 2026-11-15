#!/usr/bin/env bash
set -euo pipefail

git pull --ff-only
source .venv/bin/activate
pip install -r backend/requirements/raspberry-pi.txt

