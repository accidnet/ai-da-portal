import { computed, ref, type ComputedRef } from 'vue'

import { createAnalysis, sendChatInteraction, streamChatMessage, type ChatInteractionResponse } from '../../../shared/api/portalApi'
import type { ChatMessage, MessageAttachmentPreview } from '../types'
import { DEFAULT_SESSION_TITLE } from '../constants/portalPage'
import {
  buildReportContent,
  createAttachmentPreview,
  isUploadableDatasetFile,
  normalizeAssistantMessage,
  sanitizeFileNameSegment,
} from '../utils/portalPageHelpers'
import {
  buildSharedAnalysisUrl,
  copyTextToClipboard,
  createSharedAnalysisSnapshot,
  openAnalysisPreview,
  saveSharedAnalysisSnapshot,
} from '../utils/portalShare'
import { mapDatasetAsset, type SessionRuntimeState } from '../utils/sessionState'

export function usePortalInteractions(options: {
  activeSessionState: ComputedRef<SessionRuntimeState | null>
  activeDataset: ComputedRef<SessionRuntimeState['datasets'][number] | null>
  analyticsPayload: ComputedRef<SessionRuntimeState['analyticsPayload']>
  workspacePayload: ComputedRef<SessionRuntimeState['workspacePayload']>
  ensureActiveSession: () => Promise<string>
  ensureSessionState: (sessionId: string, title: string) => SessionRuntimeState
  updateSessionTitleLocally: (sessionId: string, title: string) => void
  syncSessionSummaryWithState: (sessionId: string) => void
  loadDatasets: () => Promise<void>
  openDatasetPicker: () => void
}) {
  const {
    activeSessionState,
    activeDataset,
    analyticsPayload,
    workspacePayload,
    ensureActiveSession,
    ensureSessionState,
    updateSessionTitleLocally,
    syncSessionSummaryWithState,
    loadDatasets,
    openDatasetPicker,
  } = options

  const interactionPickerRef = ref<HTMLInputElement | null>(null)
  const pendingAttachment = ref<File | null>(null)
  const chatError = ref<string | null>(null)
  const analyticsError = ref<string | null>(null)
  const exportMessage = ref<string | null>(null)
  const isSending = ref(false)
  const isRunningAnalysis = ref(false)
  const isSendingInteraction = ref(false)

  function openInteractionPicker() {
    interactionPickerRef.value?.click()
  }

  function clearPendingAttachment() {
    pendingAttachment.value = null
  }

  function clearInteractionFeedback() {
    chatError.value = null
    analyticsError.value = null
    exportMessage.value = null
  }

  function queueInteractionFile(file: File, setUploadError: (message: string | null) => void) {
    if (!isUploadableDatasetFile(file)) {
      setUploadError('CSV 또는 스프레드시트 파일만 업로드할 수 있어요.')
      return
    }
    setUploadError(null)
    pendingAttachment.value = file
  }

  function handleInteractionFileChange(event: Event, setUploadError: (message: string | null) => void) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    input.value = ''
    if (file) queueInteractionFile(file, setUploadError)
  }

  async function handleSendMessage(message: string, options: { setUploadError: (message: string | null) => void }) {
    const { setUploadError } = options

    clearInteractionFeedback()
    setUploadError(null)
    const sessionId = await ensureActiveSession()
    const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE)
    const attachedFile = pendingAttachment.value
    const userMessage = message || (attachedFile ? `${attachedFile.name} 파일을 분석해줘.` : '')
    const userMessageEntry: ChatMessage = {
      role: 'user',
      text: userMessage,
    }
    sessionState.messages = [...sessionState.messages, userMessageEntry]
    isSending.value = true
    isSendingInteraction.value = Boolean(attachedFile)
    pendingAttachment.value = null
    const assistantMessageIndex = sessionState.messages.length

    if (!attachedFile) {
      sessionState.messages = [
        ...sessionState.messages,
        {
          role: 'assistant',
          author: 'AI 데이터 분석가',
          text: '',
        },
      ]
    }

    try {
      const response = attachedFile
        ? await sendChatInteraction({
            sessionId,
            message: userMessage,
            datasetIds: sessionState.datasets.map((dataset) => dataset.id),
            file: attachedFile,
          })
        : await streamChatMessage({
            sessionId,
            message: userMessage,
            datasetIds: sessionState.datasets.map((dataset) => dataset.id),
          }, {
            onDelta(delta) {
              const current = sessionState.messages[assistantMessageIndex]
              if (!current || current.role !== 'assistant') return
              sessionState.messages = sessionState.messages.map((entry, index) =>
                index === assistantMessageIndex
                  ? {
                      ...entry,
                      text: `${entry.text}${delta}`,
                    }
                  : entry,
              )
            },
          })
      const interactionResponse = attachedFile ? (response as ChatInteractionResponse) : null
      const nextSessionTitle = response.session_title?.trim()

      if (nextSessionTitle) {
        updateSessionTitleLocally(sessionId, nextSessionTitle)
      }

      let attachmentPreview: MessageAttachmentPreview | undefined

      if (interactionResponse?.dataset) {
        const uploadedDataset = interactionResponse.dataset
        const dataset = mapDatasetAsset(uploadedDataset)
        sessionState.datasets = [dataset, ...sessionState.datasets.filter((item) => item.id !== dataset.id)]
        attachmentPreview = createAttachmentPreview(
          uploadedDataset.detail.filename,
          attachedFile?.size ?? 0,
          uploadedDataset.preview,
        )
        await loadDatasets()
      }

      const assistantMessage = {
        role: 'assistant' as const,
        author: 'AI 데이터 분석가',
        text: normalizeAssistantMessage(response.assistant_message),
        route: response.route,
        usedTools: response.used_tools,
        attachmentPreview,
      }

      sessionState.messages = attachedFile
        ? [...sessionState.messages, assistantMessage]
        : sessionState.messages.map((entry, index) =>
            index === assistantMessageIndex ? assistantMessage : entry,
          )
      sessionState.analyticsPayload = response.analytics
      sessionState.workspacePayload = response.workspace
      syncSessionSummaryWithState(sessionId)
    } catch (error) {
      chatError.value =
        error instanceof Error
          ? error.message
          : '메시지를 보내지 못했어요. ChatGPT 연결과 백엔드 상태를 확인해 주세요.'
      pendingAttachment.value = attachedFile
      if (!attachedFile) {
        sessionState.messages = sessionState.messages.filter(
          (_, index) => index !== assistantMessageIndex,
        )
      }
    } finally {
      isSending.value = false
      isSendingInteraction.value = false
    }
  }

  async function runAnalysis() {
    analyticsError.value = null
    exportMessage.value = null
    const sessionId = await ensureActiveSession()
    const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE)
    const primaryDataset = sessionState.datasets[0]
    if (!primaryDataset) {
      analyticsError.value = '분석을 실행하려면 먼저 데이터셋을 업로드해 주세요.'
      return
    }

    isRunningAnalysis.value = true
    try {
      const analysis = await createAnalysis({
        sessionId,
        datasetId: primaryDataset.id,
        analysisType: 'dataset_profile',
        prompt: `Generate a dashboard-ready profile for ${primaryDataset.filename}.`,
      })
      sessionState.analyticsPayload = analysis.analytics
      sessionState.workspacePayload = analysis.workspace
      sessionState.messages = [
        ...sessionState.messages,
        {
          role: 'assistant',
          author: 'AI 데이터 분석가',
          text: analysis.analytics?.insights[0]?.body ?? '분석이 완료되어 실시간 분석 패널을 업데이트했어요.',
        },
      ]
      syncSessionSummaryWithState(sessionId)
    } catch {
      analyticsError.value = '분석을 시작하지 못했어요. 잠시 후 다시 시도해 주세요.'
    } finally {
      isRunningAnalysis.value = false
    }
  }

  async function handleSuggestedPrompt(prompt: string, setUploadError: (message: string | null) => void) {
    if (!prompt || isSending.value || isRunningAnalysis.value) return
    await handleSendMessage(prompt, { setUploadError })
  }

  async function handleInsightAction() {
    if (isSending.value || isRunningAnalysis.value) return
    if (activeDataset.value) {
      await runAnalysis()
      return
    }
    openDatasetPicker()
  }

  function exportAnalyticsReport() {
    const content = buildReportContent({
      sessionState: activeSessionState.value,
      dataset: activeDataset.value,
      analytics: analyticsPayload.value,
      workspace: workspacePayload.value,
    }).trim()
    if (!content) return
    const fileName = `${sanitizeFileNameSegment(activeSessionState.value?.title ?? DEFAULT_SESSION_TITLE)}.md`
    const opened = openAnalysisPreview({
      title: activeSessionState.value?.title ?? DEFAULT_SESSION_TITLE,
      fileName,
      content,
      createdAt: new Date().toISOString(),
    })
    exportMessage.value = opened
      ? '새 탭에서 리포트 미리보기를 열었어요. 미리보기 화면에서 다운로드할 수 있어요.'
      : '미리보기를 열지 못했어요. 팝업 차단 설정을 확인해 주세요.'
  }

  async function shareAnalyticsReport() {
    const content = buildReportContent({
      sessionState: activeSessionState.value,
      dataset: activeDataset.value,
      analytics: analyticsPayload.value,
      workspace: workspacePayload.value,
    }).trim()
    if (!content) return

    const snapshot = createSharedAnalysisSnapshot({
      title: activeSessionState.value?.title ?? DEFAULT_SESSION_TITLE,
      fileName: `${sanitizeFileNameSegment(activeSessionState.value?.title ?? DEFAULT_SESSION_TITLE)}.md`,
      content,
    })
    saveSharedAnalysisSnapshot(snapshot)
    const url = buildSharedAnalysisUrl(snapshot.id)
    const copied = await copyTextToClipboard(url)
    exportMessage.value = copied
      ? '공유 링크를 복사했어요. 같은 브라우저 환경에서 미리보기를 열 수 있어요.'
      : `공유 링크를 생성했지만 자동 복사는 실패했어요: ${url}`
  }

  const canExportReport = computed(() =>
    Boolean(
      activeDataset.value ||
        analyticsPayload.value?.summary_cards?.length ||
        analyticsPayload.value?.charts?.length ||
        analyticsPayload.value?.tables?.length ||
        analyticsPayload.value?.insights?.length ||
        activeSessionState.value?.messages?.length,
    ),
  )

  return {
    interactionPickerRef,
    pendingAttachment,
    chatError,
    analyticsError,
    exportMessage,
    isSending,
    isRunningAnalysis,
    isSendingInteraction,
    canExportReport,
    openInteractionPicker,
    clearPendingAttachment,
    clearInteractionFeedback,
    queueInteractionFile,
    handleInteractionFileChange,
    handleSendMessage,
    runAnalysis,
    handleSuggestedPrompt,
    handleInsightAction,
    exportAnalyticsReport,
    shareAnalyticsReport,
  }
}
