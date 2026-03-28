<script setup lang="ts">
import { computed } from 'vue'

import type { DatasetLibraryItem } from '../types'

const props = defineProps<{
  datasets: DatasetLibraryItem[]
  selectedDatasetId?: string | null
  activeSessionId?: string | null
  searchQuery: string
  isBusy?: boolean
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  searchChange: [value: string]
  selectDataset: [datasetId: string]
  attachDataset: [datasetId: string]
  detachDataset: [datasetId: string]
  deleteDataset: [datasetId: string]
}>()

const filteredDatasets = computed(() => {
  const keyword = props.searchQuery.trim().toLowerCase()
  if (!keyword) {
    return props.datasets
  }

  return props.datasets.filter((dataset) => {
    const haystacks = [dataset.filename, dataset.contentType ?? '', dataset.storagePath]
    return haystacks.some((value) => value.toLowerCase().includes(keyword))
  })
})

const selectedDataset = computed(
  () => props.datasets.find((dataset) => dataset.id === props.selectedDatasetId) ?? filteredDatasets.value[0] ?? null,
)

function isLinkedToActiveSession(dataset: DatasetLibraryItem): boolean {
  return Boolean(props.activeSessionId && dataset.linkedSessionIds.includes(props.activeSessionId))
}

function formatDate(value?: string | null): string {
  if (!value) {
    return '없음'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
</script>

<template>
  <section class="library-shell">
    <header class="panel-card library-header">
      <div>
        <p>데이터 소스</p>
        <h2>데이터 소스 라이브러리</h2>
        <span>활성 세션을 기준으로 데이터셋 연결 상태를 보고 바로 attach / detach 할 수 있어요.</span>
      </div>
      <div class="header-badge">
        <span class="material-symbols-outlined">hub</span>
        {{ activeSessionId ? '활성 세션 연결 가능' : '활성 세션 없음' }}
      </div>
    </header>

    <section class="panel-card library-toolbar">
      <label class="library-search">
        <span class="material-symbols-outlined">search</span>
        <input
          :value="searchQuery"
          type="search"
          placeholder="파일명, 타입, 경로 검색"
          @input="emit('searchChange', ($event.target as HTMLInputElement).value)"
        >
      </label>
      <p>{{ filteredDatasets.length }}개 데이터셋</p>
    </section>

    <p v-if="errorMessage" class="library-error">{{ errorMessage }}</p>

    <div class="library-grid">
      <section class="dataset-list">
        <article
          v-for="dataset in filteredDatasets"
          :key="dataset.id"
          class="panel-card dataset-row"
          :class="{
            'dataset-row--selected': dataset.id === selectedDataset?.id,
            'dataset-row--linked': isLinkedToActiveSession(dataset),
          }"
          @click="emit('selectDataset', dataset.id)"
        >
          <div class="dataset-row__title">
            <div>
              <h3>{{ dataset.filename }}</h3>
              <p>{{ dataset.contentType ?? 'type 미지정' }}</p>
            </div>
            <span>{{ isLinkedToActiveSession(dataset) ? '연결됨' : '미연결' }}</span>
          </div>

          <div class="dataset-row__meta">
            <small>{{ dataset.rowCount }}행 · {{ dataset.columnCount }}열</small>
            <small>세션 {{ dataset.linkedSessionCount }}개 연결</small>
            <small>최근 사용 {{ formatDate(dataset.latestUsedAt) }}</small>
          </div>
        </article>

        <section v-if="filteredDatasets.length === 0" class="panel-card empty-card">
          <span class="material-symbols-outlined">database_off</span>
          <strong>검색 조건에 맞는 데이터셋이 없어요</strong>
        </section>
      </section>

      <section v-if="selectedDataset" class="panel-card detail-panel">
        <header class="detail-panel__header">
          <div>
            <p>상세 정보</p>
            <h3>{{ selectedDataset.filename }}</h3>
            <small>{{ selectedDataset.storagePath }}</small>
          </div>
          <div class="detail-panel__actions">
            <button
              v-if="!isLinkedToActiveSession(selectedDataset)"
              type="button"
              :disabled="isBusy || !activeSessionId"
              @click.stop="emit('attachDataset', selectedDataset.id)"
            >
              현재 세션에 연결
            </button>
            <button
              v-else
              type="button"
              :disabled="isBusy || !activeSessionId"
              @click.stop="emit('detachDataset', selectedDataset.id)"
            >
              현재 세션에서 해제
            </button>
            <button type="button" class="danger-button" :disabled="isBusy" @click.stop="emit('deleteDataset', selectedDataset.id)">
              삭제
            </button>
          </div>
        </header>

        <div class="detail-stats">
          <article><p>생성</p><strong>{{ formatDate(selectedDataset.createdAt) }}</strong></article>
          <article><p>최근 사용</p><strong>{{ formatDate(selectedDataset.latestUsedAt) }}</strong></article>
          <article><p>연결 세션</p><strong>{{ selectedDataset.linkedSessionCount }}개</strong></article>
        </div>

        <section v-if="selectedDataset.profile" class="detail-section">
          <p>프로파일</p>
          <div class="column-list">
            <article v-for="column in selectedDataset.profile.columns.slice(0, 6)" :key="column.name" class="column-card">
              <strong>{{ column.name }}</strong>
              <span>{{ column.dtype }} · 결측 {{ Math.round(column.nullRatio * 100) }}%</span>
              <small v-if="column.sampleValues.length">{{ column.sampleValues.join(', ') }}</small>
            </article>
          </div>
        </section>

        <section v-if="selectedDataset.preview?.rows.length" class="detail-section">
          <p>Preview</p>
          <div class="preview-table">
            <table>
              <thead>
                <tr>
                  <th v-for="column in selectedDataset.preview.columns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in selectedDataset.preview.rows.slice(0, 4)" :key="rowIndex">
                  <td v-for="column in selectedDataset.preview?.columns ?? []" :key="column">{{ row[column] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="selectedDataset.profile?.suggestedPrompts.length" class="detail-section">
          <p>추천 프롬프트</p>
          <div class="prompt-list">
            <span v-for="prompt in selectedDataset.profile.suggestedPrompts.slice(0, 4)" :key="prompt">{{ prompt }}</span>
          </div>
        </section>
      </section>
    </div>
  </section>
</template>

<style scoped>
.library-shell {
  min-height: 0;
  display: grid;
  gap: 16px;
}

.panel-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: var(--color-shadow);
}

.library-header,
.library-toolbar,
.dataset-row,
.detail-panel,
.empty-card {
  padding: 20px 22px;
}

.library-header,
.library-toolbar,
.detail-panel__header,
.dataset-row__title,
.dataset-row__meta,
.detail-panel__actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.library-header p,
.detail-section > p,
.detail-stats p,
.dataset-row p {
  margin: 0;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 800;
}

.library-header h2,
.dataset-row h3,
.detail-panel h3 {
  margin: 8px 0 6px;
  font-family: var(--font-heading);
}

.library-header span,
.library-toolbar p,
.dataset-row small,
.detail-panel small,
.column-card span,
.column-card small {
  color: var(--color-text-muted);
}

.header-badge,
.dataset-row__title > span,
.prompt-list span {
  padding: 8px 10px;
  border-radius: 999px;
  background: var(--color-surface-muted);
  color: var(--color-primary-strong);
  font-size: 0.78rem;
  font-weight: 700;
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

.library-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 420px);
  gap: 16px;
}

.dataset-list {
  min-height: 0;
  display: grid;
  gap: 12px;
  align-content: start;
}

.dataset-row {
  cursor: pointer;
}

.dataset-row--selected {
  border-color: rgba(24, 74, 140, 0.18);
}

.dataset-row--linked {
  background: linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(226, 238, 252, 0.86) 100%);
}

