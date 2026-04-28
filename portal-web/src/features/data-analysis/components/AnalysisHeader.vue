<script setup lang="ts">
import { computed } from 'vue'

import type { BackendConnectionStatus, HeaderData, OpenAiAuthStatus } from '../types'

const props = defineProps<{
  header: HeaderData
  searchQuery?: string
  connectionStatus: BackendConnectionStatus
  authStatus: OpenAiAuthStatus
  isConnecting: boolean
}>()

const emit = defineEmits<{
  connectOpenAi: []
  searchChange: [value: string]
}>()

const connectionLabel = computed(() => {
  if (props.connectionStatus === 'connected') {
    return '백엔드 연결됨'
  }

  if (props.connectionStatus === 'offline') {
    return '백엔드 연결 끊김'
  }

  return '백엔드 연결 확인 중'
})

const authLabel = computed(() => {
  if (props.authStatus.connected) {
    return props.authStatus.accountEmail
      ? `ChatGPT 연결됨 · ${props.authStatus.accountEmail}`
      : 'ChatGPT 연결됨'
  }

  if (props.authStatus.pending || props.isConnecting) {
    return 'ChatGPT 연결을 완료해 주세요'
  }

  return 'ChatGPT 연결'
})

const authButtonLabel = computed(() => {
  if (props.authStatus.connected) {
    return '연결 완료'
  }

  if (props.authStatus.pending || props.isConnecting) {
    return '연결 대기 중...'
  }

  return 'ChatGPT 연결'
})
</script>

<template>
  <header class="header-card">
    <label class="search-bar">
      <span class="material-symbols-outlined">search</span>
      <input
        type="text"
        :value="searchQuery ?? ''"
        :placeholder="header.searchPlaceholder"
        @input="emit('searchChange', ($event.target as HTMLInputElement).value)"
      />
    </label>

    <div class="header-actions">
      <div class="connection-pill" :class="`connection-pill--${connectionStatus}`">
        <span class="connection-pill__dot"></span>
        <strong>{{ connectionLabel }}</strong>
      </div>

      <div class="auth-pill" :class="`auth-pill--${authStatus.state}`">
        <span class="material-symbols-outlined">smart_toy</span>
        <strong>{{ authLabel }}</strong>
      </div>

      <button
        type="button"
        class="connect-button"
        :disabled="authStatus.connected || isConnecting"
        @click="emit('connectOpenAi')"
      >
        {{ authButtonLabel }}
      </button>

      <button v-for="action in header.actions" :key="action" type="button" class="action-button">
        <span class="material-symbols-outlined">{{ action }}</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.header-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid var(--color-border);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px);
}

.search-bar {
  position: relative;
  flex: 1;
}

.search-bar .material-symbols-outlined {
  position: absolute;
  left: 16px;
  top: 50%;
  color: var(--color-text-soft);
  transform: translateY(-50%);
}

.search-bar input {
  width: 100%;
  height: 52px;
  padding: 0 18px 0 50px;
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--color-text);
  background: var(--color-surface-muted);
  transition: border-color 180ms ease, box-shadow 180ms ease;
}

.search-bar input:focus {
  outline: none;
  border-color: rgba(24, 74, 140, 0.18);
  box-shadow: 0 0 0 4px rgba(24, 74, 140, 0.08);
}

.header-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.connection-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  min-height: 46px;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.connection-pill__dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: currentColor;
}

.connection-pill--checking {
  color: #8a6b2d;
  background: rgba(212, 177, 81, 0.12);
  border-color: rgba(212, 177, 81, 0.18);
}

.connection-pill--connected {
  color: #1d6b45;
  background: rgba(44, 139, 92, 0.12);
  border-color: rgba(44, 139, 92, 0.16);
}

.connection-pill--offline {
  color: #9b3b3b;
  background: rgba(184, 76, 76, 0.12);
  border-color: rgba(184, 76, 76, 0.16);
}

.action-button {
  border: 0;
  width: 46px;
  height: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
  cursor: pointer;
  transition: background-color 180ms ease, color 180ms ease;
}

.auth-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  min-height: 46px;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.auth-pill--disconnected {
  color: #8a4a24;
  background: rgba(205, 142, 79, 0.12);
  border-color: rgba(205, 142, 79, 0.18);
}

.auth-pill--pending {
  color: #8a6b2d;
  background: rgba(212, 177, 81, 0.12);
  border-color: rgba(212, 177, 81, 0.18);
}

.auth-pill--connected {
  color: #1d6b45;
  background: rgba(44, 139, 92, 0.12);
  border-color: rgba(44, 139, 92, 0.16);
}

.connect-button {
  border: 0;
  min-height: 46px;
  padding: 0 16px;
  border-radius: 999px;
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
  font-weight: 800;
  cursor: pointer;
}

.connect-button:disabled {
  opacity: 0.7;
  cursor: default;
}

.action-button:hover {
  color: var(--color-primary-strong);
  background: var(--color-surface-strong);
}

@media (max-width: 720px) {
  .header-card {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    justify-content: flex-end;
  }
}
</style>
