import { getPortalApiBaseUrl, readPortalApiErrorDetail } from '@/shared/api/portalApi'

export interface DataSourceItemResponse {
  id: string
  parent_id: string | null
  item_type: 'file' | 'folder'
  name: string
  relative_path: string
  depth: number
  sort_order: number
  content_type: string | null
  size_bytes: number | null
  storage_path: string | null
  created_at: string
  updated_at: string
  children: DataSourceItemResponse[]
}

export interface DataSourceUploadResponse {
  items: DataSourceItemResponse[]
}

export interface DataSourceTreeResponse {
  items: DataSourceItemResponse[]
}

/** 파일 또는 폴더 선택 결과를 원천 데이터 저장소에 업로드합니다. */
export async function uploadDataSources(
  files: File[],
  signal?: AbortSignal,
): Promise<DataSourceUploadResponse> {
  const formData = new FormData()
  for (const file of files) {
    const uploadPath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name
    formData.append('files', file, uploadPath)
    formData.append('relative_paths', uploadPath)
  }

  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/data-sources/uploads`, {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    const detail = await readPortalApiErrorDetail(response)
    throw new Error(detail || `Data source upload failed with status ${response.status}`)
  }

  return (await response.json()) as DataSourceUploadResponse
}

/** 원천 데이터 파일 트리를 조회합니다. */
export async function fetchDataSourceTree(signal?: AbortSignal): Promise<DataSourceTreeResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/data-sources/tree`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    const detail = await readPortalApiErrorDetail(response)
    throw new Error(detail || `Data source tree failed with status ${response.status}`)
  }

  return (await response.json()) as DataSourceTreeResponse
}
