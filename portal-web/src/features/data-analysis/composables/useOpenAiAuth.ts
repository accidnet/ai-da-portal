import { onUnmounted, ref } from 'vue'

import { authorizeOpenAi, fetchOpenAiAuthStatus, logoutOpenAi as requestOpenAiLogout } from '../../../shared/api/portalApi'
import type { OpenAiAuthStatus } from '../types'
import { OPENAI_AUTH_POPUP_SOURCE } from '../constants/analysisPage'
import { mapOpenAiAuthStatus } from '../utils/analysisPageHelpers'

interface OpenAiPopupMessage {
  source?: string
  status?: 'success' | 'error'
  error?: string
  account_email?: string
}

export function useOpenAiAuth() {
  const authStatus = ref<OpenAiAuthStatus>({
    state: 'disconnected',
    connected: false,
    pending: false,
    accountEmail: null,
    accountId: null,
    expiresAt: null,
    scopes: [],
  })
  const isConnecting = ref(false)
  const isDisconnecting = ref(false)
  const authError = ref<string | null>(null)

  let authPollTimer: number | null = null
  let authPopup: Window | null = null

  function syncAuthPolling() {
    if (authStatus.value.connected || (!authStatus.value.pending && !isConnecting.value)) {
      if (authPollTimer !== null) {
        window.clearInterval(authPollTimer)
        authPollTimer = null
      }
      return
    }

    if (authPollTimer === null) {
      authPollTimer = window.setInterval(async () => {
        await loadAuthStatus()
      }, 3000)
    }
  }

  async function loadAuthStatus() {
    try {
      const status = await fetchOpenAiAuthStatus()
      authStatus.value = mapOpenAiAuthStatus(status)
      isConnecting.value = status.pending
      if (status.connected) {
        authError.value = null
        authPopup = null
      } else if (!status.pending) {
        authPopup = null
      }
    } catch {
      authError.value = 'ChatGPT 연결 상태를 불러오지 못했어요.'
    } finally {
      syncAuthPolling()
    }
  }

  async function handleOpenAiAuthMessage(event: MessageEvent<OpenAiPopupMessage>) {
    if (!authPopup || event.source !== authPopup || event.data?.source !== OPENAI_AUTH_POPUP_SOURCE) {
      return
    }

    authPopup = null
    if (event.data.status === 'error') {
      isConnecting.value = false
      authError.value = event.data.error ?? 'ChatGPT 연결을 완료하지 못했어요.'
    }
    await loadAuthStatus()
  }

  function handleWindowFocus() {
    if (authStatus.value.pending || isConnecting.value) {
      void loadAuthStatus()
    }
  }

  function buildPopupFeatures() {
    const width = 560
    const height = 720
    const left = Math.max(window.screenX + Math.round((window.outerWidth - width) / 2), 0)
    const top = Math.max(window.screenY + Math.round((window.outerHeight - height) / 2), 0)
    return `popup=yes,width=${width},height=${height},left=${left},top=${top}`
  }

  async function connectOpenAi() {
    if (isDisconnecting.value) {
      return
    }

    if (authPopup && !authPopup.closed) {
      authPopup.focus()
      return
    }

    isConnecting.value = true
    authError.value = null
    try {
      const authorization = await authorizeOpenAi()
      const popup = window.open(authorization.authorization_url, OPENAI_AUTH_POPUP_SOURCE, buildPopupFeatures())
      if (!popup) {
        window.location.assign(authorization.authorization_url)
        return
      }
      authPopup = popup
      authStatus.value = {
        ...authStatus.value,
        state: 'pending',
        pending: true,
        connected: false,
      }
    } catch {
      isConnecting.value = false
      authError.value = 'ChatGPT 연결을 시작하지 못했어요.'
    } finally {
      syncAuthPolling()
    }
  }

  async function logoutOpenAi() {
    if (isConnecting.value || isDisconnecting.value) {
      return
    }

    isDisconnecting.value = true
    authError.value = null

    try {
      await requestOpenAiLogout()
      authStatus.value = {
        state: 'disconnected',
        connected: false,
        pending: false,
        accountEmail: null,
        accountId: null,
        expiresAt: null,
        scopes: [],
      }
      authPopup = null
      await loadAuthStatus()
    } catch {
      authError.value = '로그아웃하지 못했어요. 잠시 후 다시 시도해 주세요.'
    } finally {
      isDisconnecting.value = false
      syncAuthPolling()
    }
  }

  function bindAuthListeners() {
    window.addEventListener('message', handleOpenAiAuthMessage)
    window.addEventListener('focus', handleWindowFocus)
  }

  function unbindAuthListeners() {
    window.removeEventListener('message', handleOpenAiAuthMessage)
    window.removeEventListener('focus', handleWindowFocus)
    if (authPollTimer !== null) {
      window.clearInterval(authPollTimer)
    }
    authPopup = null
  }

  onUnmounted(() => {
    unbindAuthListeners()
  })

  return {
    authStatus,
    isConnecting,
    isDisconnecting,
    authError,
    bindAuthListeners,
    unbindAuthListeners,
    loadAuthStatus,
    connectOpenAi,
    logoutOpenAi,
  }
}
