<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type {
  DatasetAsset,
  DatasetLibraryItem,
  DatasetSourceTreeItem,
} from "@/features/data-analysis/types";

const props = defineProps<{
  connectedDatasets: DatasetAsset[];
  activeWorkspaceId: string | null;
  datasetsLibrary: DatasetLibraryItem[];
  isDatasetMutating: boolean;
}>();

const emit = defineEmits<{
  uploadDataset: [];
  attachDataset: [datasetId: string, workspaceId?: string];
  selectDataset: [datasetId: string];
  detachDataset: [datasetId: string];
  detachDatasets: [datasetIds: string[]];
}>();

const expandedDatasetId = ref<string | null>(null);
const isDatasetLinkDialogOpen = ref(false);
const selectedDatasetIds = ref<Set<string>>(new Set());
const hiddenDatasetIds = ref<Set<string>>(new Set());
const hiddenColumnKeys = ref<Set<string>>(new Set());

const connectedDatasetIds = computed(() => props.connectedDatasets.map((dataset) => dataset.id));
const selectedConnectedDatasetIds = computed(() =>
  connectedDatasetIds.value.filter((datasetId) => selectedDatasetIds.value.has(datasetId)),
);
const selectedDatasetCount = computed(() => selectedConnectedDatasetIds.value.length);
const isAllDatasetsSelected = computed(
  () => props.connectedDatasets.length > 0 && selectedDatasetCount.value === props.connectedDatasets.length,
);
const selectAllLabel = computed(
  () => `전체 선택 (${selectedDatasetCount.value}/${props.connectedDatasets.length})`,
);
const connectedDatasetIdSet = computed(
  () => new Set(props.connectedDatasets.map((dataset) => dataset.id)),
);
const connectableDatasets = computed(() =>
  props.datasetsLibrary.filter(
    (dataset) => !connectedDatasetIdSet.value.has(dataset.id),
  ),
);

watch(connectedDatasetIds, (datasetIds) => {
  const connectedIds = new Set(datasetIds);
  const nextSelectedIds = new Set(
    [...selectedDatasetIds.value].filter((datasetId) => connectedIds.has(datasetId)),
  );
  if (nextSelectedIds.size !== selectedDatasetIds.value.size) {
    selectedDatasetIds.value = nextSelectedIds;
  }
});

/** 기존 데이터셋 목록에서 현재 세션에 연결할 항목을 고르는 다이얼로그를 엽니다. */
function openDatasetLinkDialog() {
  if (!props.activeWorkspaceId) return;
  isDatasetLinkDialogOpen.value = true;
}

/** 데이터셋 연결 다이얼로그를 닫습니다. */
function closeDatasetLinkDialog() {
  if (props.isDatasetMutating) return;
  isDatasetLinkDialogOpen.value = false;
}

/** 선택한 데이터셋을 현재 세션과 연결하고 다이얼로그를 닫습니다. */
function attachDataset(datasetId: string) {
  emit("attachDataset", datasetId, props.activeWorkspaceId ?? undefined);
  isDatasetLinkDialogOpen.value = false;
}

/** 연결 데이터의 파일 트리를 열거나 닫습니다. */
function toggleDatasetOpen(datasetId: string) {
  expandedDatasetId.value =
    expandedDatasetId.value === datasetId ? null : datasetId;
  emit("selectDataset", datasetId);
}

/** 개별 연결 데이터셋의 선택 상태를 전환합니다. */
function toggleDatasetSelection(datasetId: string) {
  const next = new Set(selectedDatasetIds.value);
  if (next.has(datasetId)) {
    next.delete(datasetId);
  } else {
    next.add(datasetId);
  }
  selectedDatasetIds.value = next;
}

/** 전체 선택 버튼으로 연결 데이터셋 전체를 선택하거나 해제합니다. */
function toggleAllDatasetSelection() {
  if (isAllDatasetsSelected.value) {
    selectedDatasetIds.value = new Set();
    return;
  }
  selectedDatasetIds.value = new Set(connectedDatasetIds.value);
}

/** 선택한 연결 데이터셋을 현재 워크스페이스에서 해제합니다. */
function detachSelectedDatasets() {
  if (selectedConnectedDatasetIds.value.length === 0) return;
  emit("detachDatasets", selectedConnectedDatasetIds.value);
  selectedDatasetIds.value = new Set();
}

