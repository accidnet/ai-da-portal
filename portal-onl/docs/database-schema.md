# Database Schema

## 테이블

### `sessions`

채팅 세션의 최소 메타데이터입니다.

| column       | type     | nullable | description      |
| ------------ | -------- | -------- | ---------------- |
| `id`         | string   | no       | 세션 ID          |
| `title`      | string   | no       | 세션 제목        |
| `created_at` | datetime | no       | 생성 시각        |
| `updated_at` | datetime | no       | 마지막 갱신 시각 |

### `datasets`

업로드 데이터셋의 파일 메타데이터와 미리 계산한 preview/profile입니다.

| column         | type     | nullable | description            |
| -------------- | -------- | -------- | ---------------------- |
| `id`           | string   | no       | 데이터셋 ID            |
| `filename`     | string   | no       | 업로드 파일명          |
| `storage_path` | text     | no       | 저장 경로              |
| `preview`      | json     | yes      | 데이터 preview payload |
| `profile`      | json     | yes      | 데이터 profile payload |
| `created_at`   | datetime | no       | 생성 시각              |

### `workspaces`

사용자가 생성한 포털 워크스페이스의 최소 메타데이터입니다.

| column       | type     | nullable | description        |
| ------------ | -------- | -------- | ------------------ |
| `id`         | string   | no       | 워크스페이스 ID    |
| `name`       | string   | no       | 워크스페이스 이름  |
| `created_at` | datetime | no       | 생성 시각          |
| `updated_at` | datetime | no       | 마지막 갱신 시각   |

지원 API는 생성, 목록 조회, 이름 변경, 삭제입니다.

### `user_messages`

사용자가 입력한 원문 메시지입니다.

| column       | type     | nullable | description      |
| ------------ | -------- | -------- | ---------------- |
| `id`         | string   | no       | 사용자 메시지 ID |
| `session_id` | string   | no       | `sessions.id` FK |
| `text`       | text     | no       | 사용자 입력 원문 |
| `created_at` | datetime | no       | 생성 시각        |

### `user_message_dataset_links`

사용자 메시지 시점에 참조된 데이터셋 연결입니다. 세션 단위 dataset link는 사용하지 않습니다.

| column            | type     | nullable | description           |
| ----------------- | -------- | -------- | --------------------- |
| `user_message_id` | string   | no       | `user_messages.id` FK |
| `dataset_id`      | string   | no       | 참조 데이터셋 ID      |
| `linked_at`       | datetime | no       | 연결 시각             |

Primary key는 `user_message_id`, `dataset_id` 조합입니다.

### `agent_runs`

사용자 메시지 1개에 대응하는 agent 실행 그룹입니다.

| column            | type     | nullable | description           |
| ----------------- | -------- | -------- | --------------------- |
| `id`              | string   | no       | agent run ID          |
| `session_id`      | string   | no       | `sessions.id` FK      |
| `user_message_id` | string   | no       | `user_messages.id` FK |
| `created_at`      | datetime | no       | 생성 시각             |

### `agent_iterations`

agent 실행 내부의 LLM API 1회 호출 단위입니다.

| column            | type     | nullable | description             |
| ----------------- | -------- | -------- | ----------------------- |
| `id`              | string   | no       | iteration ID            |
| `agent_run_id`    | string   | no       | `agent_runs.id` FK      |
| `iteration_index` | integer  | no       | run 내부 iteration 순번 |
| `created_at`      | datetime | no       | 생성 시각               |

### `agent_timeline_items`

프론트 복원과 다음 LLM input 재사용을 위한 source of truth입니다.

| column                | type     | nullable | description                                         |
| --------------------- | -------- | -------- | --------------------------------------------------- |
| `id`                  | string   | no       | timeline item ID                                    |
| `session_id`          | string   | no       | `sessions.id` FK                                    |
| `user_message_id`     | string   | yes      | 관련 `user_messages.id` FK                          |
| `agent_run_id`        | string   | yes      | 관련 `agent_runs.id` FK                             |
| `agent_iteration_id`  | string   | yes      | 관련 `agent_iterations.id` FK                       |
| `sequence`            | integer  | no       | 세션 내 timeline 순번                               |
| `input_item`          | json     | yes      | 다음 LLM input에 재사용 가능한 item payload         |
| `stream_event_type`   | string   | yes      | 프론트에 보낸 SSE event type 또는 복원용 event type |
| `stream_payload`      | json     | yes      | 프론트에 보낸 payload 또는 done 기준 완성 payload   |
| `is_frontend_visible` | boolean  | no       | 과거 세션 히스토리 조회 시 노출 여부                |
| `is_input_reusable`   | boolean  | no       | 다음 LLM API input 구성에 재사용할지 여부           |
| `created_at`          | datetime | no       | 생성 시각                                           |
