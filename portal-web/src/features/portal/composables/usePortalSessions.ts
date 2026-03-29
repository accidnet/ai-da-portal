import { ref, type Ref } from 'vue'

import { createSession, deleteSession, fetchSessionSnapshot, fetchSessions, updateSessionTitle } from '../../../shared/api/portalApi'
import type { PortalScreen, SessionItem } from '../types'
import { DEFAULT_SESSION_TITLE, LOCAL_SESSION_ID } from '../constants/portalPage'
import {
  createSessionState,
  createWelcomeMessages,
  mapSessionSummary,
  resolvePreferredDatasetId,
} from '../utils/portalPageHelpers'
import { mapSnapshotToSessionState, type SessionRuntimeState } from '../utils/sessionState'

export function usePortalSessions(options: {
  currentScreen: Ref<PortalScreen>
  onSessionDeleted?: (sessionId: string) => void | Promise<void>
}) {
  const { currentScreen, onSessionDeleted } = options

  const activeSessionId = ref<string | null>(null)
  const sessionSummaries = ref<SessionItem[]>([])
  const sessionStates = ref<Record<string, SessionRuntimeState>>({})
  const hydratedSessionIds = ref<Record<string, boolean>>({})
  const sessionHubError = ref<string | null>(null)
  const isSessionMutating = ref(false)

  let latestSnapshotRequestId = 0

  function ensureSessionState(sessionId: string, title: string): SessionRuntimeState {
    const existing = sessionStates.value[sessionId]
    if (existing) {
      existing.title = title
      return existing
    }

    const created = createSessionState(title)
    sessionStates.value[sessionId] = created
    return created
  }

  function updateSessionSummary(sessionId: string, patch: Partial<SessionItem>) {
    const current = sessionSummaries.value.find((session) => session.id === sessionId)
    if (!current) {
      return
    }

    Object.assign(current, patch)
    sessionSummaries.value = [...sessionSummaries.value]
  }

  function updateSessionTitleLocally(sessionId: string, title: string) {
    const normalizedTitle = title.trim()
    if (!normalizedTitle) {
      return
    }

    const state = ensureSessionState(sessionId, normalizedTitle)
    state.title = normalizedTitle
    updateSessionSummary(sessionId, {
      title: normalizedTitle,
      updatedAt: new Date().toISOString(),
    })
  }

  function syncSessionSummaryWithState(sessionId: string) {
    const state = sessionStates.value[sessionId]
    if (!state) {
      return
    }

    updateSessionSummary(sessionId, {
      title: state.title,
      messageCount: state.messages.length,
      datasetCount: state.datasets.length,
      preferredDatasetId: resolvePreferredDatasetId(state),
      lastDataset: state.datasets[0]
        ? {
            id: state.datasets[0].id,
            filename: state.datasets[0].filename,
          }
        : null,
      updatedAt: new Date().toISOString(),
    })
  }

  function buildSessionTitle(): string {
    return `분석 세션 ${sessionSummaries.value.length + 1}`
  }

  async function loadSessions() {
    try {
      const sessions = await fetchSessions()
      sessionSummaries.value = sessions.map(mapSessionSummary)
      if (sessionSummaries.value.length === 0) {
        const created = await createSession(DEFAULT_SESSION_TITLE)
        sessionSummaries.value = [mapSessionSummary(created)]
        activeSessionId.value = created.id
        ensureSessionState(created.id, created.title)
        hydratedSessionIds.value[created.id] = true
        return
      }

      for (const session of sessionSummaries.value) {
        if (session.id) {
          ensureSessionState(session.id, session.title)
        }
      }

      if (!activeSessionId.value || !sessionSummaries.value.some((session) => session.id === activeSessionId.value)) {
        activeSessionId.value = sessionSummaries.value[0]?.id ?? null
      }
      if (activeSessionId.value) {
        await hydrateSessionSnapshot(activeSessionId.value)
      }
      sessionHubError.value = null
    } catch {
      if (!activeSessionId.value) {
        activeSessionId.value = LOCAL_SESSION_ID
        sessionSummaries.value = [
          {
            id: LOCAL_SESSION_ID,
            title: DEFAULT_SESSION_TITLE,
            messageCount: 1,
            datasetCount: 0,
          },
        ]
        ensureSessionState(LOCAL_SESSION_ID, DEFAULT_SESSION_TITLE)
        hydratedSessionIds.value[LOCAL_SESSION_ID] = true
      }
      sessionHubError.value = '세션 목록을 서버에서 불러오지 못해 로컬 세션으로 전환했어요.'
    }
  }

  function getActiveSessionId(): string {
    if (activeSessionId.value) {
      return activeSessionId.value
    }

    activeSessionId.value = LOCAL_SESSION_ID
    ensureSessionState(LOCAL_SESSION_ID, DEFAULT_SESSION_TITLE)
    if (!sessionSummaries.value.some((session) => session.id === LOCAL_SESSION_ID)) {
      sessionSummaries.value = [{ id: LOCAL_SESSION_ID, title: DEFAULT_SESSION_TITLE }, ...sessionSummaries.value]
    }
    hydratedSessionIds.value[LOCAL_SESSION_ID] = true
    return LOCAL_SESSION_ID
  }

  async function ensureActiveSession() {
    const currentSessionId = getActiveSessionId()
    if (sessionStates.value[currentSessionId]) {
      return currentSessionId
    }

    const created = await createSession(DEFAULT_SESSION_TITLE)
    activeSessionId.value = created.id
    sessionSummaries.value = [mapSessionSummary(created), ...sessionSummaries.value]
    ensureSessionState(created.id, created.title)
    hydratedSessionIds.value[created.id] = true
    return created.id
  }

  async function hydrateSessionSnapshot(sessionId: string, force = false) {
    if (!sessionId || sessionId === LOCAL_SESSION_ID) {
      return
    }

    const summary = sessionSummaries.value.find((session) => session.id === sessionId)
    ensureSessionState(sessionId, summary?.title ?? DEFAULT_SESSION_TITLE)
    if (hydratedSessionIds.value[sessionId] && !force) {
      return
    }

    const requestId = ++latestSnapshotRequestId
    try {
      const snapshot = await fetchSessionSnapshot(sessionId)
      if (requestId !== latestSnapshotRequestId) {
        return
      }

      const state = mapSnapshotToSessionState(snapshot, createWelcomeMessages)
      sessionStates.value[sessionId] = state
      updateSessionSummary(sessionId, {
        title: state.title,
        messageCount: state.messages.length,
        datasetCount: state.datasets.length,
        lastDataset: state.datasets[0] ? { id: state.datasets[0].id, filename: state.datasets[0].filename } : null,
        updatedAt: snapshot.session.updated_at,
        createdAt: snapshot.session.created_at,
      })
      hydratedSessionIds.value[sessionId] = true
    } catch {
      hydratedSessionIds.value[sessionId] = true
    }
  }

  async function createAndSelectSession() {
    try {
      isSessionMutating.value = true
      const created = await createSession(buildSessionTitle())
      activeSessionId.value = created.id
      ensureSessionState(created.id, created.title)
      sessionSummaries.value = [mapSessionSummary(created), ...sessionSummaries.value]
      hydratedSessionIds.value[created.id] = true
      currentScreen.value = 'dashboard'
      sessionHubError.value = null
    } catch {
      sessionHubError.value = '새로운 분석 세션을 만들지 못했어요. 잠시 후 다시 시도해 주세요.'
    } finally {
      isSessionMutating.value = false
    }
  }

  async function selectSession(sessionId: string, targetScreen: PortalScreen = currentScreen.value) {
    activeSessionId.value = sessionId
    currentScreen.value = targetScreen
    const summary = sessionSummaries.value.find((session) => session.id === sessionId)
    ensureSessionState(sessionId, summary?.title ?? DEFAULT_SESSION_TITLE)
    await hydrateSessionSnapshot(sessionId, true)
  }

  async function handleRenameSession(payload: { sessionId: string; title: string }) {
    try {
      isSessionMutating.value = true
      const updated = await updateSessionTitle(payload.sessionId, payload.title)
      updateSessionSummary(payload.sessionId, {
        title: updated.title,
        updatedAt: updated.updated_at,
      })
      const state = sessionStates.value[payload.sessionId]
      if (state) {
        state.title = updated.title
      }
      sessionHubError.value = null
    } catch (error) {
      sessionHubError.value = error instanceof Error ? error.message : '세션 제목을 수정하지 못했어요.'
    } finally {
      isSessionMutating.value = false
    }
  }

  async function handleDeleteSession(sessionId: string) {
    try {
      isSessionMutating.value = true
      await deleteSession(sessionId)
      sessionSummaries.value = sessionSummaries.value.filter((session) => session.id !== sessionId)
      delete sessionStates.value[sessionId]
      delete hydratedSessionIds.value[sessionId]
      await onSessionDeleted?.(sessionId)
      if (activeSessionId.value === sessionId) {
        const nextSessionId = sessionSummaries.value[0]?.id ?? null
        activeSessionId.value = nextSessionId
        if (nextSessionId) {
          await selectSession(nextSessionId, 'dashboard')
        } else {
          await createAndSelectSession()
        }
      }
      sessionHubError.value = null
    } catch (error) {
      sessionHubError.value = error instanceof Error ? error.message : '세션을 삭제하지 못했어요.'
    } finally {
      isSessionMutating.value = false
    }
  }

  return {
    activeSessionId,
    sessionSummaries,
    sessionStates,
    hydratedSessionIds,
    sessionHubError,
    isSessionMutating,
    ensureSessionState,
    updateSessionSummary,
    updateSessionTitleLocally,
    syncSessionSummaryWithState,
    loadSessions,
    getActiveSessionId,
    ensureActiveSession,
    hydrateSessionSnapshot,
    createAndSelectSession,
    selectSession,
    handleRenameSession,
    handleDeleteSession,
  }
}
