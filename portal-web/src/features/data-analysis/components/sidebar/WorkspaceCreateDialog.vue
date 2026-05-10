<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  close: []
  create: [name: string]
}>()

const workspaceNameInput = ref('')
const trimmedWorkspaceName = computed(() => workspaceNameInput.value.trim())

watch(
  () => props.open,
  (open) => {
    if (open) {
      workspaceNameInput.value = ''
    }
  },
)

/** 입력한 워크스페이스 명을 상위 컴포넌트로 전달합니다. */
function submitWorkspace() {
  if (!trimmedWorkspaceName.value || props.isSubmitting) return

  emit('create', trimmedWorkspaceName.value)
}
</script>

<template>
  <div v-if="open" class="workspace-dialog-backdrop" role="presentation" @click.self="emit('close')">
    <form class="workspace-dialog" role="dialog" aria-modal="true" aria-labelledby="workspace-dialog-title" @submit.prevent="submitWorkspace">
      <header class="workspace-dialog__header">
        <div>
          <h2 id="workspace-dialog-title">워크스페이스 만들기</h2>
          <p>새 워크스페이스 이름을 입력하세요.</p>
        </div>
        <button type="button" class="workspace-dialog__close" aria-label="닫기" :disabled="isSubmitting" @click="emit('close')">
          <span class="material-symbols-outlined">close</span>
        </button>
      </header>

      <label class="workspace-dialog__field">
        <span>워크스페이스 명</span>
        <input
          v-model="workspaceNameInput"
          type="text"
          maxlength="40"
          placeholder="예: 고객 분석 워크스페이스"
          :disabled="isSubmitting"
          autofocus
        />
      </label>

      <footer class="workspace-dialog__actions">
        <button
          type="button"
          class="workspace-dialog__button workspace-dialog__button--ghost"
          :disabled="isSubmitting"
          @click="emit('close')"
        >
          취소
        </button>
        <button
          type="submit"
          class="workspace-dialog__button workspace-dialog__button--primary"
          :disabled="!trimmedWorkspaceName || isSubmitting"
        >
          {{ isSubmitting ? '생성 중...' : '생성' }}
        </button>
      </footer>
    </form>
  </div>
</template>

<style scoped>
.workspace-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.32);
}

.workspace-dialog {
  width: min(420px, 100%);
  display: grid;
  gap: 22px;
  padding: 24px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.22);
}

.workspace-dialog__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.workspace-dialog__header h2,
.workspace-dialog__header p {
  margin: 0;
}

.workspace-dialog__header h2 {
  color: #111827;
  font-size: 18px;
  font-weight: 800;
}

.workspace-dialog__header p {
  margin-top: 6px;
  color: #66758a;
  font-size: 13px;
  line-height: 1.45;
}

.workspace-dialog__close {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  color: #4b5563;
  background: #fff;
  cursor: pointer;
}

.workspace-dialog__close:hover,
.workspace-dialog__close:focus-visible {
  color: var(--color-primary-strong);
  background: #f3f7fc;
  outline: none;
}

.workspace-dialog__close .material-symbols-outlined {
  font-size: 20px;
}

.workspace-dialog__field {
  display: grid;
  gap: 8px;
  color: #111827;
  font-size: 14px;
  font-weight: 700;
}

.workspace-dialog__field input {
  width: 100%;
  height: 44px;
  padding: 0 14px;
  border: 1px solid #d8dee8;
  border-radius: 10px;
  color: #111827;
  background: #fff;
  font: inherit;
  font-weight: 600;
  outline: none;
}

.workspace-dialog__field input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(43, 94, 162, 0.12);
}

.workspace-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.workspace-dialog__button {
  min-width: 72px;
  height: 38px;
  border: 0;
  border-radius: 10px;
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.workspace-dialog__button--ghost {
  color: #526174;
  background: #eef3f9;
}

.workspace-dialog__button--primary {
  color: #fff;
  background: var(--color-primary);
}

.workspace-dialog__button:hover:not(:disabled),
.workspace-dialog__button:focus-visible:not(:disabled) {
  transform: translateY(-1px);
  outline: none;
}

.workspace-dialog__button--primary:hover:not(:disabled),
.workspace-dialog__button--primary:focus-visible:not(:disabled) {
  background: var(--color-primary-strong);
  box-shadow: 0 8px 18px rgba(43, 94, 162, 0.2);
}

.workspace-dialog__button:disabled,
.workspace-dialog__field input:disabled,
.workspace-dialog__close:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
