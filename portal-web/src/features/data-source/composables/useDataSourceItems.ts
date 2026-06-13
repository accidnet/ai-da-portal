import { ref } from 'vue'

import type {
  DataSourceItem,
  DataSourceUploadProgress,
  UploadPickerOptions,
} from '@/features/data-source/types'
import {
  deleteDataSourceItem,
  fetchDataSourceTree,
  uploadDataSources,
  type DataSourceItemResponse,
} from '@/features/data-source/api/dataSourceApi'

/** 원천 데이터 API 응답을 화면 모델로 변환합니다. */
function mapDataSourceItem(item: DataSourceItemResponse): DataSourceItem {
  return {
    id: item.id,
    parentId: item.parent_id,
    itemType: item.item_type,
    name: item.name,
    relativePath: item.relative_path,
    depth: item.depth,
    sortOrder: item.sort_order,
    contentType: item.content_type,
    sizeBytes: item.size_bytes,
    storagePath: item.storage_path,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    children: item.children.map(mapDataSourceItem),
  }
}

/** 새 업로드 진행 상태를 만듭니다. */
function createUploadProgress(): DataSourceUploadProgress {
  return {
    status: 'idle',
    fileCount: 0,
    loadedBytes: 0,
    totalBytes: 0,
    percent: 0,
    message: '',
    startedAt: null,
    updatedAt: null,
  }
}

/** 파일 선택 결과에 zip이 있으면 트리 구성 여부를 사용자에게 확인합니다. */
function resolveZipExtraction(files: File[], options: UploadPickerOptions): boolean {
  if (options.extractZip !== undefined) return options.extractZip
  if (!files.some(isZipFile) || typeof window === 'undefined') return false

  return window.confirm(
    '선택한 파일에 zip 파일이 포함되어 있습니다.\n압축 해제 후 내부 데이터로 폴더 트리를 구성할까요?',
  )
}

/** 브라우저가 전달한 파일 메타데이터로 zip 파일 여부를 판단합니다. */
function isZipFile(file: File): boolean {
  const contentType = file.type.toLowerCase()
  return file.name.toLowerCase().endsWith('.zip') || contentType === 'application/zip'
}

export function useDataSourceItems() {
  const dataSourceItems = ref<DataSourceItem[]>([])
  const dataSourceError = ref<string | null>(null)
  const isDataSourceUploading = ref(false)
  const isDataSourceMutating = ref(false)
  const dataSourceUploadProgress = ref<DataSourceUploadProgress>(createUploadProgress())

  /** 원천 데이터 트리를 서버에서 조회합니다. */
  async function loadDataSourceTree() {
    try {
      const response = await fetchDataSourceTree()
      dataSourceItems.value = response.items.map(mapDataSourceItem)
      dataSourceError.value = null
    } catch {
      dataSourceError.value = '원천 데이터 목록을 불러오지 못했어요.'
    }
  }

  /** 파일 또는 폴더 선택 결과를 원천 데이터 저장소에 업로드합니다. */
  async function handleDataSourceFileChange(event: Event, options: UploadPickerOptions = {}) {
    const input = event.target as HTMLInputElement
    const files = Array.from(input.files ?? [])
    input.value = ''
    if (files.length === 0) return

    try {
      const extractZip = resolveZipExtraction(files, options)
      isDataSourceUploading.value = true
      const totalBytes = files.reduce((sum, file) => sum + file.size, 0)
      const now = new Date().toISOString()
      dataSourceUploadProgress.value = {
        status: 'queued',
        fileCount: files.length,
        loadedBytes: 0,
        totalBytes,
        percent: 0,
        message: '업로드 대기 중',
        startedAt: now,
        updatedAt: now,
      }
      await uploadDataSources(files, {
        extractZip,
        onProgress: ({ loadedBytes, totalBytes: progressTotalBytes, percent }) => {
          dataSourceUploadProgress.value = {
            ...dataSourceUploadProgress.value,
            status: 'uploading',
            loadedBytes,
            totalBytes: progressTotalBytes,
            percent,
            message: '파일을 서버로 전송 중',
            updatedAt: new Date().toISOString(),
          }
        },
      })
      dataSourceUploadProgress.value = {
        ...dataSourceUploadProgress.value,
        status: 'processing',
        percent: 100,
        message: '서버에서 파일 구조를 반영 중',
        updatedAt: new Date().toISOString(),
      }
      await loadDataSourceTree()
      dataSourceError.value = null
      dataSourceUploadProgress.value = {
        ...dataSourceUploadProgress.value,
        status: 'completed',
        loadedBytes: dataSourceUploadProgress.value.totalBytes,
        percent: 100,
        message: '업로드 완료',
        updatedAt: new Date().toISOString(),
      }
    } catch (error) {
      dataSourceError.value = error instanceof Error ? error.message : '원천 데이터 업로드에 실패했어요.'
      dataSourceUploadProgress.value = {
        ...dataSourceUploadProgress.value,
        status: 'failed',
        message: '업로드 실패',
        updatedAt: new Date().toISOString(),
      }
    } finally {
      isDataSourceUploading.value = false
    }
  }

  /** 원천 데이터 파일 또는 폴더를 삭제하고 트리를 갱신합니다. */
  async function handleDeleteDataSourceItem(itemId: string) {
    try {
      isDataSourceMutating.value = true
      await deleteDataSourceItem(itemId)
      await loadDataSourceTree()
      dataSourceError.value = null
    } catch (error) {
      dataSourceError.value = error instanceof Error ? error.message : '원천 데이터를 삭제하지 못했어요.'
    } finally {
      isDataSourceMutating.value = false
    }
  }

  return {
    dataSourceItems,
    dataSourceError,
    isDataSourceUploading,
    isDataSourceMutating,
    dataSourceUploadProgress,
    loadDataSourceTree,
    handleDataSourceFileChange,
    handleDeleteDataSourceItem,
  }
}
