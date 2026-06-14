# ai-da-portal

`ai-da-portal`은 포털 서비스를 위한 모노레포 프로젝트입니다.
현재는 Vue 3 기반 프론트엔드와 Python 백엔드를 함께 관리하고 있습니다.

## 프로젝트 구조

- `portal-web`: Vue 3 + TypeScript + Vite 기반 프론트엔드
- `portal-onl`: `uv`로 관리하는 Python 백엔드 패키지

## 시작하기

### 사전 준비

개발 서버를 실행하기 전에 아래 런타임이 먼저 설치되어 있어야 합니다.

- Node.js 24.x
- Python 3.13.x
- `uv`
  - `uv`는 Python이 설치되어 있을 경우 `pip install uv`로 쉽게 설치가 가능합니다.

처음 실행하는 경우 각 앱의 의존성을 먼저 설치합니다.

```bash
# 백엔드 의존성 설치
cd portal-onl
uv sync
```

```bash
# 프론트엔드 의존성 설치
cd portal-web
npm install
```

### 백엔드 실행

리포지토리 루트에서 백엔드 개발 서버 스크립트를 실행합니다.

```bash
./scripts/portal-onl-dev.sh
```

### 프론트엔드 실행

리포지토리 루트에서 프론트엔드 개발 서버 스크립트를 실행합니다.

```bash
./scripts/portal-web-dev.sh
```

실행 후 브라우저에서 `http://localhost:5173`으로 접속합니다.