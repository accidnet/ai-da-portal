<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import WorkspaceCreateDialog from './WorkspaceCreateDialog.vue'
import WorkspaceFileExplorerDialog from './WorkspaceFileExplorerDialog.vue'
import {
  createWorkspace as createWorkspaceRequest,
  deleteWorkspace as deleteWorkspaceRequest,
  fetchWorkspaces,
  updateWorkspace as updateWorkspaceRequest,
} from '@/features/data-analysis/api/analysisApi'
import type {
  BackendConnectionStatus,
  OpenAiAuthStatus,
  PortalScreen,
  PortalSidebarData,
  SessionItem,
  WorkspaceItem,
} from '../../types'

const props = defineProps<{
  sidebar: PortalSidebarData
  workspaceSessions: Record<string, SessionItem[]>
  activeSessionId?: string | null
  activeWorkspaceId?: string | null
  activeScreen: PortalScreen
  connectionStatus: BackendConnectionStatus
  authStatus: OpenAiAuthStatus
  isConnecting?: boolean
  isDisconnecting?: boolean
}>()

const emit = defineEmits<{
  selectSession: [sessionId: string]
  primaryAction: [screen: PortalScreen]
  selectWorkspace: [workspaceId: string]
  createSession: []
  deleteSession: [sessionId: string]
  connectOpenAi: []
  disconnectOpenAi: []
  openHelp: []
}>()
const accountLabel = computed(() => props.authStatus.accountEmail ?? '로그인')
const connectButtonLabel = computed(() => {
  if (props.isConnecting || props.authStatus.pending) return '연결 중...'
  if (props.isDisconnecting) return '로그아웃 중...'
  return props.authStatus.connected ? '로그아웃' : '로그인'
})
const workspaceItems = ref<WorkspaceItem[]>([])
const isWorkspaceExpanded = ref(false)
const isWorkspaceDialogOpen = ref(false)
const workspaceDialogMode = ref<'create' | 'edit'>('create')
const editingWorkspace = ref<WorkspaceItem | null>(null)
const exploringWorkspace = ref<WorkspaceItem | null>(null)
const openWorkspaceMenuId = ref<string | null>(null)
const workspaceError = ref<string | null>(null)
const isWorkspaceMutating = ref(false)
const visibleWorkspaceItems = computed(() => (
  isWorkspaceExpanded.value ? workspaceItems.value : workspaceItems.value.slice(0, 5)
))
const hasMoreWorkspaces = computed(() => workspaceItems.value.length > 5)
const workspaceMoreLabel = computed(() => (isWorkspaceExpanded.value ? '접기' : '... 더보기'))

/** 워크스페이스에 소속된 세션 목록을 반환합니다. */
function sessionsForWorkspace(workspaceId: string): SessionItem[] {
  return props.workspaceSessions[workspaceId] ?? []
}

/** 워크스페이스 생성 다이얼로그를 엽니다. */
function openWorkspaceDialog() {
  workspaceDialogMode.value = 'create'
  editingWorkspace.value = null
  openWorkspaceMenuId.value = null
  isWorkspaceDialogOpen.value = true
}

/** 워크스페이스 생성 다이얼로그를 닫습니다. */
function closeWorkspaceDialog() {
  isWorkspaceDialogOpen.value = false
  editingWorkspace.value = null
}

