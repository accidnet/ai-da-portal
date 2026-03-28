<script setup lang="ts">
import { computed } from 'vue'

import type { BackendConnectionStatus, OpenAiAuthStatus, PortalScreen, SidebarData } from '../types'

const props = defineProps<{
  sidebar: SidebarData
  activeSessionId?: string | null
  activeScreen: PortalScreen
  connectionStatus: BackendConnectionStatus
  authStatus: OpenAiAuthStatus
  isConnecting?: boolean
}>()

const emit = defineEmits<{
  selectSession: [sessionId: string]
  primaryAction: [screen: PortalScreen]
  createSession: []
  connectOpenAi: []
  openHelp: []
}>()

const statusItems = computed(() => {
  const backendLabel = props.connectionStatus === 'connected'
    ? '백엔드 연결됨'
    : props.connectionStatus === 'offline'
      ? '백엔드 연결 끊김'
      : '백엔드 확인 중'

  const authLabel = props.authStatus.connected
    ? 'ChatGPT 연결됨'
    : props.authStatus.pending || props.isConnecting
      ? 'ChatGPT 연결 대기 중'
      : 'ChatGPT 미연결'

  const summaryLabel = props.authStatus.connected && props.connectionStatus === 'connected'
    ? '연결 완료'
    : props.authStatus.pending || props.isConnecting
      ? '연결 진행 중'
      : '연결 상태 확인 필요'

  return [backendLabel, authLabel, summaryLabel]
})

const accountLabel = computed(() => props.authStatus.accountEmail ?? 'ChatGPT 연결 후 계정 정보가 표시됩니다.')
</script>

<template>
  <aside class="sidebar-card">
    <div class="brand-block">
      <div class="brand-icon">
        <span class="material-symbols-outlined">architecture</span>
      </div>
      <div>
        <h1>{{ sidebar.productName }}</h1>
        <p>{{ sidebar.productTagline }}</p>
      </div>
    </div>

    <nav class="nav-group" aria-label="주요 탐색">
      <button
        v-for="item in sidebar.primaryNav"
        :key="item.label"
        type="button"
        class="nav-item"
        :class="{ 'nav-item--active': item.screen === activeScreen && item.action !== 'create-session' }"
        @click="item.action === 'create-session' ? emit('createSession') : item.screen && emit('primaryAction', item.screen)"
      >
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="sessions-block">
      <p class="section-label">최근 세션</p>
      <button
        v-for="session in sidebar.recentSessions"
        :key="session.id ?? session.title"
        type="button"
        class="session-item"
        :class="{ 'session-item--active': session.id && session.id === activeSessionId }"
        @click="session.id && emit('selectSession', session.id)"
      >
        {{ session.title }}
      </button>
      <p v-if="sidebar.recentSessions.length === 0" class="empty-state">표시할 세션이 아직 없어요.</p>
    </div>

    <div class="connection-card">
      <p class="section-label section-label--inline">연결 상태</p>
      <div class="status-line">
        <span v-for="item in statusItems" :key="item" class="status-text">{{ item }}</span>
      </div>
      <p class="account-label">{{ accountLabel }}</p>

      <div class="connection-actions">
        <button type="button" class="connect-button" :disabled="authStatus.connected || isConnecting" @click="emit('connectOpenAi')">
          {{ authStatus.connected ? 'ChatGPT 연결됨' : isConnecting || authStatus.pending ? '연결 중...' : 'ChatGPT 연결' }}
        </button>
        <button type="button" class="ghost-button" @click="emit('openHelp')">도움말</button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-card {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: var(--color-shadow);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-icon {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: var(--color-primary);
}

.brand-block h1 {
  margin: 0;
  font: 800 1.15rem/1.1 var(--font-heading);
  color: var(--color-primary-strong);
}

.brand-block p {
  margin: 4px 0 0;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 700;
}

.nav-group,
.sessions-block,
.connection-card {
  display: grid;
  gap: 10px;
}

.nav-item,
.session-item,
.connect-button,
.ghost-button {
  border: 1px solid transparent;
  font: inherit;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  border-radius: 16px;
  text-align: left;
  color: var(--color-text-muted);
  background: transparent;
  cursor: pointer;
}

.nav-item:hover,
.session-item:hover,
.ghost-button:hover,
.connect-button:hover:not(:disabled) {
  border-color: rgba(24, 74, 140, 0.12);
  background: var(--color-surface-muted);
}

.nav-item--active,
.session-item--active {
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
  font-weight: 700;
}

.section-label {
  margin: 0;
  padding: 0 14px;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.7rem;
  font-weight: 700;
}

.section-label--inline {
  padding: 0;
}

.session-item {
  width: 100%;
  appearance: none;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 12px 14px;
  border-radius: 14px;
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.48);
  cursor: pointer;
}

.empty-state,
.account-label {
  margin: 0;
  color: var(--color-text-soft);
  font-size: 0.82rem;
  line-height: 1.5;
}

.connection-card {
  margin-top: auto;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.84);
}

.status-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.status-text {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  line-height: 1.5;
}

.status-text:not(:last-child)::after {
  content: '|';
  margin-left: 6px;
  color: rgba(22, 32, 43, 0.28);
}

.connection-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.connect-button,
.ghost-button {
  min-height: 42px;
  padding: 0 14px;
  border-radius: 14px;
  cursor: pointer;
}

.connect-button {
  color: #fff;
  background: var(--color-primary);
}

.ghost-button {
  color: var(--color-text);
  background: var(--color-surface-muted);
}

.connect-button:disabled {
  opacity: 0.7;
  cursor: default;
}

@media (max-width: 960px) {
  .sidebar-card {
    height: auto;
  }
}
</style>