/** 연결 데이터셋 전체를 현재 워크스페이스에서 해제합니다. */
function detachAllDatasets() {
  if (connectedDatasetIds.value.length === 0) return;
  emit("detachDatasets", connectedDatasetIds.value);
  selectedDatasetIds.value = new Set();
}

/** 데이터 카드의 표시/숨김 상태를 로컬 UI 상태로 전환합니다. */
function toggleDatasetVisibility(datasetId: string) {
  const next = new Set(hiddenDatasetIds.value);
  if (next.has(datasetId)) {
    next.delete(datasetId);
  } else {
    next.add(datasetId);
  }
  hiddenDatasetIds.value = next;
}

/** 원천 데이터 행의 표시/숨김 상태를 로컬 UI 상태로 전환합니다. */
function toggleColumnVisibility(datasetId: string, sourceId: string) {
  const key = `${datasetId}:${sourceId}`;
  const next = new Set(hiddenColumnKeys.value);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  hiddenColumnKeys.value = next;
}

function isDatasetVisible(datasetId: string): boolean {
  return !hiddenDatasetIds.value.has(datasetId);
}

function isColumnVisible(datasetId: string, sourceId: string): boolean {
  return !hiddenColumnKeys.value.has(`${datasetId}:${sourceId}`);
}

function formatDatasetMeta(dataset: DatasetAsset): string {
  const rowCount =
    dataset.profile?.rowCount ?? dataset.preview?.rows.length ?? 0;
  const columnCount =
    dataset.profile?.columnCount ?? dataset.preview?.columns.length ?? 0;
  return `${rowCount.toLocaleString()}행 · ${columnCount.toLocaleString()}열`;
}

function formatLibraryDatasetMeta(dataset: DatasetLibraryItem): string {
  return `${dataset.rowCount.toLocaleString()}행 · ${dataset.columnCount.toLocaleString()}열`;
}

/** 데이터셋 원천 데이터 트리를 카드 확장 영역에 표시할 flat row로 변환합니다. */
function fileRows(dataset: DatasetAsset): DatasetSourceTreeItem[] {
  const flattenTree = (
    items: DatasetSourceTreeItem[],
  ): DatasetSourceTreeItem[] =>
    items.flatMap((item) => [item, ...flattenTree(item.children)]);
  return flattenTree(dataset.sourceTree ?? []);
}

/** 원천 데이터 행의 파일 수와 shape 정보를 보조 텍스트로 표시합니다. */
function formatSourceMeta(source: DatasetSourceTreeItem): string {
  if (source.itemType === "folder") {
    return `${source.fileCount.toLocaleString()}개 파일`;
  }
  return `${source.rowCount.toLocaleString()}행 · ${source.columnCount.toLocaleString()}열`;
}
</script>

