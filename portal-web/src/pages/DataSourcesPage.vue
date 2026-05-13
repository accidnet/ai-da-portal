<script setup lang="ts">
import DataSourceLibrary from '@/features/data-source/components/DataSourceLibrary.vue'
import type {
  DataSourceItem,
  DataSourceUploadProgress,
  DatasetLibraryItem,
  UploadPickerMode,
} from '@/features/data-source/types'

defineProps<{
  activeSessionId: string | null
  datasetsLibrary: DatasetLibraryItem[]
  dataSourceItems: DataSourceItem[]
  dataSourceUploadProgress: DataSourceUploadProgress
  selectedDatasetId: string | null
  datasetLibrarySearchQuery: string
  datasetLibraryError: string | null
  isDatasetMutating: boolean
}>()

const emit = defineEmits<{
  datasetLibrarySearchChange: [value: string]
  uploadDataset: [mode?: UploadPickerMode]
  selectDataset: [datasetId: string]
  attachDataset: [datasetId: string]
  detachDataset: [datasetId: string]
  deleteDataset: [datasetId: string]
}>()
</script>

<template>
  <DataSourceLibrary
    :datasets="datasetsLibrary"
    :data-source-items="dataSourceItems"
    :data-source-upload-progress="dataSourceUploadProgress"
    :selected-dataset-id="selectedDatasetId"
    :active-session-id="activeSessionId"
    :search-query="datasetLibrarySearchQuery"
    :is-busy="isDatasetMutating"
    :error-message="datasetLibraryError"
    @search-change="(value) => emit('datasetLibrarySearchChange', value)"
    @upload-file="(mode) => emit('uploadDataset', mode)"
    @select-dataset="(datasetId) => emit('selectDataset', datasetId)"
    @attach-dataset="(datasetId) => emit('attachDataset', datasetId)"
    @detach-dataset="(datasetId) => emit('detachDataset', datasetId)"
    @delete-dataset="(datasetId) => emit('deleteDataset', datasetId)"
  />
</template>
