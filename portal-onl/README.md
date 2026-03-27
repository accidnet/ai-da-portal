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
uv run uvicorn portal_onl.main:app --reload
```

## Test

```bash
uv run pytest
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
