<script setup lang="ts">
import type { DatasetAsset, SessionItem } from '../types'

const props = defineProps<{
  session: SessionItem | null
  datasets: DatasetAsset[]
  activeDatasetId?: string | null
  isUpdatingActiveDataset?: boolean
}>()

const emit = defineEmits<{
  selectActiveDataset: [datasetId: string]
}>()
</script>

<template>
  <section class="overview-card">
    <div class="overview-copy">
      <p>현재 세션</p>
      <h2>{{ session?.title ?? '세션을 불러오는 중' }}</h2>
      <span>
        메시지 {{ session?.messageCount ?? 0 }} · 연결된 데이터셋 {{ datasets.length || session?.datasetCount || 0 }}
      </span>
    </div>

    <div class="overview-datasets">
      <div class="overview-datasets__headline">
        <p>연결된 데이터셋</p>
        <label v-if="datasets.length" class="dataset-selector">
          <span>활성 데이터셋</span>
          <select
            :value="activeDatasetId ?? datasets[0]?.id ?? ''"
            :disabled="isUpdatingActiveDataset"
            @change="emit('selectActiveDataset', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">
              {{ dataset.filename }}
            </option>
          </select>
        </label>
      </div>
      <div v-if="datasets.length" class="dataset-chip-list">
        <button
          v-for="dataset in datasets"
          :key="dataset.id"
          type="button"
          class="dataset-chip"
          :class="{ 'dataset-chip--active': dataset.id === activeDatasetId }"
          :disabled="isUpdatingActiveDataset"
          @click="emit('selectActiveDataset', dataset.id)"
        >
          <span class="material-symbols-outlined">database</span>
          <div>
            <strong>{{ dataset.filename }}</strong>
            <small>
              {{ dataset.id === activeDatasetId ? '활성 데이터셋' : '보조 데이터셋' }}
            </small>
          </div>
        </button>
      </div>
      <p v-else class="overview-empty">아직 연결된 데이터셋이 없어요. 업로드하거나 데이터 소스에서 연결해 보세요.</p>
    </div>
  </section>
</template>

<style scoped>
.overview-card {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 18px;
  padding: 20px 22px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.76);
  box-shadow: var(--color-shadow);
}

.overview-copy p,
.overview-datasets > p {
  margin: 0;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 800;
}

.overview-copy h2 {
  margin: 8px 0 6px;
  font: 800 1.2rem/1.2 var(--font-heading);
}

.overview-copy span,
.overview-empty,
.dataset-chip small {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.overview-datasets {
  display: grid;
  gap: 10px;
}

.overview-datasets__headline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dataset-selector {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 14px;
  background: var(--color-surface-muted);
}

.dataset-selector span {
  color: var(--color-text-soft);
  font-size: 0.74rem;
  font-weight: 700;
}

.dataset-selector select {
  border: 0;
  background: transparent;
  color: var(--color-text);
  font-weight: 700;
}

.dataset-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.dataset-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 12px 14px;
  border-radius: 18px;
  background: var(--color-surface-muted);
  border: 1px solid transparent;
  text-align: left;
  cursor: pointer;
}

.dataset-chip--active {
  border-color: rgba(24, 74, 140, 0.18);
  background: var(--color-primary-soft);
}

.dataset-chip strong {
  display: block;
  font-size: 0.88rem;
}

.dataset-chip .material-symbols-outlined {
  color: var(--color-primary-strong);
}

.overview-empty {
  margin: 0;
}

@media (max-width: 960px) {
  .overview-card {
    grid-template-columns: minmax(0, 1fr);
  }

  .overview-datasets__headline {
    align-items: flex-start;
    display: grid;
  }
}
</style>
