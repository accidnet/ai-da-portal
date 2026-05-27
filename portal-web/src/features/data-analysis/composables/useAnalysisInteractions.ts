import { computed, ref, type ComputedRef } from 'vue'

import {
  resolveSessionTitle,
  streamChatMessage,
  type AgentChartStreamPayload,
  type AgentPlanStreamPayload,
  type AgentStateStreamPayload,
  type ChatSubMessageStreamEvent,
} from '@/features/data-analysis/api/analysisApi'
import type {
  AnalyticsChartPayload,
  AnalyticsPayload,
  ChatMessage,
  ChatSubMessage,
} from '../types'
import { DEFAULT_SESSION_TITLE } from '../constants/analysisPage'
import {
  buildReportContent,
  normalizeAssistantMessage,
  sanitizeFileNameSegment,
} from '../utils/analysisPageHelpers'
import {
  buildSharedAnalysisUrl,
  copyTextToClipboard,
  createSharedAnalysisSnapshot,
  openAnalysisPreview,
  saveSharedAnalysisSnapshot,
} from '../utils/analysisShare'
import type { SessionRuntimeState } from '../utils/sessionState'

export function useAnalysisInteractions(options: {
  activeSessionState: ComputedRef<SessionRuntimeState | null>
  activeWorkspaceId?: ComputedRef<string | null>
  activeDataset: ComputedRef<SessionRuntimeState['datasets'][number] | null>
  analyticsPayload: ComputedRef<SessionRuntimeState['analyticsPayload']>
  workspacePayload: ComputedRef<SessionRuntimeState['workspacePayload']>
  ensureActiveSession: () => Promise<string>
  ensureSessionState: (sessionId: string, title: string) => SessionRuntimeState
  updateSessionTitleLocally: (sessionId: string, title: string) => void
  syncSessionSummaryWithState: (sessionId: string) => void
  revealSessionSummary: (sessionId: string, fallbackTitle?: string) => void
  openDatasetPicker: () => void
}) {
  const {
    activeSessionState,
    activeWorkspaceId,
    activeDataset,
    analyticsPayload,
    workspacePayload,
    ensureActiveSession,
    ensureSessionState,
    updateSessionTitleLocally,
    syncSessionSummaryWithState,
    revealSessionSummary,
    openDatasetPicker,
  } = options

  const chatError = ref<string | null>(null)
  const analyticsError = ref<string | null>(null)
  const exportMessage = ref<string | null>(null)
  const isSending = ref(false)
  const isRunningAnalysis = ref(false)
  // 메시지 입력 첨부 업로드 제거 후에도 기존 layout prop 계약을 유지하기 위한 상태입니다.
  const isSendingInteraction = ref(false)
  let activeChatStreamController: AbortController | null = null

  function isAbortError(error: unknown): boolean {
    return error instanceof DOMException && error.name === 'AbortError'
  }

  function cancelActiveChatStream() {
    activeChatStreamController?.abort()
    activeChatStreamController = null
  }

  function clearInteractionFeedback() {
    chatError.value = null
    analyticsError.value = null
    exportMessage.value = null
  }

  function applyStreamingAssistantState(
    assistantMessageIndex: number,
    sessionState: SessionRuntimeState,
    state: AgentStateStreamPayload,
  ) {
    const current = sessionState.messages[assistantMessageIndex]
    if (!current || current.role !== 'assistant') return

    sessionState.messages = sessionState.messages.map((entry, index) =>
      index === assistantMessageIndex
        ? {
            ...entry,
            usedTools: state.used_tools ?? entry.usedTools ?? [],
          }
        : entry,
    )
  }

  function createEmptyAnalyticsPayload(): AnalyticsPayload {
    return {
      summary_cards: [],
      charts: [],
      tables: [],
      insights: [],
      dataset_profile: null,
    }
  }

  /**
   * 스트리밍 완료 응답과 실시간 차트 이벤트가 같은 payload를 보낼 때 중복 추가를 막습니다.
   */
  function findExactChartIndex(
    charts: AnalyticsChartPayload[],
    chart: AnalyticsChartPayload,
  ): number {
    const signature = JSON.stringify(chart)
    return charts.findIndex((entry) => JSON.stringify(entry) === signature)
  }

  function applyStreamingChart(
    sessionState: SessionRuntimeState,
    payload: AgentChartStreamPayload,
  ) {
    const currentPayload = sessionState.analyticsPayload ?? createEmptyAnalyticsPayload()
    const charts = [...currentPayload.charts]
    if (findExactChartIndex(charts, payload.chart) < 0) {
      charts.push(payload.chart)
    }

    sessionState.analyticsPayload = {
      ...currentPayload,
      charts,
    }
  }

  function applyStreamingPlan(
    assistantMessageIndex: number,
    sessionState: SessionRuntimeState,
    payload: AgentPlanStreamPayload,
  ) {
    if (!payload.ok || !payload.data) return
    const current = sessionState.messages[assistantMessageIndex]
    if (!current || current.role !== 'assistant') return

    const nextPlan = payload.data.plan ?? []
    const nextExplanation = payload.data.explanation?.trim() || undefined
    sessionState.messages = sessionState.messages.map((entry, index) =>
      index === assistantMessageIndex
        ? {
            ...entry,
            plan: nextPlan,
            planExplanation: nextExplanation,
          }
        : entry,
    )
  }

  function applyStreamingSubMessage(
    assistantMessageIndex: number,
    sessionState: SessionRuntimeState,
    event: ChatSubMessageStreamEvent,
  ) {
    const current = sessionState.messages[assistantMessageIndex]
    if (!current || current.role !== 'assistant') return

    const sourceId = event.call_id?.trim() || event.item_id?.trim() || event.name?.trim() || event.type.trim()
    const subMessageId = `${event.type}:${sourceId}`
    const isDone = event.type.endsWith('.done')
    const nextChunk =
      typeof event.delta === 'string'
        ? event.delta
        : typeof event.arguments === 'string'
          ? event.arguments
          : typeof event.text === 'string'
            ? event.text
            : ''

    sessionState.messages = sessionState.messages.map((entry, index) => {
      if (index !== assistantMessageIndex || entry.role !== 'assistant') {
        return entry
      }

      const subMessages = [...(entry.subMessages ?? [])]
      const existingIndex = subMessages.findIndex((subMessage) => subMessage.id === subMessageId)
      const existing = existingIndex >= 0 ? subMessages[existingIndex] : null
      const nextText = isDone
        ? nextChunk || existing?.text || ''
        : `${existing?.text ?? ''}${nextChunk}`
      const nextSubMessage: ChatSubMessage = {
        id: subMessageId,
        type: event.type,
        text: nextText,
        isStreaming: !isDone,
      }

      if (existingIndex >= 0) {
        subMessages[existingIndex] = nextSubMessage
      } else {
        subMessages.push(nextSubMessage)
      }

      return {
        ...entry,
        subMessages,
      }
    })
  }

  function hasVisibleAssistantContent(message: ChatMessage | undefined): boolean {
    if (!message || message.role !== 'assistant') return false

    return Boolean(
      message.text.trim()
      || message.subMessages?.length
      || message.plan?.length
      || message.planExplanation?.trim()
      || message.attachmentPreview,
    )
  }

  /**
   * 완료 이벤트 본문은 최종 중복 출력이므로 표시하지 않고 스트리밍 본문만 유지합니다.
   */
  function resolveStreamedAssistantText(streamedText: string): string {
    return streamedText.trim()
  }

  async function handleSendMessage(message: string) {
    if (isSending.value || isRunningAnalysis.value) {
      return
    }

    clearInteractionFeedback()
    const sessionId = await ensureActiveSession()
    const sessionState = ensureSessionState(sessionId, DEFAULT_SESSION_TITLE)
    const userMessage = message.trim()
    if (!userMessage) return
    const shouldResolveSessionTitle = !sessionState.messages.some((entry) => entry.role === 'user')
    const userMessageEntry: ChatMessage = {
      role: 'user',
      text: userMessage,
    }
    sessionState.messages = [...sessionState.messages, userMessageEntry]
    isSending.value = true
    isSendingInteraction.value = false
    const assistantMessageIndex = sessionState.messages.length
    const chatStreamController = new AbortController()
    activeChatStreamController = chatStreamController

    sessionState.messages = [
      ...sessionState.messages,
      {
        role: 'assistant',
        author: 'AI 데이터 에이전트',
        text: '',
        subMessages: [],
      },
    ]

    try {
      const shouldSeparateNextAgentIteration: { current: boolean } = { current: false }
      if (shouldResolveSessionTitle) {
        void resolveSessionTitle(sessionId, userMessage)
          .then((response) => {
            const title = response.title.trim()
            if (!title) return
            updateSessionTitleLocally(sessionId, title)
            revealSessionSummary(sessionId, title)
          })
          .catch(() => undefined)
      }

      const response = await streamChatMessage(
        {
          sessionId,
          workspaceId: activeWorkspaceId?.value ?? null,
          message: userMessage,
          datasetIds: sessionState.datasets.map((dataset) => dataset.id),
        },
        {
          signal: chatStreamController.signal,
          onAgentIterationStart() {
            shouldSeparateNextAgentIteration.current = true
          },
          onDelta(delta) {
            const current = sessionState.messages[assistantMessageIndex]
            if (!current || current.role !== 'assistant') return
            sessionState.messages = sessionState.messages.map((entry, index) =>
              index === assistantMessageIndex
                ? {
                    ...entry,
                    text: `${
                      shouldSeparateNextAgentIteration.current && entry.text.trim()
                        ? `${entry.text}\n\n`
                        : entry.text
                    }${delta}`,
                  }
                : entry,
            )
            shouldSeparateNextAgentIteration.current = false
          },
          onSubMessage(event) {
            applyStreamingSubMessage(assistantMessageIndex, sessionState, event)
          },
          onState(state) {
            applyStreamingAssistantState(assistantMessageIndex, sessionState, state)
          },
          onChart(payload) {
            applyStreamingChart(sessionState, payload)
          },
          onPlan(payload) {
            applyStreamingPlan(assistantMessageIndex, sessionState, payload)
          },
        },
      )
      revealSessionSummary(sessionId, sessionState.title)

      const streamedAssistantText =
        sessionState.messages[assistantMessageIndex]?.role === 'assistant'
          ? sessionState.messages[assistantMessageIndex].text
          : ''
      const streamedAssistantPlan =
        sessionState.messages[assistantMessageIndex]?.role === 'assistant'
          ? sessionState.messages[assistantMessageIndex].plan ?? []
          : []
      const streamedAssistantPlanExplanation =
        sessionState.messages[assistantMessageIndex]?.role === 'assistant'
          ? sessionState.messages[assistantMessageIndex].planExplanation
          : undefined

      const assistantMessage = {
        role: 'assistant' as const,
        author: 'AI 데이터 에이전트',
        // 완료 이벤트의 assistant_message는 마지막 중복 출력이므로 화면 본문에 반영하지 않습니다.
        text: resolveStreamedAssistantText(streamedAssistantText),
        subMessages:
          sessionState.messages[assistantMessageIndex]?.role === 'assistant'
            ? sessionState.messages[assistantMessageIndex].subMessages ?? []
            : [],
        usedTools: response.used_tools,
        plan: response.plan.length ? response.plan : streamedAssistantPlan,
        planExplanation: response.plan_explanation?.trim() || streamedAssistantPlanExplanation,
      }

      sessionState.messages = sessionState.messages.map((entry, index) =>
        index === assistantMessageIndex ? assistantMessage : entry,
      )
      syncSessionSummaryWithState(sessionId)
    } catch (error) {
      if (chatStreamController.signal.aborted || isAbortError(error)) {
        if (!hasVisibleAssistantContent(sessionState.messages[assistantMessageIndex])) {
          sessionState.messages = sessionState.messages.filter(
            (_, index) => index !== assistantMessageIndex,
          )
        }
        syncSessionSummaryWithState(sessionId)
        return
      }

      chatError.value =
        error instanceof Error
          ? error.message
          : '메시지를 보내지 못했어요. ChatGPT 연결과 백엔드 상태를 확인해 주세요.'
      if (!hasVisibleAssistantContent(sessionState.messages[assistantMessageIndex])) {
        sessionState.messages = sessionState.messages.filter(
          (_, index) => index !== assistantMessageIndex,
        )
      }
      syncSessionSummaryWithState(sessionId)
    } finally {
      if (activeChatStreamController === chatStreamController) {
        activeChatStreamController = null
      }
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
      const analysisPrompt = `${primaryDataset.filename} 데이터셋을 대시보드용으로 요약하고 적합한 시각화와 인사이트를 만들어줘.`
      const streamedPlan: {
        plan: ChatMessage['plan']
        explanation?: string
      } = { plan: [] }
      sessionState.messages = [
        ...sessionState.messages,
        {
          role: 'user',
          text: analysisPrompt,
        },
      ]
      const response = await streamChatMessage(
        {
          sessionId,
          workspaceId: activeWorkspaceId?.value ?? null,
          datasetIds: [primaryDataset.id],
          // 백엔드의 남은 agent/tool 흐름을 통해 분석 패널 데이터를 생성합니다.
          message: analysisPrompt,
        },
        {
          onChart(payload) {
            applyStreamingChart(sessionState, payload)
          },
          onPlan(payload) {
            if (!payload.ok || !payload.data) return
            streamedPlan.plan = payload.data.plan ?? []
            streamedPlan.explanation = payload.data.explanation?.trim() || undefined
          },
        },
      )
      sessionState.messages = [
        ...sessionState.messages,
        {
          role: 'assistant',
          author: 'AI 데이터 에이전트',
          text:
            normalizeAssistantMessage(response.assistant_message)
            || '분석이 완료되어 실시간 분석 패널을 업데이트했어요.',
          usedTools: response.used_tools,
          plan: response.plan.length ? response.plan : streamedPlan.plan,
          planExplanation: response.plan_explanation?.trim() || streamedPlan.explanation,
        },
      ]
      syncSessionSummaryWithState(sessionId)
    } catch {
      analyticsError.value = '분석을 시작하지 못했어요. 잠시 후 다시 시도해 주세요.'
    } finally {
      isRunningAnalysis.value = false
    }
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
    chatError,
    analyticsError,
    exportMessage,
    isSending,
    isRunningAnalysis,
    isSendingInteraction,
    canExportReport,
    clearInteractionFeedback,
    handleSendMessage,
    cancelActiveChatStream,
    runAnalysis,
    handleInsightAction,
    exportAnalyticsReport,
    shareAnalyticsReport,
  }
}
