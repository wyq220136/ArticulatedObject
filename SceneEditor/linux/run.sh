#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CONFIG_PATH="${1:-${SCRIPT_DIR}/../config.yml}"

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/run.py" "${CONFIG_PATH}"
