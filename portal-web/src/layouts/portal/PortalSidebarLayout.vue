<script setup lang="ts">
import PortalSidebar from './components/sidebar/PortalSidebar.vue'
import type {
  BackendConnectionStatus,
  OpenAiAuthStatus,
  PortalScreen,
  PortalSidebarData,
  SessionItem,
} from './types'

defineProps<{
  isCompactLayout: boolean
  isSidebarOpen: boolean
  shellSidebar: PortalSidebarData
  recentSessions: SessionItem[]
  workspaceSessions: Record<string, SessionItem[]>
  currentScreen: PortalScreen
  activeSessionId: string | null
  activeWorkspaceId: string | null
  connectionStatus: BackendConnectionStatus
  authStatus: OpenAiAuthStatus
  isConnecting: boolean
  isDisconnecting: boolean
}>()

const emit = defineEmits<{
  primaryAction: [screen: PortalScreen]
  createSession: []
  connectOpenAi: []
  disconnectOpenAi: []
  openHelp: []
  selectWorkspace: [workspaceId: string]
  selectSession: [sessionId: string]
  deleteSession: [sessionId: string]
  closeSidebarPanel: []
}>()
</script>

<template>
  <aside
    class="analysis-sidebar-shell"
    :class="{
      'analysis-sidebar-shell--compact': isCompactLayout,
      'analysis-sidebar-shell--open': isSidebarOpen,
    }"
  >
    <div v-if="isCompactLayout" class="mobile-panel-header">
      <strong>메뉴</strong>
      <button type="button" class="mobile-panel-close" @click="emit('closeSidebarPanel')">
        <span class="material-symbols-outlined">close</span>
      </button>
    </div>

    <PortalSidebar
      :sidebar="{ ...shellSidebar, recentSessions }"
      :workspace-sessions="workspaceSessions"
      :active-screen="currentScreen"
      :active-session-id="activeSessionId"
      :active-workspace-id="activeWorkspaceId"
      :connection-status="connectionStatus"
      :auth-status="authStatus"
      :is-connecting="isConnecting"
      :is-disconnecting="isDisconnecting"
      @primary-action="(screen) => emit('primaryAction', screen)"
      @create-session="emit('createSession')"
      @connect-open-ai="emit('connectOpenAi')"
      @disconnect-open-ai="emit('disconnectOpenAi')"
      @open-help="emit('openHelp')"
      @select-workspace="(workspaceId) => emit('selectWorkspace', workspaceId)"
      @select-session="(sessionId) => emit('selectSession', sessionId)"
      @delete-session="(sessionId) => emit('deleteSession', sessionId)"
    />
  </aside>
</template>

<style scoped>
.analysis-sidebar-shell {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.analysis-sidebar-shell :deep(.sidebar-card) {
  flex: 1 1 auto;
  height: auto;
}

.mobile-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 4px;
}

.mobile-panel-header strong {
  color: var(--color-primary-strong);
  font-size: 0.95rem;
}

.mobile-panel-close {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  color: var(--color-primary-strong);
  background: rgba(255, 255, 255, 0.92);
  font: inherit;
  cursor: pointer;
}

@media (max-width: 960px) {
  .analysis-sidebar-shell {
    position: fixed;
    top: 16px;
    left: 16px;
    bottom: 16px;
    z-index: 12;
    width: min(320px, calc(100vw - 32px));
    padding: 14px;
    border-radius: 24px;
    background: rgba(245, 247, 251, 0.96);
    box-shadow: 0 24px 56px rgba(15, 23, 42, 0.18);
    transform: translateX(calc(-100% - 24px));
    transition: transform 220ms ease;
  }

  .analysis-sidebar-shell--open {
    transform: translateX(0);
  }

  .analysis-sidebar-shell :deep(.sidebar-card) {
    height: auto;
  }
}
</style>
