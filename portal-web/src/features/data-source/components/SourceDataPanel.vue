<script setup lang="ts">
import { computed, ref } from "vue";

import type {
  DataSourceItem,
  UploadPickerMode,
} from "@/features/data-source/types";

const props = defineProps<{
  items: DataSourceItem[];
}>();

const emit = defineEmits<{
  uploadFile: [mode: UploadPickerMode];
}>();

type SourceDetail = "upload" | "db";

const activeDetail = ref<SourceDetail>("upload");
const collapsedFolderIds = ref<Set<string>>(new Set());

/** 원천 데이터 파일 목록을 폴더 접힘 상태를 반영해 정리합니다. */
const uploadedItems = computed(() => {
  return flattenVisibleItems(props.items);
});

/** 트리 응답을 파일 브라우저 행 목록으로 펼치되 접힌 폴더 하위는 제외합니다. */
function flattenVisibleItems(items: DataSourceItem[]): DataSourceItem[] {
  const sortedItems = [...items].sort((left, right) => {
    if (left.itemType !== right.itemType) {
      return left.itemType === "folder" ? -1 : 1;
    }
    return left.name.localeCompare(right.name);
  });

  return sortedItems.flatMap((item) => {
    if (item.itemType !== "folder" || collapsedFolderIds.value.has(item.id)) {
      return [item];
    }
    return [item, ...flattenVisibleItems(item.children)];
  });
}

/** 원천 데이터 노드의 상태 텍스트를 반환합니다. */
function formatStatus(item: DataSourceItem): string {
  if (item.itemType === "folder") {
    return collapsedFolderIds.value.has(item.id) ? "접힘" : "열림";
  }
  return "등록됨";
}

/** 폴더 행 클릭 시 하위 항목을 접거나 펼칩니다. */
function toggleFolder(item: DataSourceItem) {
  if (item.itemType !== "folder") return;

  const nextCollapsedIds = new Set(collapsedFolderIds.value);
  if (nextCollapsedIds.has(item.id)) {
    nextCollapsedIds.delete(item.id);
  } else {
    nextCollapsedIds.add(item.id);
  }
  collapsedFolderIds.value = nextCollapsedIds;
}

/** 파일 브라우저 행 클릭을 처리합니다. */
function handleItemClick(item: DataSourceItem) {
  toggleFolder(item);
}

/** 등록일을 파일 목록 표시용 날짜로 변환합니다. */
function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** 원천 데이터 상세 패널을 전환합니다. */
function setActiveDetail(detail: SourceDetail) {
  activeDetail.value = detail;
}
</script>

