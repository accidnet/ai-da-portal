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

/** 활성 세션에 연결된 데이터셋 수를 요약 카드에 표시합니다. */
const linkedDatasetCount = computed(() => {
  return props.datasets.filter((dataset) => isLinkedToActiveSession(dataset)).length;
});

/** 카탈로그 전체 데이터 규모를 행 기준으로 합산합니다. */
const totalRowCount = computed(() => {
  return props.datasets.reduce((total, dataset) => total + dataset.rowCount, 0);
});

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

/** 큰 숫자를 데이터셋 메타 정보에 맞게 간결한 문자열로 변환합니다. */
function formatNumber(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

/** 데이터셋 카탈로그의 등록일 정렬 방향을 전환합니다. */
function toggleSortOrder() {
  sortOrder.value = sortOrder.value === "desc" ? "asc" : "desc";
}
</script>

<template>
  <section class="catalog-workspace">
    <section class="catalog-panel">
      <header class="catalog-header">
        <div class="catalog-title">
          <span class="catalog-title__icon material-symbols-outlined">dataset</span>
          <div>
            <p>데이터셋 카탈로그</p>
            <h3>분석에 연결할 데이터셋 관리</h3>
            <span>등록된 원천 데이터를 세션에 바로 연결하고 상태를 확인합니다.</span>
          </div>
        </div>
        <div class="catalog-header__actions">
          <button type="button" class="icon-button" disabled aria-label="필터">
            <span class="material-symbols-outlined">tune</span>
          </button>
          <button type="button" class="icon-button" disabled aria-label="스키마 보기">
            <span class="material-symbols-outlined">schema</span>
          </button>
          <button type="button" class="toolbar-button toolbar-button--primary" disabled>
            <span class="material-symbols-outlined">add</span>
            데이터셋 만들기
          </button>
        </div>
      </header>

      <div class="catalog-summary" aria-label="데이터셋 카탈로그 요약">
        <div class="summary-item">
          <span>전체</span>
          <strong>{{ formatNumber(datasets.length) }}</strong>
        </div>
        <div class="summary-item">
          <span>활성 연결</span>
          <strong>{{ formatNumber(linkedDatasetCount) }}</strong>
        </div>
        <div class="summary-item">
          <span>누적 행</span>
          <strong>{{ formatNumber(totalRowCount) }}</strong>
        </div>
      </div>

      <div class="library-toolbar">
        <label class="library-search">
          <span class="material-symbols-outlined">search</span>
          <input
            :value="searchQuery"
            type="search"
            placeholder="파일명 또는 저장 경로 검색"
            @input="
              emit('searchChange', ($event.target as HTMLInputElement).value)
            "
          />
        </label>

        <button type="button" class="sort-button" @click="toggleSortOrder">
          <span class="material-symbols-outlined">swap_vert</span>
          {{ sortOrder === "desc" ? "최신순" : "오래된순" }}
        </button>
      </div>

      <p v-if="errorMessage" class="library-error">{{ errorMessage }}</p>

      <header class="dataset-list-header">
        <strong>{{ formatNumber(filteredDatasets.length) }}개 데이터셋</strong>
        <span>선택한 행은 상세 미리보기와 세션 연결 작업에 사용됩니다.</span>
      </header>

      <div class="dataset-table-wrap">
        <table class="dataset-table">
          <thead>
            <tr>
              <th>파일명</th>
              <th>등록일</th>
              <th>규모</th>
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
              <td data-label="등록일">{{ formatDate(dataset.createdAt) }}</td>
              <td data-label="규모">
                {{ formatNumber(dataset.rowCount) }}행 ·
                {{ formatNumber(dataset.columnCount) }}열
              </td>
              <td data-label="상태">
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
              <td data-label="연결 세션">{{ dataset.linkedSessionCount }}개</td>
              <td class="dataset-table__actions">
                <div class="row-actions">
                  <button
                    v-if="!isLinkedToActiveSession(dataset)"
                    type="button"
                    class="action-button action-button--primary"
                    :disabled="isBusy || !activeSessionId"
                    @click.stop="emit('attachDataset', dataset.id)"
                  >
                    <span class="material-symbols-outlined">link</span>
                    연결
                  </button>
                  <button
                    v-else
                    type="button"
                    class="action-button"
                    :disabled="isBusy || !activeSessionId"
                    @click.stop="emit('detachDataset', dataset.id)"
                  >
                    <span class="material-symbols-outlined">link_off</span>
                    해제
                  </button>
                  <button
                    type="button"
                    class="action-button action-button--danger"
                    :disabled="isBusy"
                    @click.stop="emit('deleteDataset', dataset.id)"
                  >
                    <span class="material-symbols-outlined">delete</span>
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
  min-height: 0;
  height: 100%;
}

.catalog-panel {
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--color-surface-strong);
  box-shadow: var(--color-shadow);
}

.catalog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px 16px;
  border-bottom: 1px solid var(--color-border);
}

.catalog-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
}

