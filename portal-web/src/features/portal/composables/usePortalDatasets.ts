import { computed, ref, type ComputedRef, type Ref } from 'vue'

import {
  attachDatasetToSession,
  deleteDataset,
  detachDatasetFromSession,
  fetchDatasetPreview,
  fetchDatasetProfile,
  fetchDatasets,
  uploadDataset,
} from '../../../shared/api/portalApi'
import type { DatasetLibraryItem, SessionItem } from '../types'
import { DEFAULT_SESSION_TITLE } from '../constants/portalPage'
import { isUploadableDatasetFile, mapDatasetLibraryItem } from '../utils/portalPageHelpers'
import { mapDatasetDetailToAsset, type SessionRuntimeState } from '../utils/sessionState'

export function usePortalDatasets(options: {
  activeSessionId: Ref<string | null>
  activeSessionSummary: ComputedRef<SessionItem | null>
  sessionStates: Ref<Record<string, SessionRuntimeState>>
  ensureActiveSession: () => Promise<string>
  ensureSessionState: (sessionId: string, title: string) => SessionRuntimeState
  syncSessionSummaryWithState: (sessionId: string) => void
}) {
  const {
    activeSessionId,
    activeSessionSummary,
    sessionStates,
    ensureActiveSession,
    ensureSessionState,
    syncSessionSummaryWithState,
  } = options

  const datasetsLibrary = ref<DatasetLibraryItem[]>([])
  const selectedDatasetId = ref<string | null>(null)
  const datasetPickerRef = ref<HTMLInputElement | null>(null)
  const datasetLibraryError = ref<string | null>(null)
  const isDatasetMutating = ref(false)
  const isUploading = ref(false)
  const uploadError = ref<string | null>(null)

  const selectedDataset = computed(() => datasetsLibrary.value.find((dataset) => dataset.id === selectedDatasetId.value) ?? null)

  async function ensureDatasetLibraryDetails(datasetId: string) {
    const target = datasetsLibrary.value.find((dataset) => dataset.id === datasetId)
    if (!target || (target.preview && target.profile)) {
      return target ?? null
    }

    try {
      const [preview, profile] = await Promise.all([fetchDatasetPreview(datasetId), fetchDatasetProfile(datasetId)])
      target.preview = { columns: preview.columns, rows: preview.rows }
      target.profile = {
        rowCount: profile.profile.row_count,
        columnCount: profile.profile.column_count,
        columns: profile.profile.columns.map((column) => ({
          name: column.name,
          dtype: column.dtype,
          nullRatio: column.null_ratio,
          sampleValues: column.sample_values,
        })),
        suggestedPrompts: profile.profile.suggested_prompts,
      }
      datasetsLibrary.value = [...datasetsLibrary.value]
    } catch {
      datasetLibraryError.value = '데이터셋 상세 정보를 불러오지 못했어요.'
    }

    return target
  }

  async function loadDatasets() {
    try {
      const datasets = await fetchDatasets()
      datasetsLibrary.value = datasets.map(mapDatasetLibraryItem)
      if (!selectedDatasetId.value || !datasetsLibrary.value.some((dataset) => dataset.id === selectedDatasetId.value)) {
        selectedDatasetId.value = datasetsLibrary.value[0]?.id ?? null
      }
      if (selectedDatasetId.value) {
        await ensureDatasetLibraryDetails(selectedDatasetId.value)
      }
      datasetLibraryError.value = null
    } catch {
      datasetLibraryError.value = '데이터 소스 목록을 불러오지 못했어요.'
    }
  }

  function openDatasetPicker() {
    datasetPickerRef.value?.click()
  }

  async function processDatasetFile(file: File) {
    if (!isUploadableDatasetFile(file)) {
      uploadError.value = 'CSV 또는 스프레드시트 파일만 업로드할 수 있어요.'
      return
    }

    uploadError.value = null
    isUploading.value = true

    try {
      const sessionId = await ensureActiveSession()
      const detail = await uploadDataset(file, sessionId)
      const [preview, profile] = await Promise.all([fetchDatasetPreview(detail.id), fetchDatasetProfile(detail.id)])
      const dataset = mapDatasetDetailToAsset({ detail, preview, profile })
      const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE)
      sessionState.datasets = [dataset, ...sessionState.datasets.filter((item) => item.id !== dataset.id)]
      sessionState.analyticsPayload = null
      sessionState.workspacePayload = null
      sessionState.messages = [
        ...sessionState.messages,
        {
          role: 'assistant',
          author: 'AI 데이터 분석가',
          text: `${dataset.filename} 업로드를 완료했어요. 이제 같은 데이터셋 ID로 채팅과 분석을 이어서 실행할 수 있어요.`,
          bullets: [
            {
              text: `${dataset.profile?.rowCount ?? 0}행 / ${dataset.profile?.columnCount ?? 0}열 프로파일을 반영했어요`,
            },
            { text: '오른쪽 패널에 서버 기준 미리보기와 프로파일이 반영돼요' },
            { text: '이제 프롬프트 전송과 분석 실행이 같은 데이터셋을 사용해요' },
          ],
        },
      ]
      activeSessionId.value = sessionId
      syncSessionSummaryWithState(sessionId)
      await loadDatasets()
    } catch {
      uploadError.value = '데이터셋 업로드에 실패했어요. CSV 또는 스프레드시트 파일로 다시 시도해 주세요.'
    } finally {
      isUploading.value = false
    }
  }

  function handleDatasetFileChange(event: Event) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    input.value = ''
    if (file) void processDatasetFile(file)
  }

  async function handleSelectDataset(datasetId: string) {
    selectedDatasetId.value = datasetId
    await ensureDatasetLibraryDetails(datasetId)
  }

  async function handleAttachDataset(datasetId: string) {
    const sessionId = await ensureActiveSession()
    try {
      isDatasetMutating.value = true
      const linked = await attachDatasetToSession(sessionId, datasetId)
      const details = await ensureDatasetLibraryDetails(datasetId)
      if (details) {
        const state = ensureSessionState(sessionId, activeSessionSummary.value?.title ?? DEFAULT_SESSION_TITLE)
        const asset = mapDatasetDetailToAsset({
          detail: {
            id: details.id,
            filename: details.filename,
            content_type: details.contentType,
            storage_path: details.storagePath,
            created_at: details.createdAt,
          },
          preview: details.preview
            ? {
                dataset_id: details.id,
                columns: details.preview.columns,
                rows: details.preview.rows,
              }
            : null,
          profile: details.profile
            ? {
                dataset_id: details.id,
                profile: {
                  row_count: details.profile.rowCount,
                  column_count: details.profile.columnCount,
                  columns: details.profile.columns.map((column) => ({
                    name: column.name,
                    dtype: column.dtype,
                    null_ratio: column.nullRatio,
                    sample_values: column.sampleValues,
                  })),
                  suggested_prompts: details.profile.suggestedPrompts,
                },
              }
            : null,
        })
        const byId = new Map([...state.datasets, asset].map((dataset) => [dataset.id, dataset]))
        state.datasets = linked.dataset_ids
          .map((id) => byId.get(id))
          .filter((dataset): dataset is NonNullable<typeof dataset> => Boolean(dataset))
        syncSessionSummaryWithState(sessionId)
      }
      await loadDatasets()
      datasetLibraryError.value = null
    } catch (error) {
      datasetLibraryError.value = error instanceof Error ? error.message : '데이터셋 연결에 실패했어요.'
    } finally {
      isDatasetMutating.value = false
    }
  }

  async function handleDetachDataset(datasetId: string) {
    const sessionId = activeSessionId.value
    if (!sessionId) {
      datasetLibraryError.value = '활성 세션이 없어 연결 해제를 진행할 수 없어요.'
      return
    }
    try {
      isDatasetMutating.value = true
      const linked = await detachDatasetFromSession(sessionId, datasetId)
      const state = ensureSessionState(sessionId, activeSessionSummary.value?.title ?? DEFAULT_SESSION_TITLE)
      state.datasets = state.datasets.filter((dataset) => linked.dataset_ids.includes(dataset.id))
      syncSessionSummaryWithState(sessionId)
      await loadDatasets()
      datasetLibraryError.value = null
    } catch (error) {
      datasetLibraryError.value = error instanceof Error ? error.message : '데이터셋 연결 해제에 실패했어요.'
    } finally {
      isDatasetMutating.value = false
    }
  }

  async function handleDeleteDataset(datasetId: string) {
    try {
      isDatasetMutating.value = true
      await deleteDataset(datasetId)
      datasetsLibrary.value = datasetsLibrary.value.filter((dataset) => dataset.id !== datasetId)
      for (const state of Object.values(sessionStates.value)) {
        state.datasets = state.datasets.filter((dataset) => dataset.id !== datasetId)
      }
      if (selectedDatasetId.value === datasetId) {
        selectedDatasetId.value = datasetsLibrary.value[0]?.id ?? null
      }
      if (activeSessionId.value) {
        syncSessionSummaryWithState(activeSessionId.value)
      }
      datasetLibraryError.value = null
    } catch (error) {
      datasetLibraryError.value = error instanceof Error ? error.message : '연결된 데이터셋은 삭제할 수 없어요.'
    } finally {
      isDatasetMutating.value = false
    }
  }

  function removeSessionLinks(sessionId: string) {
    datasetsLibrary.value = datasetsLibrary.value.map((dataset) => {
      const linkedSessionIds = dataset.linkedSessionIds.filter((id) => id !== sessionId)
      return {
        ...dataset,
        linkedSessionIds,
        linkedSessionCount: linkedSessionIds.length,
      }
    })
  }

  return {
    datasetsLibrary,
    selectedDatasetId,
    selectedDataset,
    datasetPickerRef,
    datasetLibraryError,
    isDatasetMutating,
    isUploading,
    uploadError,
    ensureDatasetLibraryDetails,
    loadDatasets,
    openDatasetPicker,
    processDatasetFile,
    handleDatasetFileChange,
    handleSelectDataset,
    handleAttachDataset,
    handleDetachDataset,
    handleDeleteDataset,
    removeSessionLinks,
  }
}