<template>
  <section class="source-workspace">
    <div class="source-action-grid">
      <article
        class="panel-card source-action-card source-action-card--primary"
        :class="{ 'source-action-card--active': activeDetail === 'upload' }"
        role="button"
        tabindex="0"
        @click="setActiveDetail('upload')"
        @keydown.enter="setActiveDetail('upload')"
      >
        <div class="source-action-card__icon">
          <span class="material-symbols-outlined">upload_file</span>
        </div>
        <div class="source-action-card__body">
          <p>직접 업로드</p>
          <h3>데이터 직접 업로드</h3>
          <span
            >파일 여러 개를 선택하거나 폴더 전체를 원천 데이터로 등록할 수
            있습니다.</span
          >
        </div>
      </article>

      <article
        class="panel-card source-action-card"
        :class="{ 'source-action-card--active': activeDetail === 'db' }"
        role="button"
        tabindex="0"
        @click="setActiveDetail('db')"
        @keydown.enter="setActiveDetail('db')"
      >
        <div class="source-action-card__icon">
          <span class="material-symbols-outlined">dns</span>
        </div>
        <div class="source-action-card__body">
          <p>DB 연결</p>
          <h3>운영 DB 또는 분석 DB를 원천 데이터로 연결</h3>
          <span>연결 정보와 테이블 선택 기능은 준비 중입니다.</span>
        </div>
        <button type="button" class="toolbar-button" disabled @click.stop>
          연결 준비중
        </button>
      </article>
    </div>

    <section v-if="activeDetail === 'upload'" class="panel-card source-detail-panel">
      <header class="source-detail-header">
        <div>
          <p>업로드 파일 관리</p>
          <h3>원천 데이터 디렉토리</h3>
          <span>업로드된 파일과 폴더 항목을 탐색하고 수정, 이동, 삭제 작업을 준비합니다.</span>
        </div>
        <div class="source-detail-actions">
          <button type="button" class="toolbar-button toolbar-button--primary" @click="emit('uploadFile', 'files')">
            파일 추가
          </button>
          <button type="button" class="toolbar-button" @click="emit('uploadFile', 'folder')">
            폴더 추가
          </button>
        </div>
      </header>

      <div class="source-file-toolbar">
        <button type="button" class="file-tool-button" disabled>
          <span class="material-symbols-outlined">drive_file_rename_outline</span>
          이름 변경
        </button>
        <button type="button" class="file-tool-button" disabled>
          <span class="material-symbols-outlined">drive_file_move</span>
          이동
        </button>
        <button type="button" class="file-tool-button" disabled>
          <span class="material-symbols-outlined">delete</span>
          삭제
        </button>
      </div>

      <div class="source-file-browser">
        <div class="source-file-browser__head">
          <span>이름</span>
          <span>등록일</span>
          <span>상태</span>
          <span>관리</span>
        </div>
        <div class="source-file-browser__body">
          <div v-if="uploadedItems.length === 0" class="source-file-empty">
            <span class="material-symbols-outlined">folder_open</span>
            아직 업로드된 원천 데이터가 없습니다.
          </div>
          <template v-else>
            <button
              v-for="dataset in uploadedItems"
              :key="dataset.id"
              type="button"
              class="source-file-row"
              :class="{ 'source-file-row--folder': dataset.itemType === 'folder' }"
              :style="{ '--file-depth': dataset.depth }"
              :aria-expanded="
                dataset.itemType === 'folder'
                  ? !collapsedFolderIds.has(dataset.id)
                  : undefined
              "
              @click="handleItemClick(dataset)"
            >
              <span class="source-file-name">
                <span
                  v-if="dataset.itemType === 'folder'"
                  class="material-symbols-outlined source-folder-caret"
                >
                  {{ collapsedFolderIds.has(dataset.id) ? "chevron_right" : "expand_more" }}
                </span>
                <span v-else class="source-folder-caret"></span>
                <span class="material-symbols-outlined">
                  {{ dataset.itemType === "folder" ? "folder" : "description" }}
                </span>
                <span>
                  <strong>{{ dataset.name }}</strong>
                  <small>{{ dataset.relativePath }}</small>
                </span>
              </span>
              <span>{{ formatDate(dataset.createdAt) }}</span>
              <span class="source-file-status">{{ formatStatus(dataset) }}</span>
              <span class="source-file-controls">
                <span class="material-symbols-outlined">more_horiz</span>
              </span>
            </button>
          </template>
        </div>
      </div>
    </section>

    <section v-else class="panel-card source-detail-panel source-detail-panel--pending">
      <div class="source-pending-icon">
        <span class="material-symbols-outlined">dns</span>
      </div>
      <div>
        <p>DB 연결</p>
        <h3>DB 원천 데이터 연결 준비중</h3>
        <span>연결 정보 등록, 테이블 선택, 스키마 미리보기 화면이 이 영역에 배치될 예정입니다.</span>
      </div>
    </section>
  </section>
</template>

<style scoped>
.source-workspace {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 16px;
}

.panel-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--color-shadow);
}

.source-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.source-action-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  padding: 20px;
  cursor: pointer;
}

.source-action-card--primary {
  border-color: rgba(24, 74, 140, 0.28);
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.96),
    rgba(247, 250, 255, 0.92)
  );
}

