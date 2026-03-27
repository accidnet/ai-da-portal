<script setup lang="ts">
import { computed } from 'vue'

import type { BackendConnectionStatus, HeaderData } from '../types'

const props = defineProps<{
  header: HeaderData
  connectionStatus: BackendConnectionStatus
}>()

const connectionLabel = computed(() => {
  if (props.connectionStatus === 'connected') {
    return 'Backend connected'
  }

  if (props.connectionStatus === 'offline') {
    return 'Backend offline'
  }

  return 'Checking backend'
})
</script>

<template>
  <header class="header-card">
    <label class="search-bar">
      <span class="material-symbols-outlined">search</span>
      <input type="text" :placeholder="header.searchPlaceholder" />
    </label>

    <div class="header-actions">
      <div class="connection-pill" :class="`connection-pill--${connectionStatus}`">
        <span class="connection-pill__dot"></span>
        <strong>{{ connectionLabel }}</strong>
      </div>

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