<template>
  <section class="connected-data-pane">
    <div class="connected-data-pane__header">
      <h2>워크스페이스와 연결된 데이터</h2>
      <button
        type="button"
        class="pane-add-button"
        aria-label="데이터 추가"
        @click="openDatasetLinkDialog"
      >
        <span class="material-symbols-outlined">add</span>
      </button>
    </div>

    <div class="bulk-select-row">
      <button
        type="button"
        class="bulk-select-row__toggle"
        :disabled="isDatasetMutating || connectedDatasets.length === 0"
        @click="toggleAllDatasetSelection"
      >
        <span
          class="checkbox"
          :class="{ 'checkbox--checked': isAllDatasetsSelected }"
          aria-hidden="true"
        ></span>
        <span>{{ selectAllLabel }}</span>
      </button>
      <div class="bulk-select-row__actions">
        <button
          type="button"
          class="soft-button"
          :disabled="isDatasetMutating || selectedDatasetCount === 0"
          @click="detachSelectedDatasets"
        >
          선택 해제
        </button>
        <button
          type="button"
          class="primary-button"
          :disabled="isDatasetMutating || connectedDatasets.length === 0"
          @click="detachAllDatasets"
        >
          전체 해제
        </button>
      </div>
    </div>

    <div class="connected-data-pane__divider"></div>

    <div v-if="connectedDatasets.length" class="dataset-card-list">
      <article
        v-for="dataset in connectedDatasets"
        :key="dataset.id"
        class="dataset-card"
        :class="{
          'dataset-card--open': expandedDatasetId === dataset.id,
          'dataset-card--hidden': !isDatasetVisible(dataset.id),
        }"
      >
        <div class="dataset-card__body">
          <div class="dataset-card__top">
            <button
              type="button"
              class="select-label"
              :disabled="isDatasetMutating"
              @click="toggleDatasetSelection(dataset.id)"
            >
              <span
                class="checkbox"
                :class="{ 'checkbox--checked': selectedDatasetIds.has(dataset.id) }"
                aria-hidden="true"
              ></span>
              <span>선택</span>
            </button>

            <div class="dataset-card__actions">
              <button
                type="button"
                class="soft-button"
                :disabled="isDatasetMutating"
                @click="emit('selectDataset', dataset.id)"
              >
                변경
              </button>
              <button
                type="button"
                class="gray-button"
                :disabled="isDatasetMutating"
                @click="toggleDatasetOpen(dataset.id)"
              >
                {{ expandedDatasetId === dataset.id ? "닫기" : "열기" }}
              </button>
              <button
                type="button"
                class="primary-button"
                :disabled="isDatasetMutating"
                @click="emit('detachDataset', dataset.id)"
              >
                해제
              </button>
            </div>
          </div>

          <div class="dataset-card__divider"></div>

          <div class="dataset-card__name-row">
            <div class="dataset-card__title">
              <strong>{{ dataset.filename }}</strong>
              <span>{{ formatDatasetMeta(dataset) }}</span>
            </div>
            <button
              type="button"
              class="visibility-button"
              :aria-label="
                isDatasetVisible(dataset.id) ? '데이터 보이기' : '데이터 숨김'
              "
              @click="toggleDatasetVisibility(dataset.id)"
            >
              <span class="material-symbols-outlined">{{
                isDatasetVisible(dataset.id) ? "visibility" : "visibility_off"
              }}</span>
            </button>
          </div>
        </div>

        <div v-if="expandedDatasetId === dataset.id" class="file-tree">
          <div class="file-tree__rows">
            <div v-if="dataset.sourceTree == null" class="file-tree__empty">
              <span class="material-symbols-outlined">progress_activity</span>
              원천 데이터 목록을 불러오는 중입니다.
            </div>

            <div
              v-else
              v-for="row in fileRows(dataset)"
              :key="row.id"
              class="file-row"
              :class="{
                'file-row--folder': row.itemType === 'folder',
                'file-row--hidden': !isColumnVisible(dataset.id, row.id),
              }"
              :style="{ '--file-depth': row.depth + 1 }"
            >
              <span class="file-row__branch">ㄴ</span>
              <span class="material-symbols-outlined file-row__icon">
                {{ row.itemType === "folder" ? "folder" : "description" }}
              </span>
              <span class="file-row__name">
                <strong>{{ row.name }}</strong>
                <small
                  >{{ row.relativePath }} · {{ formatSourceMeta(row) }}</small
                >
              </span>
              <button
                type="button"
                class="visibility-button"
                @click="toggleColumnVisibility(dataset.id, row.id)"
              >
                <span class="material-symbols-outlined">{{
                  isColumnVisible(dataset.id, row.id)
                    ? "visibility"
                    : "visibility_off"
                }}</span>
              </button>
            </div>

            <div
              v-if="
                dataset.sourceTree != null && fileRows(dataset).length === 0
              "
              class="file-tree__empty"
            >
              <span class="material-symbols-outlined">folder_off</span>
              연결된 원천 데이터가 없습니다.
            </div>
          </div>
        </div>
      </article>
    </div>

    <section v-else class="empty-data-state">
      <span class="material-symbols-outlined">database</span>
      <strong>연결된 데이터가 없습니다</strong>
      <p>
        상단의 추가 버튼으로 등록된 데이터셋을 현재 워크스페이스에 연결합니다.
      </p>
    </section>

    <div
      v-if="isDatasetLinkDialogOpen"
      class="link-dialog-backdrop"
      role="presentation"
      @click.self="closeDatasetLinkDialog"
    >
      <section
        class="link-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dataset-link-dialog-title"
      >
        <header class="link-dialog__header">
          <div>
            <p>데이터셋 연결</p>
            <h3 id="dataset-link-dialog-title">세션에 연결할 데이터셋 선택</h3>
          </div>
          <button
            type="button"
            class="dialog-icon-button"
            :disabled="isDatasetMutating"
            aria-label="닫기"
            @click="closeDatasetLinkDialog"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>

        <div class="link-dialog__list">
          <article
            v-for="dataset in connectableDatasets"
            :key="dataset.id"
            class="link-dialog__item"
          >
            <div>
              <strong>{{ dataset.filename }}</strong>
              <span>{{ formatLibraryDatasetMeta(dataset) }}</span>
            </div>
            <button
              type="button"
              class="link-dialog__action"
              :disabled="isDatasetMutating"
              @click="attachDataset(dataset.id)"
            >
              <span class="material-symbols-outlined">link</span>
              연결
            </button>
          </article>

          <div
            v-if="connectableDatasets.length === 0"
            class="link-dialog__empty"
          >
            <span class="material-symbols-outlined">dataset_linked</span>
            연결 가능한 데이터셋이 없습니다.
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.connected-data-pane {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  overflow: hidden;
}

