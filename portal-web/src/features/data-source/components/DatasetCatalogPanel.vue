<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  fetchWorkspaces,
  type CreateDatasetFromSourcesPayload,
} from "@/features/data-analysis/api/analysisApi";
import type {
  DataSourceItem,
  DatasetLibraryItem,
  DatasetSourceTreeItem,
} from "@/features/data-source/types";

const props = defineProps<{
  datasets: DatasetLibraryItem[];
  dataSourceItems: DataSourceItem[];
  selectedDatasetId?: string | null;
  activeSessionId?: string | null;
  activeWorkspaceId?: string | null;
  searchQuery: string;
  isBusy?: boolean;
  errorMessage?: string | null;
}>();

const emit = defineEmits<{
  searchChange: [value: string];
  selectDataset: [datasetId: string | null];
  attachDataset: [datasetId: string, workspaceId?: string];
  detachDataset: [datasetId: string];
  deleteDataset: [datasetId: string];
  createDatasetFromSources: [payload: CreateDatasetFromSourcesPayload];
}>();

const sortOrder = ref<"desc" | "asc">("desc");
const isCreateDialogOpen = ref(false);
const datasetNameInput = ref("");
const datasetDescriptionInput = ref("");
const sourceSearchQuery = ref("");
const selectedSourceIds = ref<Set<string>>(new Set());
const collapsedSourceFolderIds = ref<Set<string>>(new Set());
const createDatasetError = ref<string | null>(null);
const isCreateSubmitting = ref(false);
const createDatasetProgressPercent = ref(0);
const sessionLinkDatasetId = ref<string | null>(null);
const workspaceItems = ref<Array<{ id: string; name: string; updatedAt: string }>>([]);
const isWorkspaceListLoading = ref(false);
const workspaceListError = ref<string | null>(null);
let createDatasetProgressTimer: ReturnType<typeof window.setInterval> | null = null;
let createDatasetProgressStartedAt = 0;

/** 데이터셋 생성 요청 중 모달 입력과 닫기 동작을 잠급니다. */
const isCreatePending = computed(() => isCreateSubmitting.value || props.isBusy);

/** 활성 세션에 연결된 데이터셋 수를 요약 카드에 표시합니다. */
const linkedDatasetCount = computed(() => {
  return props.datasets.filter((dataset) => isLinkedToActiveSession(dataset)).length;
});

/** 현재 선택된 데이터셋 상세 정보를 테이블 확장 영역에 표시합니다. */
const selectedDataset = computed(() => {
  return props.datasets.find((dataset) => dataset.id === props.selectedDatasetId) ?? null;
});

/** 카탈로그 전체 데이터 규모를 행 기준으로 합산합니다. */
const totalRowCount = computed(() => {
  return props.datasets.reduce((total, dataset) => total + dataset.rowCount, 0);
});

/** 데이터셋 생성 모달에서 표시할 원천 데이터 트리 목록입니다. */
const visibleSourceItems = computed(() => {
  const keyword = sourceSearchQuery.value.trim().toLowerCase();
  const flattened = flattenVisibleSourceItems(props.dataSourceItems);
  if (!keyword) return flattened;

  return flattened.filter((item) => {
    const haystacks = [item.name, item.relativePath];
    return haystacks.some((value) => value.toLowerCase().includes(keyword));
  });
});

/** 선택된 원천 데이터가 실제로 포함하는 파일 수와 용량을 계산합니다. */
const selectedSourceStats = computed(() => {
  const stats = { fileCount: 0, totalBytes: 0 };
  const fileIds = new Set<string>();
  for (const item of props.dataSourceItems) {
    collectSelectedFileStats(item, fileIds, stats);
  }
  return stats;
});

const selectedSourceFileCount = computed(() => selectedSourceStats.value.fileCount);
const selectedSourceSizeLabel = computed(() => formatBytes(selectedSourceStats.value.totalBytes));
const createDatasetProgressLabel = computed(() => `${Math.round(createDatasetProgressPercent.value)}%`);
const createDatasetProgressMessage = computed(() => {
  if (createDatasetProgressPercent.value >= 95) {
    return "데이터셋 목록과 상세 정보를 갱신하는 중입니다.";
  }
  if (createDatasetProgressPercent.value >= 68) {
    return "선택한 파일의 미리보기와 프로파일을 저장하는 중입니다.";
  }
  if (createDatasetProgressPercent.value >= 32) {
    return "선택한 원천 파일을 확인하고 프로파일을 계산하는 중입니다.";
  }
  return "데이터셋 생성 요청을 준비하고 있습니다.";
});

