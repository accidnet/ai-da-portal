<script setup lang="ts">
import { ref } from "vue";

import DatasetCatalogPanel from "./DatasetCatalogPanel.vue";
import SourceDataPanel from "./SourceDataPanel.vue";
import type {
  DataSourceItem,
  DataSourceUploadProgress,
  DatasetLibraryItem,
  UploadPickerMode,
} from "@/features/data-source/types";

const props = defineProps<{
  datasets: DatasetLibraryItem[];
  dataSourceItems: DataSourceItem[];
  dataSourceUploadProgress: DataSourceUploadProgress;
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
  uploadFile: [mode: UploadPickerMode];
}>();

type LibraryView = "source" | "catalog";

const activeView = ref<LibraryView>("source");

/** 라이브러리 상단 토글의 활성 화면을 변경합니다. */
function setActiveView(view: LibraryView) {
  activeView.value = view;
}
</script>

<template>
  <section class="library-shell">
    <header class="panel-card library-header">
      <div class="library-title">
        <p>데이터 소스</p>
        <h2>데이터 소스 라이브러리</h2>
        <span>원천 데이터 수집부터 데이터셋 구성까지 한 곳에서 관리합니다.</span>
      </div>

      <div
        class="library-view-toggle"
        role="tablist"
        aria-label="데이터 소스 보기 전환"
      >
        <button
          type="button"
          role="tab"
          :aria-selected="activeView === 'source'"
          :class="{
            'library-view-toggle__button--active': activeView === 'source',
          }"
          class="library-view-toggle__button"
          @click="setActiveView('source')"
        >
          <span class="material-symbols-outlined">database_upload</span>
          원천데이터
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="activeView === 'catalog'"
          :class="{
            'library-view-toggle__button--active': activeView === 'catalog',
          }"
          class="library-view-toggle__button"
          @click="setActiveView('catalog')"
        >
          <span class="material-symbols-outlined">dataset</span>
          데이터셋 카탈로그
        </button>
      </div>
    </header>

    <SourceDataPanel
      v-if="activeView === 'source'"
      :items="props.dataSourceItems"
      :upload-progress="props.dataSourceUploadProgress"
      @upload-file="(mode) => emit('uploadFile', mode)"
    />
    <DatasetCatalogPanel
      v-else
      :datasets="props.datasets"
      :selected-dataset-id="selectedDatasetId"
      :active-session-id="activeSessionId"
      :search-query="searchQuery"
      :is-busy="isBusy"
      :error-message="errorMessage"
      @search-change="(value) => emit('searchChange', value)"
      @select-dataset="(datasetId) => emit('selectDataset', datasetId)"
      @attach-dataset="(datasetId) => emit('attachDataset', datasetId)"
      @detach-dataset="(datasetId) => emit('detachDataset', datasetId)"
      @delete-dataset="(datasetId) => emit('deleteDataset', datasetId)"
    />
  </section>
</template>

<style scoped>
.library-shell {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 18px;
}

.panel-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--color-shadow);
}

.library-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 10px 14px;
}

.library-title {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.library-header p {
  margin: 0;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 800;
}

.library-header h2 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 1.12rem;
  line-height: 1.25;
}

.library-header span {
  color: var(--color-text-muted);
}

.library-header .library-title > span {
  font-size: 0.82rem;
  line-height: 1.35;
}

.library-view-toggle {
  flex: 0 0 auto;
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: var(--color-surface-muted);
}

.library-view-toggle__button {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  font: inherit;
  font-size: 0.86rem;
  font-weight: 800;
  white-space: nowrap;
}

.library-view-toggle__button .material-symbols-outlined {
  font-size: 1.15rem;
}

.library-view-toggle__button--active {
  background: #fff;
  color: var(--color-primary);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

@media (max-width: 900px) {
  .library-header {
    display: grid;
  }

  .library-view-toggle {
    width: 100%;
  }

  .library-view-toggle__button {
    flex: 1;
  }
}

@media (max-width: 640px) {
  .library-header {
    padding: 16px;
  }

  .library-view-toggle {
    display: grid;
    grid-template-columns: 1fr;
  }
}
</style>
