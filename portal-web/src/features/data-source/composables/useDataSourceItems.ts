import { ref } from 'vue'

import type { DataSourceItem } from '@/features/data-source/types'
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

export function useDataSourceItems() {
  const dataSourceItems = ref<DataSourceItem[]>([])
  const dataSourceError = ref<string | null>(null)
  const isDataSourceUploading = ref(false)

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
      await uploadDataSources(files)
      await loadDataSourceTree()
      dataSourceError.value = null
    } catch {
      dataSourceError.value = '원천 데이터 업로드에 실패했어요.'
    } finally {
      isDataSourceUploading.value = false
    }
  }

  return {
    dataSourceItems,
    dataSourceError,
    isDataSourceUploading,
    loadDataSourceTree,
    handleDataSourceFileChange,
  }
}