/** 선택된 데이터셋에 연결된 원천 데이터를 렌더링 가능한 flat tree row로 변환합니다. */
const selectedDatasetSourceRows = computed(() => {
  return flattenDatasetSourceTree(selectedDataset.value?.sourceTree ?? []);
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

/** 데이터셋 연결 다이얼로그에 보여줄 워크스페이스 목록입니다. */
const linkableWorkspaces = computed(() => {
  return [...workspaceItems.value].sort((left, right) => {
    if (left.id === props.activeWorkspaceId) return -1;
    if (right.id === props.activeWorkspaceId) return 1;
    return left.name.localeCompare(right.name);
  });
});

const sessionLinkDataset = computed(() => {
  return props.datasets.find((dataset) => dataset.id === sessionLinkDatasetId.value) ?? null;
});

/** 현재 활성 세션과 데이터셋 연결 여부를 확인합니다. */
function isLinkedToActiveSession(dataset: DatasetLibraryItem): boolean {
  return Boolean(
    props.activeSessionId &&
      dataset.linkedSessionIds.includes(props.activeSessionId),
  );
}

/** 모달의 원천 데이터 트리를 접힘 상태에 맞게 펼칩니다. */
function flattenVisibleSourceItems(items: DataSourceItem[]): DataSourceItem[] {
  const sortedItems = [...items].sort((left, right) => {
    if (left.itemType !== right.itemType) {
      return left.itemType === "folder" ? -1 : 1;
    }
    return left.name.localeCompare(right.name);
  });

  return sortedItems.flatMap((item) => {
    if (item.itemType !== "folder" || collapsedSourceFolderIds.value.has(item.id)) {
      return [item];
    }
    return [item, ...flattenVisibleSourceItems(item.children)];
  });
}

/** 특정 폴더 아래의 모든 하위 노드를 수집합니다. */
function collectDescendantItems(item: DataSourceItem): DataSourceItem[] {
  return item.children.flatMap((child) => [child, ...collectDescendantItems(child)]);
}

/** 선택 상태에서 실제 파일 노드만 중복 없이 집계합니다. */
function collectSelectedFileStats(
  item: DataSourceItem,
  fileIds: Set<string>,
  stats: { fileCount: number; totalBytes: number },
) {
  if (item.itemType === "file" && selectedSourceIds.value.has(item.id)) {
    if (!fileIds.has(item.id)) {
      fileIds.add(item.id);
      stats.fileCount += 1;
      stats.totalBytes += item.sizeBytes ?? 0;
    }
    return;
  }

  if (item.itemType === "folder" && selectedSourceIds.value.has(item.id)) {
    for (const descendant of collectDescendantItems(item)) {
      if (descendant.itemType === "file" && !fileIds.has(descendant.id)) {
        fileIds.add(descendant.id);
        stats.fileCount += 1;
        stats.totalBytes += descendant.sizeBytes ?? 0;
      }
    }
    return;
  }

  for (const child of item.children) {
    collectSelectedFileStats(child, fileIds, stats);
  }
}

/** 데이터셋 원천 트리를 화면 row 목록으로 펼칩니다. */
function flattenDatasetSourceTree(
  items: DatasetSourceTreeItem[],
): DatasetSourceTreeItem[] {
  return items.flatMap((item) => [item, ...flattenDatasetSourceTree(item.children)]);
}

/** 이미 선택된 데이터셋 row를 다시 누르면 선택을 해제합니다. */
function toggleDatasetRow(datasetId: string) {
  emit("selectDataset", datasetId === props.selectedDatasetId ? null : datasetId);
}

/** 데이터셋 row의 연결 버튼에서 세션 선택 다이얼로그를 엽니다. */
async function openSessionLinkDialog(datasetId: string) {
  sessionLinkDatasetId.value = datasetId;
  await loadWorkspacesForLinkDialog();
}

/** 세션 선택 다이얼로그를 닫습니다. */
function closeSessionLinkDialog() {
  if (props.isBusy) return;
  sessionLinkDatasetId.value = null;
}

/** 선택한 워크스페이스와 데이터셋 연결을 요청합니다. */
function attachDatasetToWorkspace(workspaceId: string) {
  if (!sessionLinkDatasetId.value) return;
  emit("attachDataset", sessionLinkDatasetId.value, workspaceId);
  sessionLinkDatasetId.value = null;
}

/** DB에 등록된 워크스페이스 목록을 연결 다이얼로그용으로 조회합니다. */
async function loadWorkspacesForLinkDialog() {
  try {
    isWorkspaceListLoading.value = true;
    workspaceListError.value = null;
    const workspaces = await fetchWorkspaces();
    workspaceItems.value = workspaces.map((workspace) => ({
      id: workspace.id,
      name: workspace.name,
      updatedAt: workspace.updated_at,
    }));
  } catch {
    workspaceListError.value = "워크스페이스 목록을 불러오지 못했어요.";
  } finally {
    isWorkspaceListLoading.value = false;
  }
}

/** 폴더 선택 시 하위 전체 선택/해제를 함께 적용합니다. */
function toggleSourceSelection(item: DataSourceItem) {
  const relatedItems =
    item.itemType === "folder" ? [item, ...collectDescendantItems(item)] : [item];
  const relatedIds = relatedItems.map((sourceItem) => sourceItem.id);
  const nextIds = new Set(selectedSourceIds.value);
  const isEveryRelatedSelected = relatedIds.every((id) => nextIds.has(id));

  for (const id of relatedIds) {
    if (isEveryRelatedSelected) {
      nextIds.delete(id);
    } else {
      nextIds.add(id);
    }
  }

  selectedSourceIds.value = nextIds;
}

/** 폴더 행의 펼침 상태를 전환합니다. */
function toggleSourceFolder(item: DataSourceItem) {
  if (item.itemType !== "folder") return;

  const nextIds = new Set(collapsedSourceFolderIds.value);
  if (nextIds.has(item.id)) {
    nextIds.delete(item.id);
  } else {
    nextIds.add(item.id);
  }
  collapsedSourceFolderIds.value = nextIds;
}

/** 데이터셋 생성 모달을 초기 상태로 엽니다. */
function openCreateDatasetDialog() {
  datasetNameInput.value = "";
  datasetDescriptionInput.value = "";
  sourceSearchQuery.value = "";
  selectedSourceIds.value = new Set();
  collapsedSourceFolderIds.value = new Set();
  createDatasetError.value = null;
  isCreateDialogOpen.value = true;
}

/** 데이터셋 생성 모달을 닫습니다. */
function closeCreateDatasetDialog() {
  if (isCreatePending.value) return;

  isCreateDialogOpen.value = false;
  createDatasetError.value = null;
  isCreateSubmitting.value = false;
  resetCreateDatasetProgress();
}

/** 선택한 원천 데이터와 메타데이터로 데이터셋 생성을 요청합니다. */
function submitCreateDataset() {
  const name = datasetNameInput.value.trim();
  if (!name) {
    createDatasetError.value = "데이터셋 명을 입력해 주세요.";
    return;
  }
  if (selectedSourceFileCount.value === 0) {
    createDatasetError.value = "데이터셋에 포함할 파일 또는 폴더를 선택해 주세요.";
    return;
  }

  isCreateSubmitting.value = true;
  startCreateDatasetProgress();
  createDatasetError.value = null;
  emit("createDatasetFromSources", {
    name,
    description: datasetDescriptionInput.value.trim() || null,
    dataSourceItemIds: Array.from(selectedSourceIds.value),
  });
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

/** 바이트 값을 진행률 보조 정보에 맞는 용량 문자열로 변환합니다. */
function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

/** 데이터셋 카탈로그의 등록일 정렬 방향을 전환합니다. */
function toggleSortOrder() {
  sortOrder.value = sortOrder.value === "desc" ? "asc" : "desc";
}

/** 선택한 파일 규모에 따라 완료 전까지 보여줄 추정 진행률을 시작합니다. */
function startCreateDatasetProgress() {
  stopCreateDatasetProgress();
  createDatasetProgressStartedAt = Date.now();
  createDatasetProgressPercent.value = 6;

  const estimatedDurationMs = Math.min(
    90000,
    Math.max(
      10000,
      selectedSourceStats.value.fileCount * 1300 +
        selectedSourceStats.value.totalBytes / (18 * 1024 * 1024),
    ),
  );

  createDatasetProgressTimer = window.setInterval(() => {
    const elapsedRatio = Math.min(
      1,
      (Date.now() - createDatasetProgressStartedAt) / estimatedDurationMs,
    );
    const easedRatio = 1 - Math.pow(1 - elapsedRatio, 2.2);
    createDatasetProgressPercent.value = Math.min(
      92,
      Math.max(createDatasetProgressPercent.value, 6 + easedRatio * 86),
    );
  }, 300);
}

/** 생성 완료 시 진행률을 100%로 표시한 뒤 다이얼로그를 닫습니다. */
function finishCreateDatasetProgress() {
  stopCreateDatasetProgress();
  createDatasetProgressPercent.value = 100;
  window.setTimeout(() => {
    isCreateDialogOpen.value = false;
    createDatasetError.value = null;
    resetCreateDatasetProgress();
  }, 360);
}

/** 진행률 타이머를 중지합니다. */
function stopCreateDatasetProgress() {
  if (!createDatasetProgressTimer) return;
  window.clearInterval(createDatasetProgressTimer);
  createDatasetProgressTimer = null;
}

/** 생성 진행률 상태를 초기화합니다. */
function resetCreateDatasetProgress() {
  stopCreateDatasetProgress();
  createDatasetProgressPercent.value = 0;
  createDatasetProgressStartedAt = 0;
}

watch(
  () => props.isBusy,
  (isBusy, wasBusy) => {
    if (!isCreateSubmitting.value || isBusy || !wasBusy) return;

    isCreateSubmitting.value = false;
    if (!props.errorMessage) {
      finishCreateDatasetProgress();
    }
  },
);

watch(
  () => props.errorMessage,
  (message) => {
    if (!isCreateSubmitting.value || !message) return;

    isCreateSubmitting.value = false;
    resetCreateDatasetProgress();
    createDatasetError.value = message;
  },
);

onMounted(() => {
  void loadWorkspacesForLinkDialog();
});

onBeforeUnmount(() => {
  stopCreateDatasetProgress();
});
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
          <button
            type="button"
            class="toolbar-button toolbar-button--primary"
            :disabled="isBusy"
            @click="openCreateDatasetDialog"
          >
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
            <template
              v-for="dataset in filteredDatasets"
              :key="dataset.id"
            >
              <tr
                class="dataset-row"
                :class="{
                  'dataset-row--selected': dataset.id === selectedDatasetId,
                  'dataset-row--linked': isLinkedToActiveSession(dataset),
                }"
                @click="toggleDatasetRow(dataset.id)"
              >
                <td>
                  <div class="dataset-name-cell">
                    <strong>{{ dataset.filename }}</strong>
                    <span>{{ dataset.storagePath ?? "원천 데이터 연결" }}</span>
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
                      :disabled="isBusy"
                      @click.stop="openSessionLinkDialog(dataset.id)"
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
              <tr
                v-if="dataset.id === selectedDatasetId"
                class="dataset-source-detail-row"
              >
                <td colspan="6">
                  <section class="dataset-source-detail">
                    <header>
                      <div>
                        <strong>연결된 원천 데이터</strong>
                        <span>
                          {{ formatNumber(dataset.sourceTree?.length ? selectedDatasetSourceRows.filter((item) => item.itemType === "file").length : 0) }}개 파일
                        </span>
                      </div>
                      <small>{{ dataset.description || "설명 없음" }}</small>
                    </header>

                    <div
                      v-if="selectedDatasetSourceRows.length > 0"
                      class="dataset-linked-source-tree"
                    >
                      <div
                        v-for="sourceItem in selectedDatasetSourceRows"
                        :key="sourceItem.id"
                        class="dataset-linked-source-row"
                        :class="{
                          'dataset-linked-source-row--folder': sourceItem.itemType === 'folder',
                        }"
                        :style="{ '--source-depth': sourceItem.depth }"
                      >
                        <span class="material-symbols-outlined">
                          {{ sourceItem.itemType === "folder" ? "folder" : "description" }}
                        </span>
                        <div>
                          <strong>{{ sourceItem.name }}</strong>
                          <small>{{ sourceItem.relativePath }}</small>
                        </div>
                        <em v-if="sourceItem.itemType === 'folder'">
                          {{ formatNumber(sourceItem.fileCount) }}개 파일
                        </em>
                        <em v-else>
                          {{ formatNumber(sourceItem.rowCount) }}행 ·
                          {{ formatNumber(sourceItem.columnCount) }}열
                        </em>
                      </div>
                    </div>

                    <div v-else class="dataset-source-detail__empty">
                      <span class="material-symbols-outlined">account_tree</span>
                      연결된 원천 데이터 정보를 불러오는 중입니다.
                    </div>
                  </section>
                </td>
              </tr>
            </template>
            <tr v-if="filteredDatasets.length === 0">
              <td colspan="6" class="empty-row">
                <span class="material-symbols-outlined">database_off</span>
                검색 조건에 맞는 데이터 소스가 없어요.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div
      v-if="isCreateDialogOpen"
      class="dataset-create-backdrop"
      role="presentation"
      @click.self="closeCreateDatasetDialog"
    >
      <section
        class="dataset-create-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dataset-create-title"
      >
        <header class="dataset-create-header">
          <div>
            <p>데이터셋 만들기</p>
            <h3 id="dataset-create-title">원천 데이터에서 데이터셋 구성</h3>
          </div>
          <button
            type="button"
            class="icon-button"
            :disabled="isCreatePending"
            aria-label="닫기"
            @click="closeCreateDatasetDialog"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>

        <div
          v-if="isCreatePending"
          class="dataset-create-progress"
          role="status"
          aria-live="polite"
        >
          <div>
            <span class="material-symbols-outlined">progress_activity</span>
            <strong>데이터셋을 만들고 있습니다</strong>
            <small>{{ createDatasetProgressMessage }}</small>
          </div>
          <div class="dataset-create-progress__meta">
            <span>
              {{ formatNumber(selectedSourceFileCount) }}개 파일 ·
              {{ selectedSourceSizeLabel }}
            </span>
            <strong>{{ createDatasetProgressLabel }}</strong>
          </div>
          <span
            class="dataset-create-progress__bar"
            role="progressbar"
            aria-label="데이터셋 생성 진행률"
            :aria-valuenow="Math.round(createDatasetProgressPercent)"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <span :style="{ width: createDatasetProgressLabel }"></span>
          </span>
        </div>

        <div class="dataset-create-body">
          <section class="dataset-create-form">
            <label class="dataset-field">
              <span>데이터셋 명</span>
              <input
                v-model="datasetNameInput"
                type="text"
                placeholder="예: 2026년 주문 데이터셋"
                :disabled="isCreatePending"
              />
            </label>
            <label class="dataset-field">
              <span>데이터셋 설명</span>
              <textarea
                v-model="datasetDescriptionInput"
                rows="4"
                placeholder="포함 범위, 사용 목적, 주의할 점을 적어두세요."
                :disabled="isCreatePending"
              ></textarea>
            </label>

            <div class="source-mode-switch" aria-label="데이터셋 소스 유형">
              <button type="button" class="source-mode-switch__button source-mode-switch__button--active">
                <span class="material-symbols-outlined">folder_open</span>
                원천 데이터
              </button>
              <button type="button" class="source-mode-switch__button" disabled>
                <span class="material-symbols-outlined">database</span>
                DB 연결
              </button>
            </div>
          </section>

          <section class="dataset-source-picker">
            <div class="dataset-source-toolbar">
              <label class="library-search dataset-source-search">
                <span class="material-symbols-outlined">search</span>
                <input
                  v-model="sourceSearchQuery"
                  type="search"
                  placeholder="원천 데이터 파일 또는 폴더 검색"
                  :disabled="isCreatePending"
                />
              </label>
              <strong>{{ selectedSourceFileCount }}개 파일 선택</strong>
            </div>

            <div class="dataset-source-tree">
              <button
                v-for="sourceItem in visibleSourceItems"
                :key="sourceItem.id"
                type="button"
                class="dataset-source-row"
                :class="{
                  'dataset-source-row--folder': sourceItem.itemType === 'folder',
                  'dataset-source-row--selected': selectedSourceIds.has(sourceItem.id),
                }"
                :style="{ '--source-depth': sourceItem.depth }"
                :disabled="isCreatePending"
                @click="toggleSourceSelection(sourceItem)"
              >
                <span
                  v-if="sourceItem.itemType === 'folder'"
                  class="material-symbols-outlined source-caret"
                  @click.stop="toggleSourceFolder(sourceItem)"
                >
                  {{ collapsedSourceFolderIds.has(sourceItem.id) ? "chevron_right" : "expand_more" }}
                </span>
                <span v-else class="source-caret"></span>
                <span class="source-check material-symbols-outlined">
                  {{ selectedSourceIds.has(sourceItem.id) ? "check_box" : "check_box_outline_blank" }}
                </span>
                <span class="source-kind material-symbols-outlined">
                  {{ sourceItem.itemType === "folder" ? "folder" : "description" }}
                </span>
                <span class="source-name">
                  <strong>{{ sourceItem.name }}</strong>
                  <small>{{ sourceItem.relativePath }}</small>
                </span>
              </button>

              <div v-if="visibleSourceItems.length === 0" class="source-empty-state">
                <span class="material-symbols-outlined">folder_off</span>
                원천 데이터가 없거나 검색 결과가 없습니다.
              </div>
            </div>
          </section>
        </div>

        <p v-if="createDatasetError" class="library-error dataset-create-error">
          {{ createDatasetError }}
        </p>

        <footer class="dataset-create-actions">
          <button
            type="button"
            class="toolbar-button"
            :disabled="isCreatePending"
            @click="closeCreateDatasetDialog"
          >
            취소
          </button>
          <button
            type="button"
            class="toolbar-button toolbar-button--primary"
            :disabled="isCreatePending"
            @click="submitCreateDataset"
          >
            <span class="material-symbols-outlined">
              {{ isCreatePending ? "progress_activity" : "add" }}
            </span>
            {{ isCreatePending ? "생성 중" : "생성" }}
          </button>
        </footer>
      </section>
    </div>

    <div
      v-if="sessionLinkDatasetId"
      class="dataset-create-backdrop"
      role="presentation"
      @click.self="closeSessionLinkDialog"
    >
      <section
        class="session-link-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-link-title"
      >
        <header class="dataset-create-header">
          <div>
            <p>워크스페이스 연결</p>
            <h3 id="session-link-title">데이터셋을 연결할 워크스페이스 선택</h3>
            <small>{{ sessionLinkDataset?.filename ?? "선택한 데이터셋" }}</small>
          </div>
          <button
            type="button"
            class="icon-button"
            :disabled="isBusy"
            aria-label="닫기"
            @click="closeSessionLinkDialog"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>

        <div class="session-link-list">
          <p v-if="workspaceListError" class="library-error">{{ workspaceListError }}</p>

          <div v-if="isWorkspaceListLoading" class="session-link-empty">
            <span class="material-symbols-outlined">progress_activity</span>
            워크스페이스 목록을 불러오는 중입니다.
          </div>

          <template v-else>
            <article v-for="workspace in linkableWorkspaces" :key="workspace.id" class="session-link-item">
              <div>
                <strong>
                  {{ workspace.name }}
                  <em v-if="workspace.id === activeWorkspaceId">현재</em>
                </strong>
                <span>최근 수정 {{ formatDate(workspace.updatedAt) }}</span>
              </div>
              <button
                type="button"
                class="action-button action-button--primary"
                :disabled="isBusy || isWorkspaceListLoading"
                @click="attachDatasetToWorkspace(workspace.id)"
              >
                <span class="material-symbols-outlined">link</span>
                연결
              </button>
            </article>
          </template>

          <div v-if="!isWorkspaceListLoading && linkableWorkspaces.length === 0" class="session-link-empty">
            <span class="material-symbols-outlined">chat_error</span>
            연결할 워크스페이스가 없습니다.
          </div>
        </div>
      </section>
    </div>
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

