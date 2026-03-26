# AGENTS.md

## 저장소 개요

이 저장소는 `ai-da-portal` 프로젝트를 포함합니다.

- `portal-web`: Vue 3 + TypeScript + Vite 기반 프론트엔드
- `portal-onl`: `uv`로 관리하는 Python 백엔드 스캐폴드
- 루트 문서는 프로젝트의 전체 구조와 실행 방법을 설명하며 구현 변화와 함께 유지합니다.

## 작업 원칙

- 기존 구조와 흐름에 맞는 작고 집중된 변경을 우선합니다.
- 이미 작업 트리에 있는 사용자 변경사항은 보존합니다.
- 명령어, 구조, 동작 방식이 바뀌면 관련 문서도 함께 갱신합니다.
- 꼭 필요한 경우가 아니면 넓은 범위의 리팩터링은 피합니다.

## 프론트엔드 가이드

- 메인 진입점은 `portal-web/src/App.vue`입니다.
- 포털 UI 관련 코드는 주로 `portal-web/src/features/portal` 아래에 있습니다.
- Vue 3 Composition API와 TypeScript 패턴을 따릅니다.
- 가능하면 표시용 데이터와 UI 컴포넌트 책임을 분리합니다.

## 백엔드 가이드

- 백엔드 패키지는 `portal-onl/src/portal_onl`에 있습니다.
- 의존성 설치와 실행은 `uv` 기준으로 진행합니다.
- Python 코드는 단순하고 읽기 쉽게 유지하며 가능하면 타입을 명시합니다.
- 현재 백엔드는 스캐폴드 단계이므로, 요구사항이 생기기 전까지는 과도한 구조 확장을 피합니다.

## 권장 작업 흐름

1. 구조나 실행 방식을 바꾸기 전에 관련 패키지 파일과 문서를 먼저 확인합니다.
2. 요청을 해결하는 가장 작은 단위의 변경부터 적용합니다.
3. 가능하면 변경 범위에 맞는 검증만 빠르게 실행합니다.
4. 저장소 전반에 영향이 있는 변경은 `README.md` 또는 각 패키지 문서에 반영합니다.

## 공통 명령어

```bash
# frontend
cd portal-web && npm run dev
cd portal-web && npm run build

# backend
cd portal-onl && uv sync
cd portal-onl && uv run portal-onl
```