/** 워크스페이스 생성 또는 이름 변경을 서버에 반영합니다. */
async function saveWorkspace(workspaceName: string) {
  if (isWorkspaceMutating.value) return

  isWorkspaceMutating.value = true
  workspaceError.value = null
  try {
    if (workspaceDialogMode.value === 'edit' && editingWorkspace.value) {
      const updated = await updateWorkspaceRequest(editingWorkspace.value.id, workspaceName)
      workspaceItems.value = workspaceItems.value.map((workspace) => (
        workspace.id === updated.id
          ? {
              id: updated.id,
              name: updated.name,
              createdAt: updated.created_at,
              updatedAt: updated.updated_at,
            }
          : workspace
      ))
      closeWorkspaceDialog()
      return
    }

    const created = await createWorkspaceRequest(workspaceName)
    workspaceItems.value = [
      {
        id: created.id,
        name: created.name,
        createdAt: created.created_at,
        updatedAt: created.updated_at,
      },
      ...workspaceItems.value,
    ]
    emit('selectWorkspace', created.id)
    closeWorkspaceDialog()
  } catch {
    workspaceError.value = workspaceDialogMode.value === 'edit'
      ? '워크스페이스 이름을 변경하지 못했어요.'
      : '워크스페이스를 생성하지 못했어요.'
  } finally {
    isWorkspaceMutating.value = false
  }
}

/** 워크스페이스 행의 액션 메뉴를 열거나 닫습니다. */
function toggleWorkspaceMenu(workspaceId: string) {
  openWorkspaceMenuId.value = openWorkspaceMenuId.value === workspaceId ? null : workspaceId
}

/** 이름 변경 다이얼로그를 현재 워크스페이스 정보로 엽니다. */
function openWorkspaceRenameDialog(workspace: WorkspaceItem) {
  workspaceDialogMode.value = 'edit'
  editingWorkspace.value = workspace
  openWorkspaceMenuId.value = null
  isWorkspaceDialogOpen.value = true
}

/** 선택한 워크스페이스의 read-only 파일 탐색 다이얼로그를 엽니다. */
function openWorkspaceFileExplorer(workspace: WorkspaceItem) {
  exploringWorkspace.value = workspace
  openWorkspaceMenuId.value = null
}

/** 파일 탐색 다이얼로그를 닫고 선택 상태를 정리합니다. */
function closeWorkspaceFileExplorer() {
  exploringWorkspace.value = null
}

/** 워크스페이스를 서버와 화면 목록에서 삭제합니다. */
async function deleteWorkspace(workspaceId: string) {
  if (isWorkspaceMutating.value) return

  isWorkspaceMutating.value = true
  workspaceError.value = null
  openWorkspaceMenuId.value = null
  try {
    await deleteWorkspaceRequest(workspaceId)
    workspaceItems.value = workspaceItems.value.filter((workspace) => workspace.id !== workspaceId)
  } catch {
    workspaceError.value = '워크스페이스를 삭제하지 못했어요.'
  } finally {
    isWorkspaceMutating.value = false
  }
}

function handleConnectButtonClick() {
  if (props.authStatus.connected) {
    emit('disconnectOpenAi')
    return
  }

  emit('connectOpenAi')
}

/** 저장된 워크스페이스 목록을 사이드바에 복원합니다. */
async function loadWorkspaces() {
  try {
    const workspaces = await fetchWorkspaces()
    workspaceItems.value = workspaces.map((workspace) => ({
      id: workspace.id,
      name: workspace.name,
      createdAt: workspace.created_at,
      updatedAt: workspace.updated_at,
    }))
    workspaceError.value = null
  } catch {
    workspaceError.value = '워크스페이스 목록을 불러오지 못했어요.'
  }
}

