#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Error: .venv/bin/python not found."
  echo "Create and install dependencies in the project virtual environment first."
  exit 1
fi

.venv/bin/python build_chart_package.py
