import { ref } from 'vue'

import type { DataSourceItem, DataSourceUploadProgress } from '@/features/data-source/types'
import {
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

export function useDataSourceItems() {
  const dataSourceItems = ref<DataSourceItem[]>([])
  const dataSourceError = ref<string | null>(null)
  const isDataSourceUploading = ref(false)
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
  async function handleDataSourceFileChange(event: Event) {
    const input = event.target as HTMLInputElement
    const files = Array.from(input.files ?? [])
    input.value = ''
    if (files.length === 0) return

    try {
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
    } catch {
      dataSourceError.value = '원천 데이터 업로드에 실패했어요.'
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

  return {
    dataSourceItems,
    dataSourceError,
    isDataSourceUploading,
    dataSourceUploadProgress,
    loadDataSourceTree,
    handleDataSourceFileChange,
  }
}
