# ai-da-portal

`ai-da-portal`은 포털 서비스를 위한 모노레포 프로젝트입니다.
현재는 Vue 3 기반 프론트엔드와 Python 백엔드를 함께 관리하고 있습니다.

## 프로젝트 구조

- `portal-web`: Vue 3 + TypeScript + Vite 기반 프론트엔드
- `portal-onl`: `uv`로 관리하는 Python 백엔드 패키지

## 시작하기

### 개발 서버 실행 스크립트

루트 `scripts` 폴더에서 각 앱의 개발 서버를 바로 실행할 수 있습니다.

```bash
./scripts/portal-onl-dev.sh
./scripts/portal-web-dev.sh
```

사전 준비:

- `portal-onl`: `uv sync`
- `portal-web`: `cd portal-web && npm install`

### 프론트엔드 실행

```bash
cd portal-web
npm install
npm run dev
```

### 백엔드 실행

```bash
cd portal-onl
uv sync
uv run uvicorn --app-dir src main:app --reload
```

프론트엔드 빌드:

```bash
cd portal-web
npm run build
```
