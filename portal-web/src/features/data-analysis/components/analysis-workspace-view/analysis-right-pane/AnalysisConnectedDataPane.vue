<script setup lang="ts">
import { computed, ref } from "vue";

import type {
  DatasetAsset,
  DatasetLibraryItem,
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
}>();

const expandedDatasetId = ref<string | null>(null);
const isDatasetLinkDialogOpen = ref(false);
const hiddenDatasetIds = ref<Set<string>>(new Set());
const hiddenColumnKeys = ref<Set<string>>(new Set());

const selectedDeleteLabel = computed(
  () => `선택한 데이터 모두 삭제 (0/${props.connectedDatasets.length})`,
);
const connectedDatasetIdSet = computed(
  () => new Set(props.connectedDatasets.map((dataset) => dataset.id)),
);
const connectableDatasets = computed(() =>
  props.datasetsLibrary.filter(
    (dataset) => !connectedDatasetIdSet.value.has(dataset.id),
  ),
);

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

/** 컬럼 행의 표시/숨김 상태를 로컬 UI 상태로 전환합니다. */
function toggleColumnVisibility(datasetId: string, columnName: string) {
  const key = `${datasetId}:${columnName}`;
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

function isColumnVisible(datasetId: string, columnName: string): boolean {
  return !hiddenColumnKeys.value.has(`${datasetId}:${columnName}`);
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

function fileRows(
  dataset: DatasetAsset,
): Array<{ name: string; depth: number }> {
  const columns =
    dataset.profile?.columns.map((column) => column.name) ??
    dataset.preview?.columns ??
    [];
  return columns.slice(0, 6).map((name, index) => ({
    name,
    depth: index === 0 ? 1 : 2,
  }));
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

    <label class="bulk-delete-row">
      <span class="checkbox" aria-hidden="true"></span>
      <span>{{ selectedDeleteLabel }}</span>
    </label>

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
            <label class="select-label">
              <span class="checkbox" aria-hidden="true"></span>
              <span>선택</span>
            </label>

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
                v-if="expandedDatasetId !== dataset.id"
                type="button"
                class="gray-button"
                :disabled="isDatasetMutating"
                @click="toggleDatasetOpen(dataset.id)"
              >
                열기
              </button>
              <button
                type="button"
                class="primary-button"
                :disabled="isDatasetMutating"
                @click="emit('detachDataset', dataset.id)"
              >
                삭제
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
            <div class="file-row file-row--root">
              <span class="material-symbols-outlined file-row__icon"
                >description</span
              >
              <span class="file-row__name">{{ dataset.filename }}</span>
              <button
                type="button"
                class="visibility-button"
                @click="toggleDatasetVisibility(dataset.id)"
              >
                <span class="material-symbols-outlined">{{
                  isDatasetVisible(dataset.id) ? "visibility" : "visibility_off"
                }}</span>
              </button>
            </div>

            <div
              v-for="row in fileRows(dataset)"
              :key="`${dataset.id}-${row.name}`"
              class="file-row"
              :class="{
                'file-row--hidden': !isColumnVisible(dataset.id, row.name),
              }"
              :style="{ '--file-depth': row.depth }"
            >
              <span class="file-row__branch">ㄴ</span>
              <span class="material-symbols-outlined file-row__icon"
                >description</span
              >
              <span class="file-row__name">{{ row.name }}</span>
              <button
                type="button"
                class="visibility-button"
                @click="toggleColumnVisibility(dataset.id, row.name)"
              >
                <span class="material-symbols-outlined">{{
                  isColumnVisible(dataset.id, row.name)
                    ? "visibility"
                    : "visibility_off"
                }}</span>
              </button>
            </div>
          </div>

          <button
            type="button"
            class="tree-close-button"
            @click="expandedDatasetId = null"
          >
            닫기
          </button>
          <div class="file-tree__fade"></div>
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

.bulk-delete-row,
.select-label,
.dataset-card__top,
.dataset-card__actions,
.dataset-card__name-row {
  display: flex;
  align-items: center;
}

.bulk-delete-row {
  gap: 8px;
  margin-top: 20px;
  color: #000;
  font-size: 14px;
}

.checkbox {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border: 1px solid #000;
  background: #fff;
}

.connected-data-pane__divider {
  width: 100%;
  height: 1px;
  margin-top: 12px;
  background: #d9d9d9;
}

.dataset-card-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 16px;
  margin-top: 24px;
  overflow-y: auto;
  padding-right: 4px;
}

.dataset-card {
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
  color: #000;
  font-size: 14px;
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
  display: grid;
  gap: 13px;
  padding-right: 18px;
}

.file-row {
  min-width: 0;
  height: 24px;
  display: grid;
  grid-template-columns: 15px 24px minmax(0, 1fr) 35px;
  align-items: center;
  gap: 10px;
  padding-left: calc((var(--file-depth, 0) - 1) * 32px);
  color: #000;
  font-size: 16px;
}

.file-row--root {
  grid-template-columns: 24px minmax(0, 1fr) 35px;
  padding-left: 0;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-close-button {
  position: absolute;
  right: 20px;
  bottom: 20px;
  min-height: 28px;
  padding: 4px 16px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  background: var(--color-primary);
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.file-tree__fade {
  pointer-events: none;
  position: absolute;
  left: 7px;
  right: 0;
  bottom: 54px;
  height: 87px;
  background: linear-gradient(to bottom, rgba(237, 237, 237, 0), #ededed);
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