.catalog-title__icon {
  flex: 0 0 auto;
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.catalog-title p,
.catalog-title h3,
.catalog-title span {
  display: block;
}

.catalog-title p {
  margin: 0 0 6px;
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.catalog-title h3 {
  margin: 0 0 6px;
  color: var(--color-text);
  font-size: 1.08rem;
  line-height: 1.35;
}

.catalog-title span {
  color: var(--color-text-muted);
  font-size: 0.86rem;
  line-height: 1.45;
}

.catalog-header__actions {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.catalog-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(180deg, #fff 0%, #f8fafc 100%);
}

.summary-item {
  display: grid;
  gap: 4px;
  padding: 16px 22px;
  border-right: 1px solid var(--color-border);
}

.summary-item:last-child {
  border-right: 0;
}

.summary-item span {
  color: var(--color-text-muted);
  font-size: 0.75rem;
  font-weight: 800;
}

.summary-item strong {
  color: var(--color-text);
  font-size: 1.24rem;
  line-height: 1.1;
}

.library-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 22px;
  border-bottom: 1px solid var(--color-border);
  background: #fff;
}

.library-search {
  flex: 1;
  min-width: 220px;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 0 13px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: var(--color-surface-muted);
}

.library-search:focus-within {
  border-color: var(--color-primary);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(24, 74, 140, 0.12);
}

.library-search .material-symbols-outlined {
  color: var(--color-text-muted);
  font-size: 1.2rem;
}

.library-search input {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
}

.library-search input:focus {
  outline: none;
}

.row-actions {
  display: inline-flex;
  justify-content: flex-end;
  gap: 8px;
}

.toolbar-button,
.action-button,
.sort-button,
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-muted);
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
}

.toolbar-button,
.action-button,
.sort-button {
  min-height: 38px;
  padding: 0 12px;
  font-size: 0.84rem;
  font-weight: 800;
}

.icon-button {
  width: 38px;
  height: 38px;
  padding: 0;
}

.toolbar-button .material-symbols-outlined,
.action-button .material-symbols-outlined,
.sort-button .material-symbols-outlined,
.icon-button .material-symbols-outlined {
  font-size: 1.05rem;
}

.toolbar-button--primary,
.action-button--primary {
  border-color: var(--color-primary);
  color: #fff;
  background: var(--color-primary);
}

.action-button--danger {
  color: #a13b3b;
  background: #fff7f7;
}

.toolbar-button:hover:not(:disabled),
.action-button:hover:not(:disabled),
.sort-button:hover,
.icon-button:hover:not(:disabled),
.toolbar-button:focus-visible:not(:disabled),
.action-button:focus-visible:not(:disabled),
.sort-button:focus-visible,
.icon-button:focus-visible:not(:disabled) {
  border-color: var(--color-primary);
  outline: none;
}

.toolbar-button:disabled,
.action-button:disabled,
.icon-button:disabled {
  opacity: 0.55;
  cursor: default;
}

.library-error {
  margin: 0;
  padding: 12px 22px;
  border-bottom: 1px solid rgba(155, 59, 59, 0.18);
  color: #9b3b3b;
  background: #fff7f7;
  font-size: 0.86rem;
}

.dataset-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 22px;
  border-bottom: 1px solid var(--color-border);
  background: #fff;
}

.dataset-list-header strong {
  color: var(--color-text);
}

.dataset-list-header span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.dataset-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  background: #fff;
}

.dataset-table {
  width: 100%;
  min-width: 960px;
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
  background: #fbfcfe;
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
  transition:
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.dataset-row:hover {
  background: #f8fbff;
}

.dataset-row--selected {
  background: rgba(24, 74, 140, 0.05);
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.dataset-row--linked {
  background: rgba(24, 74, 140, 0.07);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
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
  padding: 44px 22px;
  color: var(--color-text-muted);
  text-align: center;
}

.empty-row .material-symbols-outlined {
  margin-right: 6px;
  vertical-align: middle;
}

@media (max-width: 900px) {
  .catalog-header,
  .library-toolbar {
    display: grid;
  }

  .catalog-header__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .toolbar-button--primary {
    flex: 1;
  }

  .dataset-list-header {
    align-items: flex-start;
    display: grid;
  }
}

@media (max-width: 640px) {
  .catalog-header,
  .library-toolbar,
  .dataset-list-header {
    padding: 16px;
  }

  .catalog-title {
    align-items: flex-start;
  }

  .catalog-title__icon {
    width: 36px;
    height: 36px;
  }

  .catalog-summary {
    grid-template-columns: 1fr;
  }

  .summary-item {
    padding: 12px 16px;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .summary-item:last-child {
    border-bottom: 0;
  }

  .dataset-table-wrap {
    overflow: visible;
  }

  .dataset-table,
  .dataset-table thead,
  .dataset-table tbody,
  .dataset-table tr,
  .dataset-table td {
    display: block;
    width: 100%;
    min-width: 0;
  }

  .dataset-table thead {
    display: none;
  }

  .dataset-table tr {
    padding: 14px 16px;
    border-top: 1px solid var(--color-border);
  }

  .dataset-table td {
    padding: 8px 0;
    border-top: 0;
  }

  .dataset-table td[data-label] {
    display: flex;
    justify-content: space-between;
    gap: 14px;
    color: var(--color-text);
    font-size: 0.86rem;
  }

  .dataset-table td[data-label]::before {
    content: attr(data-label);
    color: var(--color-text-muted);
    font-weight: 800;
  }

  .dataset-table__actions {
    width: auto;
    white-space: normal;
  }

  .row-actions {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .row-actions .action-button--danger {
    grid-column: 1 / -1;
  }
}
</style>
