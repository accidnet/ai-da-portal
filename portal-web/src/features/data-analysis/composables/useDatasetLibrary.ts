import { computed, ref, type ComputedRef, type Ref } from 'vue'

import {
  attachDatasetToWorkspace,
  createDatasetFromSources,
  deleteDataset,
  detachDatasetFromWorkspace,
  fetchDatasetPreview,
  fetchDatasetProfile,
  fetchDatasetSources,
  fetchDatasets,
  uploadDataset,
} from '@/features/data-analysis/api/analysisApi'
import type { DatasetLibraryItem, SessionItem } from '../types'
import type { CreateDatasetFromSourcesPayload } from '@/features/data-analysis/api/analysisApi'
import { DEFAULT_SESSION_TITLE } from '../constants/analysisPage'
import { mapDatasetLibraryItem, mapDatasetSourceTreeItem } from '../utils/analysisPageHelpers'
import { mapDatasetInfoToAsset, type SessionRuntimeState } from '../utils/sessionState'

export function useDatasetLibrary(options: {
  activeSessionId: Ref<string | null>
  activeWorkspaceId: Ref<string | null>
  activeSessionSummary: ComputedRef<SessionItem | null>
  sessionSummaries: Ref<SessionItem[]>
  sessionStates: Ref<Record<string, SessionRuntimeState>>
  ensureActiveSession: () => Promise<string>
  ensureSessionState: (sessionId: string, title: string) => SessionRuntimeState
  syncSessionSummaryWithState: (sessionId: string) => void
}) {
  const {
    activeSessionId,
    activeWorkspaceId,
    activeSessionSummary,
    sessionSummaries,
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
    if (!target || (target.preview && target.profile && target.sourceTree)) {
      return target ?? null
    }

    try {
      const [preview, profile, sources] = await Promise.all([
        fetchDatasetPreview(datasetId),
        fetchDatasetProfile(datasetId),
        fetchDatasetSources(datasetId),
      ])
      target.preview = { columns: preview.columns, rows: preview.rows }
      target.profile = {
        rowCount: profile.profile.row_count,
        columnCount: profile.profile.column_count,
        columns: profile.profile.columns.map((column) => ({
          name: column.name,
          dtype: column.dtype,
          nullRatio: column.null_ratio,
          minValue: column.min_value,
          maxValue: column.max_value,
          sampleValues: column.sample_values,
        })),
      }
      target.sourceTree = sources.sources.map(mapDatasetSourceTreeItem)
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

  /** 원천 데이터 트리 선택 결과로 서버 데이터셋을 생성하고 목록을 갱신합니다. */
  async function handleCreateDatasetFromSources(payload: CreateDatasetFromSourcesPayload) {
    try {
      isDatasetMutating.value = true
      datasetLibraryError.value = null
      const created = await createDatasetFromSources(payload)
      await loadDatasets()
      selectedDatasetId.value = created.id
      await ensureDatasetLibraryDetails(created.id)
    } catch (error) {
      datasetLibraryError.value = error instanceof Error ? error.message : '데이터셋 생성에 실패했어요.'
    } finally {
      isDatasetMutating.value = false
    }
  }

  function openDatasetPicker() {
    datasetPickerRef.value?.click()
  }

  /** 선택된 원천 데이터 파일 하나를 업로드하고 세션 상태에 반영합니다. */
  async function processDatasetFile(file: File, sessionId: string): Promise<boolean> {
    try {
      const detail = await uploadDataset(file, sessionId)
      const [preview, profile] = await Promise.all([fetchDatasetPreview(detail.id), fetchDatasetProfile(detail.id)])
      const dataset = mapDatasetInfoToAsset({ detail, preview, profile })
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
      return true
    } catch {
      return false
    }
  }

  /** 파일 여러 개 또는 폴더 선택 결과를 순차 업로드합니다. */
  async function processDatasetFiles(files: File[]) {
    if (files.length === 0) return

    uploadError.value = null
    isUploading.value = true

    try {
      const sessionId = await ensureActiveSession()
      let successCount = 0

      for (const file of files) {
        const isUploaded = await processDatasetFile(file, sessionId)
        if (isUploaded) successCount += 1
      }

      await loadDatasets()

      if (successCount < files.length) {
        uploadError.value =
          successCount > 0
            ? `${successCount}개 파일은 업로드했지만 ${files.length - successCount}개 파일은 처리하지 못했어요.`
            : '선택한 파일을 업로드하지 못했어요. 서버에서 처리 가능한 데이터 형식인지 확인해 주세요.'
      }
    } finally {
      isUploading.value = false
    }
  }

  function handleDatasetFileChange(event: Event) {
    const input = event.target as HTMLInputElement
    const files = Array.from(input.files ?? [])
    input.value = ''
    if (files.length > 0) void processDatasetFiles(files)
  }

  async function handleSelectDataset(datasetId: string | null) {
    if (datasetId === null) {
      selectedDatasetId.value = null
      return
    }

    selectedDatasetId.value = datasetId
    await ensureDatasetLibraryDetails(datasetId)
  }

  async function handleAttachDataset(datasetId: string, targetWorkspaceId?: string) {
    const workspaceId = targetWorkspaceId ?? activeWorkspaceId.value
    if (!workspaceId) {
      datasetLibraryError.value = '활성 워크스페이스가 없어 데이터셋을 연결할 수 없어요.'
      return
    }
    const sessionId = activeSessionId.value ?? await ensureActiveSession()
    try {
      isDatasetMutating.value = true
      const linked = await attachDatasetToWorkspace(workspaceId, datasetId)
      const details = await ensureDatasetLibraryDetails(datasetId)
      if (details && workspaceId === activeWorkspaceId.value) {
        const sessionTitle =
          sessionId === activeSessionId.value
            ? activeSessionSummary.value?.title
            : sessionSummaries.value.find((session) => session.id === sessionId)?.title
        const state = ensureSessionState(sessionId, sessionTitle ?? DEFAULT_SESSION_TITLE)
        const asset = mapDatasetInfoToAsset({
          detail: {
            id: details.id,
            filename: details.filename,
            name: details.name,
            description: details.description,
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
                    min_value: column.minValue,
                    max_value: column.maxValue,
                    sample_values: column.sampleValues,
                  })),
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
    const workspaceId = activeWorkspaceId.value
    if (!sessionId || !workspaceId) {
      datasetLibraryError.value = '활성 워크스페이스가 없어 연결 해제를 진행할 수 없어요.'
      return
    }
    try {
      isDatasetMutating.value = true
      const linked = await detachDatasetFromWorkspace(workspaceId, datasetId)
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
    handleCreateDatasetFromSources,
    handleSelectDataset,
    handleAttachDataset,
    handleDetachDataset,
    handleDeleteDataset,
    removeSessionLinks,
  }
}
