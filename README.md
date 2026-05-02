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

- `portal-onl`: `python -m venv. venv && uv sync`
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

개발용 `.env.dev`를 적용해서 실행하려면 아래처럼 실행하면 됩니다. 이 경우 백엔드는 `DEBUG` 레벨 로그까지 콘솔에 출력합니다.

```bash
cd portal-onl
PORTAL_ENV=dev uv run uvicorn --app-dir src main:app --reload
```

또는 루트 스크립트로 바로 실행할 수 있습니다.

```bash
./scripts/portal-onl-dev.sh
```

프론트엔드 빌드:

```bash
cd portal-web
npm run build
```

## 백엔드 도구 definition 작성 가이드

`portal-onl`의 agent tool definition은 외부 LLM API에 전달할 수 있는 JSON Schema 형태의 Python dict로 작성합니다.
도구를 추가할 때는 아래 구조를 기준으로 작성합니다.

- `type`: 항상 `"function"`을 사용합니다.
- `name`: 모델이 호출할 함수명입니다. 실제 registry에 등록된 도구명과 일치해야 합니다.
- `description`: 도구가 언제, 왜 필요한지 한두 문장으로 설명합니다.
- `parameters`: 함수 인자 스키마입니다. 최상위는 `"type": "object"`를 사용합니다.
- `properties`: 각 인자의 타입, 설명, enum, items 등을 정의합니다.
- `required`: 필수 인자명을 명시합니다.
- `additionalProperties`: 예상하지 않은 인자 전달을 막기 위해 `False`로 둡니다.

예시:

```python
_PLAN_STATUSES = ("pending", "in_progress", "completed")

tool_definition = {
    "type": "function",
    "name": "update_plan",
    "description": (
        "복잡한 작업을 위한 진행 계획을 갱신합니다. 선택적으로 explanation을 포함할 수 있고, "
        "plan에는 step과 status를 가진 단계 목록을 전달해야 합니다. "
        "동시에 in_progress는 최대 하나만 허용됩니다."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "explanation": {
                "type": "string",
                "description": "계획을 새로 만들거나 수정한 이유를 짧게 설명합니다.",
            },
            "plan": {
                "type": "array",
                "description": "현재 작업 계획 단계 목록입니다.",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {
                            "type": "string",
                            "description": "짧고 검증 가능한 작업 단계입니다.",
                        },
                        "status": {
                            "type": "string",
                            "enum": list(_PLAN_STATUSES),
                            "description": (
                                f"{', '.join(_PLAN_STATUSES)} 중 하나입니다."
                            ),
                        },
                    },
                    "required": ["step", "status"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["plan"],
        "additionalProperties": False,
    },
}
```

작성 기준:

- 모델이 선택하기 쉽도록 `description`에는 구현 세부사항보다 사용 조건과 입력 의미를 적습니다.
- 인자는 가능한 구체적인 타입으로 제한하고, 선택지가 정해진 값은 `enum`으로 표현합니다.
- 배열 객체의 `items`에도 `required`와 `additionalProperties: False`를 명시합니다.
- 실제 실행 함수에서는 definition을 신뢰하지 말고 필수값, enum, 개수 제한 같은 런타임 검증을 한 번 더 수행합니다.
