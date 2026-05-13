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

export interface DatasetLibraryItem {
  id: string
  filename: string
  storagePath: string | null
  createdAt: string
  rowCount: number
  columnCount: number
  linkedSessionCount: number
  linkedSessionIds: string[]
  latestUsedAt: string | null
  preview?: DatasetPreview | null
  profile?: DatasetProfile | null
}

export interface DatasetAsset {
  id: string
  filename: string
  createdAt: string
  preview?: DatasetPreview | null
  profile?: DatasetProfile | null
}

export type UploadPickerMode = 'files' | 'folder'
