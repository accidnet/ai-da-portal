<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import {
  fetchWorkspaceFiles,
  readWorkspaceFile,
} from '@/features/data-analysis/api/analysisApi'
import type {
  WorkspaceFileContentResponse,
  WorkspaceFileEntryResponse,
} from '@/features/data-analysis/api/analysisApi'
import type { WorkspaceItem } from '../../types'

const props = defineProps<{
  open: boolean
  workspace: WorkspaceItem | null
}>()

const emit = defineEmits<{
  close: []
}>()

const currentPath = ref('')
const entries = ref<WorkspaceFileEntryResponse[]>([])
const selectedFile = ref<WorkspaceFileEntryResponse | null>(null)
const fileContent = ref<WorkspaceFileContentResponse | null>(null)
const isListing = ref(false)
const isReading = ref(false)
const hasMore = ref(false)
const explorerError = ref<string | null>(null)
const readerError = ref<string | null>(null)
const fileExplorerBody = ref<HTMLElement | null>(null)
const browserPanePercent = ref(38)
const isResizing = ref(false)
let listingController: AbortController | null = null
let readingController: AbortController | null = null

const pathSegments = computed(() => (
  currentPath.value ? currentPath.value.split('/').filter(Boolean) : []
))

const sortedEntries = computed(() => entries.value)
const fileExplorerBodyStyle = computed(() => ({
  '--file-browser-width': `${browserPanePercent.value}%`,
}))

/** 현재 경로의 상위 경로를 계산합니다. */
function parentPath(path: string): string {
  const segments = path.split('/').filter(Boolean)
  segments.pop()
  return segments.join('/')
}

/** 경로 일부를 눌렀을 때 이동할 breadcrumb 경로를 계산합니다. */
function breadcrumbPath(index: number): string {
  return pathSegments.value.slice(0, index + 1).join('/')
}

