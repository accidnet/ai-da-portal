# portal-onl

FastAPI-based data analysis AI backend scaffold for the portal.

## Stack

- FastAPI for API routing and schema contracts
- LangGraph-oriented agent package for chat and analysis orchestration
- Pandas-based tool layer for dataset profiling and analysis execution
- SQLAlchemy and storage modules prepared for persistence work

## Setup

```bash
uv sync
```

If you need to align Python locally first:

```bash
uv python install 3.13
uv venv --python 3.13
uv sync
```

## Run

```bash
uv run uvicorn --app-dir src main:app --reload
```

개발용 설정으로 실행하려면 `PORTAL_ENV=dev`를 주고 실행하면 `.env.dev`가 함께 로드되며, 콘솔 로그 레벨도 `DEBUG`까지 출력됩니다.

```bash
PORTAL_ENV=dev uv run uvicorn --app-dir src main:app --reload
```

기본 제공되는 `./.env.dev`에는 로컬 개발용 값이 들어 있습니다.

If your shell does not pick up `pyenv` or `uv` cleanly, use the local wrapper instead:

```powershell
.\scripts\dev.ps1
```

리포지토리 루트에서는 아래 스크립트도 동일하게 `dev` 프로필을 적용해 실행합니다.

```bash
./scripts/portal-onl-dev.sh
```

## Test

```bash
uv run pytest
```

If you want to bypass shell Python resolution entirely, use:

```powershell
.\scripts\test.ps1
```

## API surface

- `GET /api/v1/health`
- `POST /api/v1/sessions`
- `POST /api/v1/chat/messages`
- `POST /api/v1/datasets/upload`
- `POST /api/v1/analyses`

## Notes

- Current services return placeholder data so `portal-web` can integrate against stable response contracts first.
- The implementation plan lives in `portal-onl/docs/data-analysis-agent-backend-plan.md`.