.connected-data-pane h2 {
  margin: 0;
  color: #000;
  font-size: 18px;
  font-weight: 800;
}

.connected-data-pane__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.pane-add-button {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--color-primary);
  border-radius: 6px;
  color: var(--color-primary);
  background: #fff;
  cursor: pointer;
  transition:
    background-color 150ms ease,
    color 150ms ease,
    box-shadow 150ms ease,
    transform 150ms ease;
}

.pane-add-button:hover,
.pane-add-button:focus-visible {
  color: #fff;
  background: var(--color-primary);
  box-shadow: 0 4px 12px rgba(43, 94, 162, 0.24);
  outline: none;
  transform: translateY(-1px);
}

.bulk-select-row,
.bulk-select-row__toggle,
.select-label,
.dataset-card__top,
.dataset-card__actions,
.dataset-card__name-row {
  display: flex;
  align-items: center;
}

.bulk-select-row {
  justify-content: space-between;
  gap: 8px;
  margin-top: 20px;
}

.bulk-select-row__toggle,
.select-label {
  border: 0;
  background: transparent;
  color: #000;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
}

.bulk-select-row__toggle {
  gap: 8px;
  padding: 0;
}

.bulk-select-row__actions {
  display: inline-flex;
  flex-shrink: 0;
  gap: 6px;
}

.bulk-select-row__toggle:disabled,
.select-label:disabled {
  cursor: default;
  opacity: 0.55;
}

.checkbox {
  position: relative;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border: 1px solid #000;
  background: #fff;
}

.checkbox--checked {
  border-color: var(--color-primary);
  background: var(--color-primary);
}

.checkbox--checked::after {
  position: absolute;
  left: 4px;
  top: 1px;
  width: 5px;
  height: 9px;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  content: "";
  transform: rotate(45deg);
}

.connected-data-pane__divider {
  width: 100%;
  height: 1px;
  margin-top: 12px;
  background: #d9d9d9;
}

.dataset-card-list {
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-self: stretch;
  gap: 16px;
  margin-top: 24px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
  scrollbar-gutter: stable;
}