onMounted(() => {
  void loadWorkspaces()
})
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
        :class="{
          'nav-item--active': item.screen === activeScreen && item.action !== 'create-session',
          'nav-item--cta': item.action === 'create-session',
        }"
        @click="item.action === 'create-session' ? emit('createSession') : item.screen && emit('primaryAction', item.screen)"
      >
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <section class="workspace-block">
      <h2 class="section-title">워크스페이스</h2>
      <button type="button" class="workspace-create-button" @click="openWorkspaceDialog">
        <span class="workspace-icon workspace-icon--create material-symbols-outlined">create_new_folder</span>
        <span>워크스페이스 만들기</span>
      </button>
      <div class="workspace-list">
        <div
          v-for="workspace in visibleWorkspaceItems"
          :key="workspace.id"
          class="workspace-item"
          :class="{ 'workspace-item--active': workspace.id === activeWorkspaceId }"
        >
          <button type="button" class="workspace-item__main" @click="emit('selectWorkspace', workspace.id)">
            <span class="workspace-icon material-symbols-outlined">folder</span>
            <span>{{ workspace.name }}</span>
          </button>
          <div class="workspace-item__actions">
            <button
              type="button"
              class="workspace-menu-button"
              :aria-label="`${workspace.name} 워크스페이스 메뉴`"
              @click.stop="toggleWorkspaceMenu(workspace.id)"
            >
              <span class="material-symbols-outlined">more_horiz</span>
            </button>
            <div v-if="openWorkspaceMenuId === workspace.id" class="workspace-menu">
              <button type="button" @click="openWorkspaceRenameDialog(workspace)">이름 변경</button>
              <button type="button" @click="openWorkspaceFileExplorer(workspace)">파일 탐색</button>
              <button type="button" class="workspace-menu__danger" @click="deleteWorkspace(workspace.id)">삭제</button>
            </div>
          </div>
          <div v-if="workspace.id === activeWorkspaceId" class="workspace-session-list">
            <div
              v-for="session in sessionsForWorkspace(workspace.id)"
              :key="session.id ?? session.title"
              class="workspace-session"
              :class="{ 'workspace-session--active': session.id && session.id === activeSessionId }"
            >
              <button
                type="button"
                class="workspace-session__select"
                :title="session.title"
                @click="session.id && emit('selectSession', session.id)"
              >
                <span>{{ session.title }}</span>
              </button>
              <button
                v-if="session.id"
                type="button"
                class="workspace-session__delete"
                :aria-label="`${session.title} 세션 삭제`"
                :title="`${session.title} 세션 삭제`"
                @click.stop="emit('deleteSession', session.id)"
              >
                <span class="material-symbols-outlined">close</span>
              </button>
            </div>
            <p v-if="sessionsForWorkspace(workspace.id).length === 0" class="workspace-session-empty">
              이 워크스페이스의 세션이 아직 없어요.
            </p>
          </div>
        </div>
      </div>
      <button v-if="hasMoreWorkspaces" type="button" class="more-button" @click="isWorkspaceExpanded = !isWorkspaceExpanded">
        {{ workspaceMoreLabel }}
      </button>
      <p v-if="workspaceError" class="workspace-error">{{ workspaceError }}</p>
    </section>

    <div class="sessions-block">
      <h2 class="section-title">최근</h2>
      <div class="sessions-list">
        <div
          v-for="session in sidebar.recentSessions"
          :key="session.id ?? session.title"
          class="session-item"
          :class="{ 'session-item--active': session.id && session.id === activeSessionId }"
        >
          <button
            type="button"
            class="session-item__select"
            :title="session.title"
            @click="session.id && emit('selectSession', session.id)"
          >
            <span>{{ session.title }}</span>
          </button>
          <button
            v-if="session.id"
            type="button"
            class="session-item__delete"
            :aria-label="`${session.title} 세션 삭제`"
            :title="`${session.title} 세션 삭제`"
            @click.stop="emit('deleteSession', session.id)"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <p v-if="sidebar.recentSessions.length === 0" class="empty-state">표시할 세션이 아직 없어요.</p>
      </div>
    </div>

    <button
      type="button"
      class="account-card"
      :disabled="isConnecting || isDisconnecting"
      :title="connectButtonLabel"
      @click="handleConnectButtonClick"
    >
      <span class="account-avatar" aria-hidden="true"></span>
      <span>{{ accountLabel }}</span>
    </button>
  </aside>

  <WorkspaceCreateDialog
    :open="isWorkspaceDialogOpen"
    :mode="workspaceDialogMode"
    :initial-name="editingWorkspace?.name"
    :is-submitting="isWorkspaceMutating"
    @close="closeWorkspaceDialog"
    @create="saveWorkspace"
  />
  <WorkspaceFileExplorerDialog
    :open="exploringWorkspace !== null"
    :workspace="exploringWorkspace"
    @close="closeWorkspaceFileExplorer"
  />
