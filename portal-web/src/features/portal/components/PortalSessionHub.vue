<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { SessionItem } from '../types'

const props = defineProps<{
  sessions: SessionItem[]
  activeSessionId?: string | null
  searchQuery: string
  isBusy?: boolean
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  searchChange: [value: string]
  openSession: [sessionId: string]
  renameSession: [payload: { sessionId: string; title: string }]
  deleteSession: [sessionId: string]
  createSession: []
}>()

const editingSessionId = ref<string | null>(null)
const titleDraft = ref('')

const filteredSessions = computed(() => {
  const keyword = props.searchQuery.trim().toLowerCase()
  if (!keyword) {
    return props.sessions
  }

  return props.sessions.filter((session) => {
    const haystacks = [
      session.title,
      session.lastDataset?.filename ?? '',
      session.id ?? '',
    ]
    return haystacks.some((value) => value.toLowerCase().includes(keyword))
  })
})

watch(() => props.activeSessionId, () => {
  editingSessionId.value = null
  titleDraft.value = ''
})

function formatRelative(value?: string): string {
  if (!value) {
    return '시각 정보 없음'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('ko-KR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function startEdit(session: SessionItem) {
  if (!session.id) {
    return
  }

  editingSessionId.value = session.id
  titleDraft.value = session.title
}

function submitEdit(sessionId?: string) {
  if (!sessionId) {
    return
  }

  const title = titleDraft.value.trim()
  if (!title) {
    return
  }

  emit('renameSession', { sessionId, title })
  editingSessionId.value = null
}
</script>

<template>
  <section class="hub-shell">
    <header class="hub-header panel-card">
      <div>
        <p>기록</p>
        <h2>세션 허브</h2>
        <span>최근 분석 세션을 탐색하고 현재 작업 세션을 바로 전환할 수 있어요.</span>
      </div>

      <button type="button" class="primary-button" :disabled="isBusy" @click="emit('createSession')">
        <span class="material-symbols-outlined">add</span>
        새 세션
      </button>
    </header>

    <section class="panel-card hub-toolbar">
      <label class="hub-search">
        <span class="material-symbols-outlined">search</span>
        <input
          :value="searchQuery"
          type="search"
          placeholder="세션 제목, 데이터셋, ID 검색"
          @input="emit('searchChange', ($event.target as HTMLInputElement).value)"
        >
      </label>
      <p>{{ filteredSessions.length }}개 세션</p>
    </section>

    <p v-if="errorMessage" class="hub-error">{{ errorMessage }}</p>

    <div class="session-list">
      <article
        v-for="session in filteredSessions"
        :key="session.id ?? session.title"
        class="panel-card session-card"
        :class="{ 'session-card--active': session.id === activeSessionId }"
      >
        <div class="session-card__top">
          <div class="session-card__title">
            <p>{{ session.id === activeSessionId ? '활성 세션' : '보관 세션' }}</p>

            <div v-if="editingSessionId === session.id" class="title-editor">
              <input
                v-model="titleDraft"
                type="text"
                maxlength="120"
                @keydown.enter.prevent="submitEdit(session.id)"
                @keydown.esc="editingSessionId = null"
              >
              <button type="button" @click="submitEdit(session.id)">저장</button>
            </div>
            <h3 v-else>{{ session.title }}</h3>
          </div>

          <div class="session-card__actions">
            <button type="button" :disabled="isBusy || !session.id" @click="session.id && emit('openSession', session.id)">열기</button>
            <button type="button" :disabled="isBusy" @click="startEdit(session)">제목 수정</button>
            <button type="button" class="danger-button" :disabled="isBusy || !session.id" @click="session.id && emit('deleteSession', session.id)">삭제</button>
          </div>
        </div>

        <div class="session-meta-grid">
          <article>
            <p>메시지</p>
            <strong>{{ session.messageCount ?? 0 }}</strong>
          </article>
          <article>
            <p>데이터셋</p>
            <strong>{{ session.datasetCount ?? 0 }}</strong>
          </article>
          <article>
            <p>최근 데이터셋</p>
            <strong>{{ session.lastDataset?.filename ?? '없음' }}</strong>
          </article>
          <article>
            <p>업데이트</p>
            <strong>{{ formatRelative(session.updatedAt) }}</strong>
          </article>
        </div>
      </article>

      <section v-if="filteredSessions.length === 0" class="panel-card empty-card">
        <span class="material-symbols-outlined">history</span>
        <strong>조건에 맞는 세션이 없어요</strong>
        <p>검색어를 바꾸거나 새 세션을 만들어 분석을 시작해 보세요.</p>
      </section>
    </div>
  </section>
</template>

<style scoped>
.hub-shell,
.session-list {
  min-height: 0;
  display: grid;
  gap: 16px;
}

.panel-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: var(--color-shadow);
}

.hub-header,
.hub-toolbar,
.session-card,
.empty-card {
  padding: 20px 22px;
}

.hub-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.hub-header p,
.session-card p,
.session-meta-grid p {
  margin: 0;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 800;
}

.hub-header h2,
.session-card h3 {
  margin: 8px 0 6px;
  font-family: var(--font-heading);
}

.hub-header span,
.hub-toolbar p,
.empty-card p {
  color: var(--color-text-muted);
}

.primary-button,
.session-card__actions button,
.title-editor button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 11px 14px;
  border-radius: 14px;
  background: var(--color-surface-muted);
  color: var(--color-text);
  cursor: pointer;
}

.primary-button {
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
}

.hub-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.hub-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 16px;
  background: var(--color-surface-muted);
}

.hub-search input,
.title-editor input {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--color-text);
}

.hub-search input:focus,
.title-editor input:focus {
  outline: none;
}

.session-card {
  display: grid;
  gap: 16px;
}

.session-card--active {
  border-color: rgba(24, 74, 140, 0.22);
  background: linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(226, 238, 252, 0.88) 100%);
}

.session-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.session-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.session-meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.session-meta-grid article {
  padding: 14px;
  border-radius: 18px;
  background: var(--color-surface-muted);
}

.session-meta-grid strong {
  display: block;
  margin-top: 8px;
  font-size: 0.95rem;
}

.title-editor {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  padding: 8px;
  border-radius: 14px;
  background: var(--color-surface-muted);
}

.danger-button {
  color: #9b3b3b !important;
}

.hub-error {
  margin: 0;
  color: #9b3b3b;
  font-size: 0.86rem;
}

.empty-card {
  display: grid;
  justify-items: center;
  gap: 8px;
  text-align: center;
}

.empty-card strong {
  font-size: 1rem;
}

@media (max-width: 960px) {
  .hub-header,
  .hub-toolbar,
  .session-card__top {
    grid-template-columns: minmax(0, 1fr);
    display: grid;
  }

  .session-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .session-meta-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .title-editor {
    flex-direction: column;
  }
}
</style>
