export interface DatasetColumnProfile {
  name: string
  dtype: string
  nullRatio: number
  minValue?: string | number | null
  maxValue?: string | number | null
  sampleValues: string[]
}

export interface DatasetProfile {
  rowCount: number
  columnCount: number
  columns: DatasetColumnProfile[]
}

export interface DatasetPreview {
  columns: string[]
  rows: Record<string, string | number | null>[]
}

export interface DatasetSourceTreeItem {
  id: string
  sourceRefId: string | null
  itemType: 'file' | 'folder'
  name: string
  relativePath: string
  depth: number
  contentType: string | null
  sizeBytes: number | null
  rowCount: number
  columnCount: number
  fileCount: number
  children: DatasetSourceTreeItem[]
}

export interface DatasetLibraryItem {
  id: string
  filename: string
  name?: string | null
  description?: string | null
  storagePath: string | null
  createdAt: string
  rowCount: number
  columnCount: number
  linkedSessionCount: number
  linkedSessionIds: string[]
  latestUsedAt: string | null
  preview?: DatasetPreview | null
  profile?: DatasetProfile | null
  sourceTree?: DatasetSourceTreeItem[] | null
}

export interface DatasetAsset {
  id: string
  filename: string
  name?: string | null
  description?: string | null
  createdAt: string
  preview?: DatasetPreview | null
  profile?: DatasetProfile | null
}

export type UploadPickerMode = 'files' | 'folder'
export type UploadPickerTarget = 'dataset' | 'data-source'
export type DataSourceUploadStatus = 'idle' | 'queued' | 'uploading' | 'processing' | 'completed' | 'failed'

export interface DataSourceUploadProgress {
  status: DataSourceUploadStatus
  fileCount: number
  loadedBytes: number
  totalBytes: number
  percent: number
  message: string
  startedAt: string | null
  updatedAt: string | null
}

export interface DataSourceItem {
  id: string
  parentId: string | null
  itemType: 'file' | 'folder'
  name: string
  relativePath: string
  depth: number
  sortOrder: number
  contentType: string | null
  sizeBytes: number | null
  storagePath: string | null
  createdAt: string
  updatedAt: string
  children: DataSourceItem[]
}