</template>

<style scoped>
.sidebar-card {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 20px 16px 14px;
  border: 0;
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), #fff),
    var(--color-surface);
  box-shadow: 0 20px 60px rgba(37, 68, 112, 0.12);
  overflow: hidden;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px 2px;
}

.brand-icon {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #1f5ebc, var(--color-primary));
  box-shadow: 0 8px 18px rgba(43, 94, 162, 0.24);
}

.brand-icon .material-symbols-outlined {
  display: none;
}

.brand-icon::before {
  content: 'A';
  font-size: 12px;
  font-weight: 800;
}

.brand-block h1 {
  margin: 0;
  color: #18395f;
  font-size: 15.5px;
  font-weight: 800;
  line-height: 1.15;
}

.brand-block p {
  margin: 2px 0 0;
  color: #546579;
  font-size: 10px;
  font-weight: 600;
}

.nav-group,
.workspace-block,
.sessions-block,
.account-card {
  display: grid;
  gap: 12px;
}

.nav-group,
.workspace-block,
.account-card {
  flex: 0 0 auto;
}

.nav-group {
  padding: 0 6px;
}

.sessions-block {
  min-height: 0;
  flex: 1 1 auto;
  grid-template-rows: auto minmax(0, 1fr);
}

.sessions-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 8px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 6px;
}

.nav-item,
.session-item__select,
.session-item__delete,
.account-card {
  border: 1px solid transparent;
  font: inherit;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 46px;
  padding: 0 16px;
  border-radius: 8px;
  text-align: left;
  color: #7d8b9f;
  background: transparent;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.nav-item:hover,
.session-item:hover,
.workspace-create-button:hover,
.workspace-item:hover .workspace-item__main,
.account-card:hover:not(:disabled),
.nav-item:focus-visible,
.session-item:focus-within,
.workspace-create-button:focus-visible,
.workspace-item:focus-within .workspace-item__main,
.account-card:focus-visible {
  border-color: rgba(24, 74, 140, 0.12);
  background: #f3f7fc;
  outline: none;
}

.nav-item--cta {
  color: #fff;
  background: #2d6dcc;
  box-shadow: 0 10px 25px rgba(45, 109, 204, 0.24);
}

.nav-item--cta:hover,
.nav-item--cta:focus-visible {
  color: #fff;
  border-color: rgba(24, 74, 140, 0.08);
  background: #1f5ebc;
  box-shadow: 0 14px 30px rgba(45, 109, 204, 0.34);
}

.nav-item--active,
.session-item--active,
.workspace-item--active .workspace-item__main,
.workspace-session--active {
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
  font-weight: 700;
}

.section-title {
  margin: 0;
  color: #000;
  font-size: 16px;
  font-weight: 800;
}

.workspace-block,
.sessions-block {
  padding: 0 8px;
}

.workspace-list {
  display: grid;
  gap: 8px;
}

.workspace-create-button,
.workspace-item__main {
  min-width: 0;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  border: 1px solid transparent;
  color: #000;
  background: transparent;
  font: inherit;
  font-size: 15px;
  text-align: left;
  cursor: pointer;
}

.workspace-create-button {
  min-height: 36px;
  border-radius: 8px;
  color: var(--color-primary-strong);
  font-weight: 700;
}

.workspace-item {
  position: relative;
  min-height: 32px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px;
  align-items: center;
  gap: 4px;
  color: #000;
}

.workspace-item__main {
  min-height: 32px;
  padding: 0;
  border-radius: 8px;
}

.workspace-item__main span:last-child,
.workspace-create-button span:last-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-icon {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #728196;
  background: #e7ebf0;
  font-size: 16px;
}

.workspace-icon--create {
  color: var(--color-primary);
  background: rgba(43, 94, 162, 0.1);
}

.workspace-item__actions {
  position: relative;
  display: flex;
  justify-content: flex-end;
}

.workspace-menu-button {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 8px;
  color: #526174;
  background: transparent;
  cursor: pointer;
}

.workspace-menu-button:hover,
.workspace-menu-button:focus-visible {
  color: var(--color-primary-strong);
  background: #eef3f9;
  outline: none;
}

.workspace-menu-button .material-symbols-outlined {
  font-size: 19px;
}

.workspace-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 6;
  min-width: 116px;
  display: grid;
  gap: 4px;
  padding: 6px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.12);
}