.dataset-source-detail-row > td {
  padding: 0;
  background: #f8fbff;
}

.dataset-source-detail {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 16px 18px 18px;
  border-top: 1px solid rgba(24, 74, 140, 0.16);
  border-bottom: 1px solid rgba(24, 74, 140, 0.16);
}

.dataset-source-detail header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.dataset-source-detail header > div {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.dataset-source-detail header strong {
  color: var(--color-primary-strong);
  font-size: 0.92rem;
}

.dataset-source-detail header span,
.dataset-source-detail header small {
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.dataset-linked-source-tree {
  max-height: 260px;
  overflow: auto;
  display: grid;
  gap: 4px;
  padding: 6px;
  border: 1px solid rgba(24, 74, 140, 0.12);
  border-radius: 8px;
  background: #fff;
}

.dataset-linked-source-row {
  min-height: 42px;
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 7px 10px 7px calc(10px + (var(--source-depth, 0) * 18px));
  border-radius: 7px;
  color: var(--color-text);
}

.dataset-linked-source-row--folder {
  background: rgba(24, 74, 140, 0.05);
}

.dataset-linked-source-row .material-symbols-outlined {
  color: var(--color-primary);
  font-size: 1.15rem;
}

.dataset-linked-source-row div {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.dataset-linked-source-row strong,
.dataset-linked-source-row small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataset-linked-source-row strong {
  font-size: 0.86rem;
}

.dataset-linked-source-row small,
.dataset-linked-source-row em {
  color: var(--color-text-muted);
  font-size: 0.76rem;
  font-style: normal;
}

.dataset-source-detail__empty {
  min-height: 120px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  border: 1px dashed rgba(24, 74, 140, 0.2);
  border-radius: 8px;
  color: var(--color-text-muted);
  background: #fff;
  text-align: center;
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

.dataset-create-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
  background: rgba(15, 23, 42, 0.42);
}

.dataset-create-dialog {
  width: min(1040px, 100%);
  max-height: min(760px, calc(100vh - 56px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-strong);
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.28);
}

.dataset-create-header,
.dataset-create-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--color-border);
}

.dataset-create-header p {
  margin: 0 0 4px;
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.dataset-create-header h3 {
  margin: 0;
  color: var(--color-text);
  font-size: 1.08rem;
}

.dataset-create-progress {
  display: grid;
  gap: 12px;
  padding: 14px 20px 16px;
  border-bottom: 1px solid rgba(24, 74, 140, 0.16);
  background: #f7fbff;
}

.dataset-create-progress > div {
  display: grid;
  grid-template-columns: 28px minmax(0, max-content) minmax(0, 1fr);
  align-items: center;
  gap: 10px;
}

.dataset-create-progress .material-symbols-outlined {
  color: var(--color-primary);
  animation: dataset-create-spin 1s linear infinite;
}

.dataset-create-progress strong {
  color: var(--color-primary-strong);
  font-size: 0.9rem;
}

.dataset-create-progress small {
  min-width: 0;
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.dataset-create-progress__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.dataset-create-progress__meta > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataset-create-progress__meta > strong {
  flex: 0 0 auto;
  color: var(--color-primary-strong);
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
}

.dataset-create-progress__bar {
  position: relative;
  display: block;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(24, 74, 140, 0.14);
}

.dataset-create-progress__bar > span {
  display: block;
  width: 0;
  height: 100%;
  border-radius: inherit;
  background: var(--color-primary);
  transition: width 0.28s ease;
}

.dataset-create-body {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(260px, 0.42fr) minmax(0, 1fr);
}

.dataset-create-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  border-right: 1px solid var(--color-border);
  background: #fbfcfe;
}

.dataset-field {
  display: grid;
  gap: 8px;
}

.dataset-field > span {
  color: var(--color-text);
  font-size: 0.84rem;
  font-weight: 800;
}

.dataset-field input,
.dataset-field textarea {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text);
  font: inherit;
}

.dataset-field input {
  min-height: 42px;
  padding: 0 12px;
}

.dataset-field textarea {
  resize: vertical;
  min-height: 104px;
  padding: 12px;
  line-height: 1.5;
}

.dataset-field input:focus,
.dataset-field textarea:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px rgba(24, 74, 140, 0.12);
}