.dataset-row__meta {
  flex-wrap: wrap;
  align-items: center;
}

.detail-panel {
  display: grid;
  gap: 16px;
  align-content: start;
}

.detail-panel__header {
  align-items: flex-start;
}

.detail-panel__actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.detail-panel__actions button {
  padding: 11px 14px;
  border-radius: 14px;
  background: var(--color-surface-muted);
  cursor: pointer;
}

.danger-button {
  color: #9b3b3b;
}

.detail-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.detail-stats article,
.column-card {
  padding: 14px;
  border-radius: 18px;
  background: var(--color-surface-muted);
}

.detail-stats strong,
.column-card strong {
  display: block;
  margin-top: 8px;
}

.detail-section {
  display: grid;
  gap: 10px;
}

.column-list {
  display: grid;
  gap: 10px;
}

.preview-table {
  overflow-x: auto;
}

.preview-table table {
  width: 100%;
  min-width: 420px;
  border-collapse: collapse;
}

.preview-table th,
.preview-table td {
  padding: 12px 10px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  font-size: 0.78rem;
}

.prompt-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.library-error {
  margin: 0;
  color: #9b3b3b;
  font-size: 0.86rem;
}

.empty-card {
  display: grid;
  justify-items: center;
  gap: 8px;
  text-align: center;
}

@media (max-width: 1100px) {
  .library-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .library-header,
  .library-toolbar,
  .detail-panel__header {
    display: grid;
  }

  .detail-stats {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