.dataset-card {
  flex: 0 0 auto;
  overflow: hidden;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.dataset-card--open {
  background: #ededed;
}

.dataset-card--hidden .dataset-card__title {
  opacity: 0.2;
}

.dataset-card__body {
  padding: 16px;
  background: #fff;
}

.dataset-card__top {
  justify-content: space-between;
  gap: 12px;
}

.select-label {
  gap: 6px;
  padding: 0;
}

.dataset-card__actions {
  justify-content: flex-end;
  gap: 4px;
}

.soft-button,
.gray-button,
.primary-button {
  min-height: 25px;
  padding: 0 8px;
  border: 0;
  border-radius: 8px;
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  transition:
    background-color 150ms ease,
    box-shadow 150ms ease,
    transform 150ms ease;
}

.soft-button {
  color: var(--color-primary);
  background: rgba(43, 94, 162, 0.1);
}

.gray-button {
  color: var(--color-primary);
  background: #d9d9d9;
}

.primary-button {
  color: #fff;
  background: var(--color-primary);
}

.soft-button:hover:not(:disabled),
.gray-button:hover:not(:disabled),
.primary-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.soft-button:hover:not(:disabled) {
  background: rgba(43, 94, 162, 0.2);
}

.gray-button:hover:not(:disabled) {
  background: #c9d6ea;
}

.primary-button:hover:not(:disabled) {
  background: var(--color-primary-strong);
  box-shadow: 0 4px 10px rgba(43, 94, 162, 0.24);
}

.soft-button:disabled,
.gray-button:disabled,
.primary-button:disabled {
  opacity: 0.55;
  cursor: default;
}

.dataset-card__divider {
  height: 1px;
  margin: 12px 0;
  background: #d9d9d9;
}

.dataset-card__name-row {
  min-height: 38px;
  justify-content: space-between;
  gap: 11px;
}

.dataset-card__title {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.dataset-card__title strong {
  display: -webkit-box;
  overflow: hidden;
  color: #000;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.22;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.dataset-card__title span {
  color: #66758a;
  font-size: 12px;
}

.visibility-button {
  width: 35px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 0;
  border-radius: 6px;
  color: #000;
  background: #d9d9d9;
  cursor: pointer;
  transition:
    background-color 150ms ease,
    transform 150ms ease;
}

.visibility-button:hover,
.visibility-button:focus-visible {
  background: #c9c9c9;
  outline: none;
  transform: scale(1.03);
}

.visibility-button .material-symbols-outlined {
  font-size: 19px;
}

.file-tree {
  position: relative;
  min-height: 308px;
  padding: 18px;
  background: #ededed;
}

.file-tree__rows {
  max-height: 270px;
  overflow-y: auto;
  display: grid;
  gap: 13px;
  padding-right: 18px;
}

.file-row {
  min-width: 0;
  min-height: 38px;
  display: grid;
  grid-template-columns: 15px 24px minmax(0, 1fr) 35px;
  align-items: center;
  gap: 10px;
  padding-left: calc((var(--file-depth, 0) - 1) * 32px);
  color: #000;
  font-size: 16px;
}

.file-row--folder {
  font-weight: 800;
}

.file-row--hidden {
  color: #b8b8b8;
}

.file-row--hidden .file-row__name {
  opacity: 0.2;
}

.file-row__branch {
  width: 15px;
  color: #000;
}

.file-row__icon {
  color: #555;
  font-size: 24px;
}

.file-row__name {
  min-width: 0;
  display: grid;
  gap: 2px;
  overflow: hidden;
}

.file-row__name strong,
.file-row__name small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-row__name strong {
  font-size: 14px;
}

.file-row__name small {
  color: #66758a;
  font-size: 11px;
  font-weight: 500;
}

.file-tree__empty {
  min-height: 160px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #66758a;
  font-size: 14px;
  text-align: center;
}

.empty-data-state {
  display: grid;
  place-items: center;
  align-self: start;
  gap: 10px;
  min-height: 240px;
  margin-top: 24px;
  padding: 28px;
  border: 1px dashed rgba(43, 94, 162, 0.24);
  border-radius: 12px;
  color: #66758a;
  text-align: center;
  background: #f7f9fc;
}

.empty-data-state strong,
.empty-data-state p {
  margin: 0;
}

.empty-data-state strong {
  color: #000;
}

.empty-data-state .material-symbols-outlined {
  color: var(--color-primary);
  font-size: 32px;
}

.link-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.36);
}

.link-dialog {
  width: min(560px, 100%);
  max-height: min(680px, calc(100vh - 48px));
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 22px 50px rgba(15, 23, 42, 0.24);
}

.link-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--color-border);
}

.link-dialog__header p,
.link-dialog__header h3 {
  margin: 0;
}

.link-dialog__header p {
  color: var(--color-text-muted);
  font-size: 0.75rem;
  font-weight: 800;
}

.link-dialog__header h3 {
  margin-top: 4px;
  color: var(--color-text);
  font-size: 1rem;
}

.dialog-icon-button {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.link-dialog__list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 10px;
  overflow-y: auto;
  padding: 16px 20px 20px;
}

.link-dialog__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
}

.link-dialog__item div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.link-dialog__item strong,
.link-dialog__item span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-dialog__item span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.link-dialog__action {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid var(--color-primary);
  border-radius: 8px;
  color: #fff;
  background: var(--color-primary);
  font: inherit;
  font-size: 0.84rem;
  font-weight: 800;
  cursor: pointer;
}

.link-dialog__action .material-symbols-outlined {
  font-size: 1rem;
}

.link-dialog__empty {
  min-height: 180px;
  display: grid;
  place-items: center;
  gap: 10px;
  color: var(--color-text-muted);
  text-align: center;
}
</style>
