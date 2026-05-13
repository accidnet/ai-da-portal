<script setup lang="ts">
import { computed, ref } from "vue";

import type { DatasetLibraryItem } from "@/features/data-source/types";

const props = defineProps<{
  datasets: DatasetLibraryItem[];
  selectedDatasetId?: string | null;
  activeSessionId?: string | null;
  searchQuery: string;
  isBusy?: boolean;
  errorMessage?: string | null;
}>();

const emit = defineEmits<{
  searchChange: [value: string];
  selectDataset: [datasetId: string];
  attachDataset: [datasetId: string];
  detachDataset: [datasetId: string];
  deleteDataset: [datasetId: string];
}>();

const sortOrder = ref<"desc" | "asc">("desc");

/** 검색어와 정렬 상태를 반영한 데이터셋 카탈로그 목록입니다. */
const filteredDatasets = computed(() => {
  const keyword = props.searchQuery.trim().toLowerCase();
  const filtered = keyword
    ? props.datasets.filter((dataset) => {
        const haystacks = [dataset.filename, dataset.storagePath ?? ""];
        return haystacks.some((value) => value.toLowerCase().includes(keyword));
      })
    : props.datasets;

  return [...filtered].sort((left, right) => {
    const leftTime = new Date(left.createdAt).getTime();
    const rightTime = new Date(right.createdAt).getTime();
    return sortOrder.value === "desc"
      ? rightTime - leftTime
      : leftTime - rightTime;
  });
});

/** 현재 활성 세션과 데이터셋 연결 여부를 확인합니다. */
function isLinkedToActiveSession(dataset: DatasetLibraryItem): boolean {
  return Boolean(
    props.activeSessionId &&
      dataset.linkedSessionIds.includes(props.activeSessionId),
  );
}

/** 데이터셋 등록일을 화면 표시용 한국어 날짜로 변환합니다. */
function formatDate(value?: string | null): string {
  if (!value) return "없음";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** 데이터셋 카탈로그의 등록일 정렬 방향을 전환합니다. */
function toggleSortOrder() {
  sortOrder.value = sortOrder.value === "desc" ? "asc" : "desc";
}
</script>

<template>
  <section class="catalog-workspace">
    <section class="panel-card catalog-intro">
      <div>
        <p>데이터셋 카탈로그</p>
        <h3>등록된 원천 데이터를 분석용 데이터셋으로 구성</h3>
        <span>업로드 파일과 DB 소스를 선택해 세션에 연결할 데이터셋을 관리합니다.</span>
      </div>
      <button type="button" class="toolbar-button toolbar-button--primary" disabled>
        데이터셋 만들기 준비중
      </button>
    </section>

    <section class="panel-card library-toolbar">
      <label class="library-search">
        <span class="material-symbols-outlined">search</span>
        <input
          :value="searchQuery"
          type="search"
          placeholder="파일명, 타입, 경로 검색"
          @input="
            emit('searchChange', ($event.target as HTMLInputElement).value)
          "
        />
      </label>

      <div class="toolbar-actions">
        <button type="button" class="toolbar-button" disabled>필터 준비중</button>
        <button type="button" class="toolbar-button" disabled>
          스키마 보기 준비중
        </button>
      </div>
    </section>

    <p v-if="errorMessage" class="library-error">{{ errorMessage }}</p>

    <section class="panel-card dataset-table-shell">
      <header class="dataset-table-header">
        <strong>{{ filteredDatasets.length }}개 데이터셋</strong>
      </header>

      <div class="dataset-table-wrap">
        <table class="dataset-table">
          <thead>
            <tr>
              <th>파일명</th>
              <th>
                <button
                  type="button"
                  class="sort-button"
                  @click="toggleSortOrder"
                >
                  등록일
                  <span class="material-symbols-outlined">filter_list</span>
                  <small>{{
                    sortOrder === "desc" ? "최신순" : "오래된순"
                  }}</small>
                </button>
              </th>
              <th>상태</th>
              <th>연결 세션</th>
              <th class="dataset-table__actions">동작</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="dataset in filteredDatasets"
              :key="dataset.id"
              class="dataset-row"
              :class="{
                'dataset-row--selected': dataset.id === selectedDatasetId,
                'dataset-row--linked': isLinkedToActiveSession(dataset),
              }"
              @click="emit('selectDataset', dataset.id)"
            >
              <td>
                <div class="dataset-name-cell">
                  <strong>{{ dataset.filename }}</strong>
                  <span>{{ dataset.storagePath ?? "저장 경로 미지정" }}</span>
                </div>
              </td>
              <td>{{ formatDate(dataset.createdAt) }}</td>
              <td>
                <span
                  class="status-badge"
                  :class="
                    isLinkedToActiveSession(dataset)
                      ? 'status-badge--linked'
                      : 'status-badge--idle'
                  "
                >
                  {{
                    isLinkedToActiveSession(dataset)
                      ? "활성 세션 연결됨"
                      : "미연결"
                  }}
                </span>
              </td>
              <td>{{ dataset.linkedSessionCount }}개</td>
              <td class="dataset-table__actions">
                <div class="row-actions">
                  <button
                    v-if="!isLinkedToActiveSession(dataset)"
                    type="button"
                    class="action-button action-button--primary"
                    :disabled="isBusy || !activeSessionId"
                    @click.stop="emit('attachDataset', dataset.id)"
                  >
                    연결
                  </button>
                  <button
                    v-else
                    type="button"
                    class="action-button"
                    :disabled="isBusy || !activeSessionId"
                    @click.stop="emit('detachDataset', dataset.id)"
                  >
                    해제
                  </button>
                  <button
                    type="button"
                    class="action-button action-button--danger"
                    :disabled="isBusy"
                    @click.stop="emit('deleteDataset', dataset.id)"
                  >
                    삭제
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="filteredDatasets.length === 0">
              <td colspan="5" class="empty-row">
                <span class="material-symbols-outlined">database_off</span>
                검색 조건에 맞는 데이터 소스가 없어요.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<style scoped>