.workspace-menu button {
  min-height: 30px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  color: #253044;
  background: transparent;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}

.workspace-menu button:hover,
.workspace-menu button:focus-visible {
  background: #f3f7fc;
  outline: none;
}

.workspace-menu .workspace-menu__danger {
  color: #a23a3a;
}

.workspace-menu .workspace-menu__danger:hover,
.workspace-menu .workspace-menu__danger:focus-visible {
  background: rgba(162, 58, 58, 0.1);
}

.more-button {
  justify-self: start;
  min-height: 30px;
  padding: 0 2px;
  border: 0;
  color: #1f2937;
  background: transparent;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.workspace-error {
  margin: 0;
  color: #a23a3a;
  font-size: 12px;
  line-height: 1.45;
}

.session-item {
  width: 100%;
  min-height: 32px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  padding: 0 0 0 2px;
  border-radius: 8px;
  color: #000;
  background: transparent;
  border: 1px solid transparent;
  font-size: 15px;
}

.workspace-session-list {
  grid-column: 1 / -1;
  display: grid;
  gap: 4px;
  margin: 2px 0 4px 40px;
}

.workspace-session {
  min-height: 30px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  gap: 4px;
  border-radius: 8px;
  color: #334155;
  font-size: 13px;
}

.session-item__select,
.session-item__delete,
.workspace-session__select,
.workspace-session__delete {
  appearance: none;
  min-width: 0;
  padding: 0;
  color: inherit;
  background: transparent;
  cursor: pointer;
}

.session-item__select,
.workspace-session__select {
  height: 32px;
  display: flex;
  align-items: center;
  text-align: left;
}

.workspace-session__select {
  height: 30px;
}

.session-item__select span,
.workspace-session__select span {
  min-width: 0;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item__delete,
.workspace-session__delete {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #000;
  opacity: 0.9;
}

.workspace-session__delete {
  width: 28px;
  height: 28px;
}

.session-item__delete:hover,
.session-item__delete:focus-visible,
.workspace-session__delete:hover,
.workspace-session__delete:focus-visible {
  color: #a23a3a;
  background: rgba(162, 58, 58, 0.1);
  outline: none;
  opacity: 1;
}

.session-item__delete .material-symbols-outlined,
.workspace-session__delete .material-symbols-outlined {
  font-size: 1rem;
}

.empty-state,
.workspace-session-empty,
.account-label {
  margin: 0;
  color: var(--color-text-soft);
  font-size: 0.82rem;
  line-height: 1.5;
}

.account-card {
  margin-top: auto;
  min-height: 53px;
  grid-template-columns: 24px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border: 1px solid #e7e7e7;
  border-radius: 8px;
  color: #000;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 150ms ease, background-color 150ms ease, box-shadow 150ms ease;
}

.account-avatar {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: linear-gradient(135deg, #d6dce4, #c6cdd7);
}

.account-card span:last-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-card:disabled {
  opacity: 0.7;
  cursor: default;
}

@media (max-width: 960px) {
  .sidebar-card {
    height: auto;
  }
}
</style>