.source-action-card--active {
  border-color: rgba(24, 74, 140, 0.46);
  box-shadow: 0 14px 28px rgba(24, 74, 140, 0.12);
}

.source-action-card__icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  color: var(--color-primary);
  background: rgba(24, 74, 140, 0.1);
}

.source-action-card__icon .material-symbols-outlined {
  font-size: 1.4rem;
}

.source-action-card__body {
  min-width: 0;
}

.source-action-card__body p {
  margin: 0 0 6px;
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.source-action-card__body h3 {
  margin: 0 0 6px;
  color: var(--color-text);
  font-size: 1rem;
  line-height: 1.35;
}

.toolbar-button {
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface-muted);
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
}

.source-upload-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.toolbar-button--primary {
  border-color: var(--color-primary);
  color: #fff;
  background: var(--color-primary);
}

.toolbar-button:disabled {
  opacity: 0.55;
  cursor: default;
}

.source-detail-panel {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 14px;
  padding: 18px 20px;
  overflow: hidden;
}

.source-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.source-detail-header p,
.source-detail-panel--pending p {
  margin: 0 0 6px;
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.source-detail-header h3,
.source-detail-panel--pending h3 {
  margin: 0 0 6px;
  color: var(--color-text);
  font-size: 1rem;
  line-height: 1.35;
}

.source-detail-header span,
.source-detail-panel--pending span {
  color: var(--color-text-muted);
}

.source-detail-actions,
.source-file-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.file-tool-button {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
  font: inherit;
}

.file-tool-button .material-symbols-outlined {
  font-size: 1rem;
}

.file-tool-button:disabled {
  opacity: 0.55;
}

.source-file-browser {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 12px;
}

.source-file-browser__head,
.source-file-row {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 140px 100px 64px;
  align-items: center;
  gap: 12px;
}

.source-file-browser__head {
  padding: 11px 14px;
  background: var(--color-surface-muted);
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.source-file-browser__body {
  min-height: 0;
  overflow: auto;
}

.source-file-row {
  width: 100%;
  padding: 12px 14px;
  border: 0;
  border-top: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.source-file-row--folder {
  background: rgba(248, 251, 255, 0.96);
}

.source-file-name {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding-left: calc(var(--file-depth, 0) * 18px);
}

.source-file-name .material-symbols-outlined {
  flex: 0 0 auto;
  color: var(--color-primary);
}

.source-folder-caret {
  width: 16px;
  min-width: 16px;
  color: var(--color-text-muted);
}

.source-file-name strong,
.source-file-name small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-file-name small {
  margin-top: 3px;
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.source-file-status {
  width: fit-content;
  padding: 6px 9px;
  border-radius: 999px;
  background: rgba(44, 139, 92, 0.12);
  color: #1d6b45;
  font-size: 0.76rem;
  font-weight: 800;
}

.source-file-controls {
  justify-self: end;
  color: var(--color-text-muted);
}

.source-file-empty {
  display: grid;
  place-items: center;
  gap: 8px;
  padding: 36px 14px;
  border-top: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

.source-detail-panel--pending {
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
}

.source-pending-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  color: var(--color-primary);
  background: rgba(24, 74, 140, 0.1);
}

@media (max-width: 900px) {
  .source-summary {
    display: grid;
  }

  .source-action-grid {
    grid-template-columns: 1fr;
  }

  .source-action-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .source-upload-actions,
  .source-detail-actions {
    grid-column: 1 / -1;
    justify-self: start;
  }

  .source-detail-header {
    display: grid;
  }

  .source-file-browser__body {
    overflow: auto;
  }

  .source-file-browser__head,
  .source-file-row {
    min-width: 680px;
  }
}

@media (max-width: 640px) {
  .source-action-card,
  .source-summary,
  .source-detail-panel {
    padding: 16px;
  }
}
</style>