.dataset-field input:disabled,
.dataset-field textarea:disabled,
.library-search input:disabled {
  cursor: wait;
  opacity: 0.7;
}

.source-mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 5px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-muted);
}

.source-mode-switch__button {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-muted);
  font: inherit;
  font-size: 0.84rem;
  font-weight: 800;
}

.source-mode-switch__button--active {
  color: var(--color-primary);
  background: #fff;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
}

.source-mode-switch__button:disabled {
  opacity: 0.55;
}

.dataset-source-picker {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.dataset-source-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--color-border);
}

.dataset-source-toolbar strong {
  flex: 0 0 auto;
  color: var(--color-primary-strong);
  font-size: 0.84rem;
}

.dataset-source-search {
  min-width: 0;
}

.dataset-source-tree {
  min-height: 320px;
  overflow: auto;
  padding: 8px;
}

.dataset-source-row {
  width: 100%;
  min-height: 46px;
  display: grid;
  grid-template-columns: 24px 24px 26px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  padding: 7px 10px 7px calc(10px + (var(--source-depth, 0) * 18px));
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.dataset-source-row:hover,
.dataset-source-row:focus-visible {
  border-color: var(--color-border);
  background: #f8fbff;
  outline: none;
}

.dataset-source-row--selected {
  border-color: rgba(24, 74, 140, 0.26);
  background: rgba(24, 74, 140, 0.07);
}

.dataset-source-row:disabled {
  cursor: wait;
  opacity: 0.72;
}

.source-caret,
.source-check,
.source-kind {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.source-caret {
  color: var(--color-text-muted);
}

.source-check {
  color: var(--color-primary);
}

.source-kind {
  color: var(--color-primary-strong);
}

.source-name {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.source-name strong,
.source-name small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-name strong {
  font-size: 0.9rem;
}

.source-name small {
  color: var(--color-text-muted);
  font-size: 0.76rem;
}

.source-empty-state {
  min-height: 220px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: var(--color-text-muted);
  text-align: center;
}

.source-empty-state .material-symbols-outlined {
  color: var(--color-primary);
  font-size: 2rem;
}

.dataset-create-error {
  border-top: 1px solid rgba(155, 59, 59, 0.18);
}

.dataset-create-actions {
  justify-content: flex-end;
  border-top: 1px solid var(--color-border);
  border-bottom: 0;
}

@keyframes dataset-create-spin {
  to {
    transform: rotate(360deg);
  }
}

.session-link-dialog {
  width: min(560px, 100%);
  max-height: min(640px, calc(100vh - 48px));
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 22px 50px rgba(15, 23, 42, 0.24);
}

.dataset-create-header small {
  display: block;
  margin-top: 6px;
  color: var(--color-text-muted);
}

.session-link-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 10px;
  overflow-y: auto;
  padding: 16px 20px 20px;
}

.session-link-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
}

.session-link-item div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.session-link-item strong,
.session-link-item span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-link-item strong em {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 6px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  font-size: 0.72rem;
  font-style: normal;
}

.session-link-item span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.session-link-empty {
  min-height: 180px;
  display: grid;
  place-items: center;
  gap: 10px;
  color: var(--color-text-muted);
  text-align: center;
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

  .dataset-create-body {
    grid-template-columns: 1fr;
  }

  .dataset-create-form {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
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

  .dataset-create-backdrop {
    align-items: stretch;
    padding: 12px;
  }

  .dataset-create-dialog {
    max-height: calc(100vh - 24px);
  }

  .dataset-create-header,
  .dataset-create-actions,
  .dataset-create-form,
  .dataset-source-toolbar {
    padding: 14px;
  }

  .dataset-source-toolbar {
    display: grid;
  }

  .source-mode-switch {
    grid-template-columns: 1fr;
  }
}
</style>
