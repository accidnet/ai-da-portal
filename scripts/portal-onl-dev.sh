#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)

cd "${REPO_ROOT}/portal-onl"
# 개발 실행은 앱 로그와 uvicorn 로그를 모두 DEBUG로 맞춘다.
exec env PORTAL_ENV=dev LOG_LEVEL=DEBUG uv run uvicorn --app-dir src main:app --reload --log-level debug "$@"
