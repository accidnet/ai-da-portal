#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)

cd "${REPO_ROOT}/portal-onl"
exec uv run uvicorn --app-dir src main:app --reload "$@"
