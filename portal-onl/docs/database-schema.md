# Database Schema

## 테이블

### `sessions`

채팅 세션의 최소 메타데이터입니다.

| column         | type     | nullable | description                            |
| -------------- | -------- | -------- | -------------------------------------- |
| `id`           | string   | no       | 세션 ID                                |
| `workspace_id` | string   | yes      | `workspaces.id` FK. null이면 일반 세션 |
| `title`        | string   | no       | 세션 제목                              |
| `created_at`   | datetime | no       | 생성 시각                              |
| `updated_at`   | datetime | no       | 마지막 갱신 시각                       |

### `datasets`

데이터셋의 논리적 정의와 표시 메타데이터입니다. 실제 원천 연결과 파일별 preview/profile은 하위 테이블로 분리합니다.

| column        | type     | nullable | description                              |
| ------------- | -------- | -------- | ---------------------------------------- |
| `id`          | string   | no       | 데이터셋 ID                              |
| `name`        | string   | yes      | 사용자가 지정한 데이터셋 명              |
| `description` | text     | yes      | 데이터셋 설명                            |
| `created_at`  | datetime | no       | 생성 시각                                |
| `updated_at`  | datetime | no       | 마지막 갱신 시각                         |

### `dataset_sources`

데이터셋에 연결된 원천 파일 또는 향후 DB 테이블/컬럼을 추적하는 lineage 테이블입니다. 폴더를 선택해도 서버에서 하위 파일을 확장해 파일 단위 row를 저장합니다.

| column          | type     | nullable | description                                                        |
| --------------- | -------- | -------- | ------------------------------------------------------------------ |
| `id`            | string   | no       | 데이터셋 원천 연결 ID                                              |
| `dataset_id`    | string   | no       | `datasets.id` FK                                                   |
| `source_ref_id` | string   | yes      | `data_source_items.id`. 레거시 직접 업로드는 null 가능             |
| `created_at`    | datetime | no       | 생성 시각                                                          |

원천 데이터 선택 기반 데이터셋은 하위 파일 전체를 `dataset_sources`에 연결합니다. 실제 파일 경로, 크기, MIME type 등은 `data_source_items`를 그대로 참조합니다.

### `dataset_source_profiles`

데이터셋 등록 API 호출 중 계산한 원천 파일별 preview/profile 스냅샷입니다. 조회 API는 이 값을 우선 사용하고, 스냅샷이 없는 레거시 row만 원천 파일을 다시 읽어 계산합니다.

| column              | type     | nullable | description                                  |
| ------------------- | -------- | -------- | -------------------------------------------- |
| `id`                | string   | no       | 프로파일 스냅샷 ID                           |
| `dataset_source_id` | string   | no       | `dataset_sources.id` FK. 파일 연결 단위      |
| `row_count`         | integer  | no       | 등록 시점 원천 파일 행 수                    |
| `column_count`      | integer  | no       | 등록 시점 원천 파일 컬럼 수                  |
| `preview`           | json     | yes      | 등록 시점 preview payload                    |
| `profile`           | json     | yes      | 등록 시점 profile payload                    |
| `created_at`        | datetime | no       | 생성 시각                                    |

`dataset_source_id`는 unique입니다. 즉 하나의 `dataset_sources` row는 하나의 파일별 스냅샷만 가집니다.

### `data_source_items`

원천 데이터 파일/폴더 트리를 DB에서 재현하기 위한 flat 노드 테이블입니다. 실제 파일은 flat storage에 저장하고, 트리 구조는 `relative_path`, `parent_id`, `depth`로 복원합니다.

| column          | type     | nullable | description                                      |
| --------------- | -------- | -------- | ------------------------------------------------ |
| `id`            | string   | no       | 파일/폴더 노드 ID                                |
| `parent_id`     | string   | yes      | 상위 `data_source_items.id` FK                   |
| `item_type`     | string   | no       | `file` 또는 `folder`                             |
| `name`          | string   | no       | 파일/폴더 이름                                   |
| `relative_path` | text     | no       | 업로드 루트 기준 상대 경로                       |
| `depth`         | integer  | no       | 트리 깊이                                        |
| `sort_order`    | integer  | no       | 동일 레벨 표시 순서                              |
| `content_type`  | string   | yes      | 파일 MIME type                                   |
| `size_bytes`    | integer  | yes      | 파일 크기. 폴더는 null                           |
| `storage_path`  | text     | yes      | flat 저장소의 실제 파일 경로. 폴더는 null        |
| `created_at`    | datetime | no       | 생성 시각                                        |
| `updated_at`    | datetime | no       | 마지막 갱신 시각                                 |

`relative_path`는 unique입니다.

### `workspaces`

사용자가 생성한 포털 워크스페이스의 최소 메타데이터입니다.

| column       | type     | nullable | description        |
| ------------ | -------- | -------- | ------------------ |
| `id`         | string   | no       | 워크스페이스 ID    |
| `name`       | string   | no       | 워크스페이스 이름  |
| `created_at` | datetime | no       | 생성 시각          |
| `updated_at` | datetime | no       | 마지막 갱신 시각   |

지원 API는 생성, 목록 조회, 이름 변경, 삭제입니다.

워크스페이스와 세션은 `workspaces` 1:N `sessions` 관계입니다. 워크스페이스 전용 채팅은 기존 `sessions` row에 `workspace_id`를 저장해 구분합니다.

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
