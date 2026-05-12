<script setup lang="ts">
import DatasetLibrary from '@/features/data-analysis/components/DatasetLibrary.vue'
import type { DatasetLibraryItem } from '@/features/data-analysis/types'

defineProps<{
  activeSessionId: string | null
  datasetsLibrary: DatasetLibraryItem[]
  selectedDatasetId: string | null
  datasetLibrarySearchQuery: string
  datasetLibraryError: string | null
  isDatasetMutating: boolean
}>()

const emit = defineEmits<{
  datasetLibrarySearchChange: [value: string]
  uploadDataset: []
  selectDataset: [datasetId: string]
  attachDataset: [datasetId: string]
  detachDataset: [datasetId: string]
  deleteDataset: [datasetId: string]
}>()
</script>

<template>
  <DatasetLibrary
    :datasets="datasetsLibrary"
    :selected-dataset-id="selectedDatasetId"
    :active-session-id="activeSessionId"
    :search-query="datasetLibrarySearchQuery"
    :is-busy="isDatasetMutating"
    :error-message="datasetLibraryError"
    @search-change="(value) => emit('datasetLibrarySearchChange', value)"
    @upload-file="emit('uploadDataset')"
    @select-dataset="(datasetId) => emit('selectDataset', datasetId)"
    @attach-dataset="(datasetId) => emit('attachDataset', datasetId)"
    @detach-dataset="(datasetId) => emit('detachDataset', datasetId)"
    @delete-dataset="(datasetId) => emit('deleteDataset', datasetId)"
  />
</template>