/** 바이트 단위 크기를 사용자가 읽기 쉬운 문자열로 변환합니다. */
function formatFileSize(sizeBytes: number | null): string {
  if (sizeBytes === null) return '-'
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`
}

/** API의 수정 시각을 사이드바 탐색용 짧은 표기로 변환합니다. */
function formatUpdatedAt(updatedAt: string): string {
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(updatedAt))
}

/** 폴더 목록을 현재 경로 기준으로 lazy loading 합니다. */
async function loadEntries(path = '') {
  if (!props.workspace) return

  listingController?.abort()
  const controller = new AbortController()
  listingController = controller
  isListing.value = true
  explorerError.value = null
  readerError.value = null
  selectedFile.value = null
  fileContent.value = null

  try {
    const response = await fetchWorkspaceFiles(
      props.workspace.id,
      path,
      controller.signal,
    )
    currentPath.value = response.path
    entries.value = response.entries
    hasMore.value = response.has_more
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    explorerError.value = '폴더 구성을 불러오지 못했어요.'
  } finally {
    if (listingController === controller) {
      isListing.value = false
    }
  }
}

/** 선택한 파일의 read-only 미리보기 내용을 불러옵니다. */
async function selectFile(entry: WorkspaceFileEntryResponse) {
  if (!props.workspace || entry.kind !== 'file') return

  readingController?.abort()
  const controller = new AbortController()
  readingController = controller
  selectedFile.value = entry
  fileContent.value = null
  readerError.value = null
  isReading.value = true

  try {
    fileContent.value = await readWorkspaceFile(
      props.workspace.id,
      entry.path,
      controller.signal,
    )
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    readerError.value = '파일 내용을 불러오지 못했어요.'
  } finally {
    if (readingController === controller) {
      isReading.value = false
    }
  }
}

/** 항목 타입에 맞게 폴더 이동 또는 파일 미리보기를 실행합니다. */
function openEntry(entry: WorkspaceFileEntryResponse) {
  if (entry.kind === 'directory') {
    void loadEntries(entry.path)
    return
  }
  void selectFile(entry)
}

/** 좌우 패널 사이 resizer 드래그를 시작합니다. */
function startPaneResize(event: PointerEvent) {
  isResizing.value = true
  event.preventDefault()
  window.addEventListener('pointermove', resizePane)
  window.addEventListener('pointerup', stopPaneResize)
}

/** 모달 너비 안에서 브라우저 패널 비율을 계산해 갱신합니다. */
function resizePane(event: PointerEvent) {
  const body = fileExplorerBody.value
  if (!body) return

  const rect = body.getBoundingClientRect()
  const nextPercent = ((event.clientX - rect.left) / rect.width) * 100
  browserPanePercent.value = Math.min(Math.max(nextPercent, 28), 68)
}

/** 드래그 종료 시 전역 포인터 이벤트를 정리합니다. */
function stopPaneResize() {
  isResizing.value = false
  window.removeEventListener('pointermove', resizePane)
  window.removeEventListener('pointerup', stopPaneResize)
}

/** 닫기 시 진행 중인 요청을 정리하고 상태를 초기화합니다. */
function closeDialog() {
  listingController?.abort()
  readingController?.abort()
  stopPaneResize()
  emit('close')
}

watch(
  () => props.open,
  (open) => {
    if (!open) return
    currentPath.value = ''
    void loadEntries('')
  },
)

onBeforeUnmount(() => {
  stopPaneResize()
})
</script>

<template>
  <div v-if="open" class="file-explorer-backdrop" role="presentation" @click.self="closeDialog">
    <section class="file-explorer" role="dialog" aria-modal="true" aria-labelledby="file-explorer-title">
      <header class="file-explorer__header">
        <div>
          <p>파일 탐색</p>
          <h2 id="file-explorer-title">{{ workspace?.name }}</h2>
        </div>
        <button type="button" class="file-explorer__close" aria-label="닫기" @click="closeDialog">
          <span class="material-symbols-outlined">close</span>
        </button>
      </header>

      <div
        ref="fileExplorerBody"
        class="file-explorer__body"
        :class="{ 'file-explorer__body--resizing': isResizing }"
        :style="fileExplorerBodyStyle"
      >
        <section class="file-explorer__browser" aria-label="워크스페이스 파일 목록">
          <nav class="file-explorer__breadcrumbs" aria-label="현재 경로">
            <button type="button" :class="{ active: !currentPath }" @click="loadEntries('')">
              root
            </button>
            <template v-for="(segment, index) in pathSegments" :key="`${segment}-${index}`">
              <span>/</span>
              <button type="button" :class="{ active: index === pathSegments.length - 1 }" @click="loadEntries(breadcrumbPath(index))">
                {{ segment }}
              </button>
            </template>
          </nav>

          <button v-if="currentPath" type="button" class="file-explorer__back" @click="loadEntries(parentPath(currentPath))">
            <span class="material-symbols-outlined">arrow_upward</span>
            <span>상위 폴더</span>
          </button>

          <p v-if="explorerError" class="file-explorer__error">{{ explorerError }}</p>
          <p v-else-if="isListing" class="file-explorer__empty">불러오는 중...</p>
          <p v-else-if="sortedEntries.length === 0" class="file-explorer__empty">표시할 파일이 없어요.</p>

          <div v-else class="file-explorer__list">
            <button
              v-for="entry in sortedEntries"
              :key="entry.path"
              type="button"
              class="file-entry"
              :class="{
                'file-entry--selected': selectedFile?.path === entry.path,
                'file-entry--folder': entry.kind === 'directory',
              }"
              :title="entry.path"
              @click="openEntry(entry)"
            >
              <span class="file-entry__icon material-symbols-outlined">
                {{ entry.kind === 'directory' ? 'folder' : 'description' }}
              </span>
              <span class="file-entry__name">{{ entry.name }}</span>
              <span class="file-entry__meta">{{ formatFileSize(entry.size_bytes) }}</span>
              <span class="file-entry__meta">{{ formatUpdatedAt(entry.updated_at) }}</span>
            </button>
          </div>

          <p v-if="hasMore" class="file-explorer__notice">항목이 많아 처음 200개만 표시합니다.</p>
        </section>

        <button
          type="button"
          class="file-explorer__resizer"
          role="separator"
          aria-label="파일 탐색 패널 크기 조절"
          aria-orientation="vertical"
          :aria-valuenow="Math.round(browserPanePercent)"
          aria-valuemin="28"
          aria-valuemax="68"
          @pointerdown="startPaneResize"
        ></button>

        <section class="file-explorer__preview" aria-label="파일 미리보기">
          <div v-if="!selectedFile" class="file-preview__empty">
            <span class="material-symbols-outlined">article</span>
            <p>미리볼 파일을 선택하세요.</p>
          </div>
          <div v-else class="file-preview">
            <header class="file-preview__header">
              <div>
                <h3>{{ selectedFile.name }}</h3>
                <p>{{ selectedFile.path }} · {{ formatFileSize(selectedFile.size_bytes) }}</p>
              </div>
            </header>

            <p v-if="readerError" class="file-explorer__error">{{ readerError }}</p>
            <p v-else-if="isReading" class="file-explorer__empty">파일을 읽는 중...</p>
            <p v-else-if="fileContent?.is_binary" class="file-explorer__empty">바이너리 파일은 미리볼 수 없어요.</p>
            <div v-else class="file-preview__content">
              <p v-if="fileContent?.truncated" class="file-explorer__notice">파일이 커서 일부만 표시합니다.</p>
              <pre>{{ fileContent?.content ?? '' }}</pre>
            </div>
          </div>
        </section>
      </div>
    </section>
  </div>
</template>

<style scoped>
.file-explorer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 45;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.34);
}

.file-explorer {
  width: min(980px, 100%);
  height: min(720px, calc(100vh - 48px));
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  border: 1px solid #dfe6ef;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.22);
  overflow: hidden;
}

.file-explorer__header {
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #e5eaf1;
}

.file-explorer__header p,
.file-explorer__header h2 {
  margin: 0;
}

.file-explorer__header p {
  color: #66758a;
  font-size: 12px;
  font-weight: 800;
}

.file-explorer__header h2 {
  margin-top: 4px;
  color: #111827;
  font-size: 19px;
  font-weight: 800;
}

.file-explorer__close {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  color: #4b5563;
  background: #fff;
  cursor: pointer;
}

.file-explorer__close:hover,
.file-explorer__close:focus-visible {
  color: var(--color-primary-strong);
  background: #f3f7fc;
  outline: none;
}

.file-explorer__body {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(300px, var(--file-browser-width, 38%)) 8px minmax(0, 1fr);
}

.file-explorer__body--resizing {
  cursor: col-resize;
  user-select: none;
}

.file-explorer__browser,
.file-explorer__preview {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 10px;
  padding: 16px;
}

.file-explorer__browser {
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  background: #f8fafc;
}

.file-explorer__resizer {
  position: relative;
  width: 8px;
  min-width: 8px;
  height: 100%;
  padding: 0;
  border: 0;
  border-left: 1px solid #e5eaf1;
  border-right: 1px solid #e5eaf1;
  background: #f1f5f9;
  cursor: col-resize;
}

.file-explorer__resizer::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 2px;
  height: 36px;
  border-radius: 999px;
  background: #94a3b8;
  transform: translate(-50%, -50%);
}

.file-explorer__resizer:hover,
.file-explorer__resizer:focus-visible,
.file-explorer__body--resizing .file-explorer__resizer {
  background: #e8f0f8;
  outline: none;
}

.file-explorer__resizer:hover::before,
.file-explorer__resizer:focus-visible::before,
.file-explorer__body--resizing .file-explorer__resizer::before {
  background: var(--color-primary);
}

.file-explorer__preview {
  background: #fff;
  overflow: hidden;
}

.file-explorer__breadcrumbs {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  color: #64748b;
  font-size: 13px;
}

.file-explorer__breadcrumbs button,
.file-explorer__back {
  min-width: 0;
  border: 0;
  color: inherit;
  background: transparent;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.file-explorer__breadcrumbs button {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-explorer__breadcrumbs button.active {
  color: #111827;
}

.file-explorer__back {
  justify-self: start;
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  border-radius: 8px;
  color: #334155;
}

.file-explorer__back:hover,
.file-explorer__back:focus-visible,
.file-explorer__breadcrumbs button:hover,
.file-explorer__breadcrumbs button:focus-visible {
  color: var(--color-primary-strong);
  background: #eef3f9;
  outline: none;
}

.file-explorer__back .material-symbols-outlined {
  font-size: 17px;
}

.file-explorer__list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 6px;
  overflow-y: auto;
  padding-right: 4px;
}

.file-entry {
  min-width: 0;
  min-height: 42px;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) 72px 94px;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: #253044;
  background: #fff;
  font: inherit;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.file-entry:hover,
.file-entry:focus-visible,
.file-entry--selected {
  border-color: rgba(43, 94, 162, 0.16);
  background: #eef3f9;
  outline: none;
}

.file-entry__icon {
  color: #64748b;
  font-size: 20px;
}

.file-entry--folder .file-entry__icon {
  color: var(--color-primary);
}

.file-entry__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 800;
}

.file-entry__meta {
  min-width: 0;
  overflow: hidden;
  color: #66758a;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-preview,
.file-preview__content {
  min-height: 0;
  display: grid;
}

.file-preview {
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  height: 100%;
}

.file-preview__header {
  display: flex;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5eaf1;
}

.file-preview__header h3,
.file-preview__header p {
  margin: 0;
}

.file-preview__header h3 {
  color: #111827;
  font-size: 15px;
  font-weight: 800;
}

.file-preview__header p {
  margin-top: 5px;
  color: #66758a;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-all;
}

.file-preview__content {
  overflow: hidden;
}

.file-preview__content pre {
  min-height: 0;
  margin: 0;
  overflow: auto;
  padding: 14px;
  border: 1px solid #e5eaf1;
  border-radius: 8px;
  color: #1f2937;
  background: #f8fafc;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.file-preview__empty {
  height: 100%;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: #66758a;
  text-align: center;
}

.file-preview__empty .material-symbols-outlined {
  color: #94a3b8;
  font-size: 34px;
}

.file-preview__empty p,
.file-explorer__empty,
.file-explorer__error,
.file-explorer__notice {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
}

.file-explorer__empty {
  color: #66758a;
}

.file-explorer__error {
  color: #a23a3a;
}

.file-explorer__notice {
  color: #7c5a1f;
}

@media (max-width: 760px) {
  .file-explorer {
    height: calc(100vh - 32px);
  }

  .file-explorer__body {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(260px, 46%) minmax(0, 1fr);
  }

  .file-explorer__resizer {
    display: none;
  }

  .file-explorer__browser {
    border-right: 0;
    border-bottom: 1px solid #e5eaf1;
  }

  .file-entry {
    grid-template-columns: 24px minmax(0, 1fr) 64px;
  }

  .file-entry__meta:last-child {
    display: none;
  }
}
</style>
