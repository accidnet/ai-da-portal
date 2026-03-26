# ai-da-portal

`ai-da-portal`은 포털 서비스를 위한 작은 모노레포 프로젝트입니다.
현재는 Vue 3 기반 프론트엔드 프로토타입과 Python 백엔드 스캐폴드를 함께 관리하고 있습니다.

## 프로젝트 구조

- `portal-web`: Vue 3 + TypeScript + Vite 기반 프론트엔드
- `portal-onl`: `uv`로 관리하는 Python 백엔드 패키지
- `AGENTS.md`: 에이전트 및 협업 작업을 위한 저장소 운영 가이드

## 현재 상태

- 프론트엔드: 포털 대시보드 형태의 UI가 구성되어 있습니다.
- 백엔드: 최소 실행 구조만 갖춘 초기 스캐폴드 상태입니다.
- 루트 문서: 저장소 전체 구조와 개발 흐름을 설명합니다.

## 시작하기

### 프론트엔드 실행

```bash
cd portal-web
npm install
npm run dev
```

프론트엔드 빌드:

```bash
cd portal-web
npm run build
```

### 백엔드 실행

```bash
cd portal-onl
uv sync
uv run portal-onl
```

## 개발 메모

- 프론트엔드 코드는 `portal-web/src` 아래에서 작업합니다.
- 백엔드 코드는 `portal-onl/src/portal_onl` 아래에서 작업합니다.
- 프로젝트 구조, 실행 방법, 아키텍처가 바뀌면 이 README도 함께 업데이트합니다.