.catalog-workspace {
  display: grid;
  gap: 16px;
}

.panel-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--color-shadow);
}

.catalog-intro,
.library-toolbar,
.dataset-table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px;
}

.catalog-intro p {
  margin: 0 0 6px;
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.catalog-intro h3 {
  margin: 0 0 6px;
  color: var(--color-text);
  font-size: 1rem;
  line-height: 1.35;
}

.catalog-intro span {
  color: var(--color-text-muted);
}

.library-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 16px;
  background: var(--color-surface-muted);
}

.library-search input {
  width: 100%;
  border: 0;
  background: transparent;
}

.library-search input:focus {
  outline: none;
}

.toolbar-actions,
.row-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.toolbar-button,
.action-button,
.sort-button {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface-muted);
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
}

.toolbar-button,
.action-button {
  min-height: 40px;
  padding: 0 14px;
}

.toolbar-button--primary,
.action-button--primary {
  border-color: var(--color-primary);
  color: #fff;
  background: var(--color-primary);
}

.action-button--danger {
  color: #9b3b3b;
}

.toolbar-button:disabled,
.action-button:disabled {
  opacity: 0.55;
  cursor: default;
}

.library-error {
  margin: 0;
  color: #9b3b3b;
  font-size: 0.86rem;
}

.dataset-table-shell {
  min-height: 0;
  display: grid;
}

.dataset-table-header {
  padding-bottom: 12px;
}

.dataset-table-wrap {
  overflow: auto;
}

.dataset-table {
  width: 100%;
  min-width: 880px;
  border-collapse: collapse;
}

.dataset-table th,
.dataset-table td {
  padding: 16px 22px;
  border-top: 1px solid var(--color-border);
  text-align: left;
  vertical-align: middle;
}

.dataset-table th {
  color: var(--color-text-soft);
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.sort-button {
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: inherit;
}

.sort-button small {
  color: var(--color-text-muted);
  font-size: 0.72rem;
}

.dataset-name-cell {
  display: grid;
  gap: 4px;
}

.dataset-name-cell strong {
  color: var(--color-text);
}

.dataset-name-cell span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.dataset-row {
  cursor: pointer;
}

.dataset-row--selected {
  background: rgba(24, 74, 140, 0.03);
}

.dataset-row--linked {
  background: rgba(24, 74, 140, 0.06);
}

.status-badge {
  display: inline-flex;
  padding: 7px 10px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 700;
}

.status-badge--linked {
  color: #1d6b45;
  background: rgba(44, 139, 92, 0.12);
}

.status-badge--idle {
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
}

.dataset-table__actions {
  width: 1%;
  white-space: nowrap;
}

.empty-row {
  color: var(--color-text-muted);
  text-align: center;
}

.empty-row .material-symbols-outlined {
  margin-right: 6px;
  vertical-align: middle;
}

@media (max-width: 900px) {
  .catalog-intro,
  .library-toolbar {
    display: grid;
  }
}

@media (max-width: 640px) {
  .catalog-intro,
  .library-toolbar,
  .dataset-table-header {
    padding: 16px;
  }
}
</style>
