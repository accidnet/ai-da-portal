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

export interface DataSourceDeleteResponse {
  id: string
  deleted: boolean
  deleted_count: number
}

export interface DataSourceUploadProgressEvent {
  loadedBytes: number
  totalBytes: number
  percent: number
}

export interface DataSourceUploadOptions {
  signal?: AbortSignal
  onProgress?: (event: DataSourceUploadProgressEvent) => void
}

/** XMLHttpRequest 오류 응답에서 FastAPI detail 메시지를 추출합니다. */
function parseUploadErrorDetail(responseText: string): string {
  try {
    const errorBody = JSON.parse(responseText) as { detail?: string }
    return errorBody.detail?.trim() ?? ''
  } catch {
    return ''
  }
}

/** 파일 또는 폴더 선택 결과를 원천 데이터 저장소에 업로드합니다. */
export async function uploadDataSources(
  files: File[],
  options: DataSourceUploadOptions = {},
): Promise<DataSourceUploadResponse> {
  const formData = new FormData()
  for (const file of files) {
    const uploadPath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name
    formData.append('files', file, uploadPath)
    formData.append('relative_paths', uploadPath)
  }

  return new Promise<DataSourceUploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const abortUpload = () => xhr.abort()

    xhr.open('POST', `${getPortalApiBaseUrl()}/api/v1/data-sources/uploads`)
    xhr.responseType = 'text'

    xhr.upload.onprogress = (event) => {
      const totalBytes = event.lengthComputable ? event.total : files.reduce((sum, file) => sum + file.size, 0)
      const loadedBytes = event.loaded
      const percent = totalBytes > 0 ? Math.min(Math.round((loadedBytes / totalBytes) * 100), 100) : 0
      options.onProgress?.({ loadedBytes, totalBytes, percent })
    }

    xhr.onload = () => {
      options.signal?.removeEventListener('abort', abortUpload)
      if (xhr.status < 200 || xhr.status >= 300) {
        const detail = parseUploadErrorDetail(xhr.responseText)
        reject(new Error(detail || `Data source upload failed with status ${xhr.status}`))
        return
      }

      try {
        resolve(JSON.parse(xhr.responseText) as DataSourceUploadResponse)
      } catch {
        reject(new Error('Data source upload response parsing failed.'))
      }
    }

    xhr.onerror = () => {
      options.signal?.removeEventListener('abort', abortUpload)
      reject(new Error('Data source upload failed.'))
    }

    xhr.onabort = () => {
      options.signal?.removeEventListener('abort', abortUpload)
      reject(new DOMException('Data source upload aborted.', 'AbortError'))
    }

    if (options.signal) {
      if (options.signal.aborted) {
        xhr.abort()
        return
      }
      options.signal.addEventListener('abort', abortUpload, { once: true })
    }

    options.onProgress?.({
      loadedBytes: 0,
      totalBytes: files.reduce((sum, file) => sum + file.size, 0),
      percent: 0,
    })
    xhr.send(formData)
  })
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

/** 원천 데이터 파일 또는 폴더 노드를 삭제합니다. */
export async function deleteDataSourceItem(
  itemId: string,
  signal?: AbortSignal,
): Promise<DataSourceDeleteResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/data-sources/${itemId}`, {
    method: 'DELETE',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    const detail = await readPortalApiErrorDetail(response)
    throw new Error(detail || `Data source delete failed with status ${response.status}`)
  }

  return (await response.json()) as DataSourceDeleteResponse
}
