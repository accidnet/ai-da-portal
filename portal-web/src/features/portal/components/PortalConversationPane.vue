<script setup lang="ts">
import { computed, ref } from 'vue'

import type { ComposerData, ConversationData } from '../types'

const props = defineProps<{
  conversation: ConversationData
  composer: ComposerData
  sendDisabled?: boolean
  attachDisabled?: boolean
  errorMessage?: string | null
  attachedFileName?: string | null
  attachedFileMeta?: string | null
}>()

const emit = defineEmits<{
  send: [message: string]
  attach: []
  dropFile: [file: File]
  removeAttachment: []
}>()

const draft = ref('')
const isDragActive = ref(false)

const canSend = computed(
  () => (draft.value.trim().length > 0 || Boolean(props.attachedFileName)) && !props.sendDisabled,
)

function submit() {
  const message = draft.value.trim()
  if ((!message && !props.attachedFileName) || props.sendDisabled) {
    return
  }
  emit('send', message)
  draft.value = ''
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function handleDragEnter() {
  if (props.attachDisabled) {
    return
  }

  isDragActive.value = true
}

function handleDragOver(event: DragEvent) {
  if (props.attachDisabled) {
    return
  }

  event.preventDefault()
  isDragActive.value = true
}

function handleDragLeave(event: DragEvent) {
  const nextTarget = event.relatedTarget as Node | null
  if (nextTarget && event.currentTarget instanceof HTMLElement && event.currentTarget.contains(nextTarget)) {
    return
  }

  isDragActive.value = false
}

function handleDrop(event: DragEvent) {
  if (props.attachDisabled) {
    return
  }

  event.preventDefault()
  isDragActive.value = false
  const file = event.dataTransfer?.files?.[0]

  if (!file) {
    return
  }

  emit('dropFile', file)
}
</script>

<template>
  <section
    class="conversation-shell"
    :class="{ 'conversation-shell--drag-active': isDragActive }"
    @dragenter="handleDragEnter"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <div class="conversation-scroll">
      <article
        v-for="(message, index) in conversation.messages"
        :key="`${message.role}-${index}`"
        class="message-row"
        :class="`message-row--${message.role}`"
      >
        <div class="message-card" :class="`message-card--${message.role}`">
          <div v-if="message.author" class="message-author">
            <span class="message-author__badge material-symbols-outlined">architecture</span>
            <span>{{ message.author }}</span>
          </div>

          <p class="message-text">{{ message.text }}</p>

          <div v-if="message.codeBlock" class="code-card">
            <span class="code-language">{{ message.codeBlock.language }}</span>
            <pre><code>{{ message.codeBlock.content }}</code></pre>
          </div>

          <ul v-if="message.bullets?.length" class="message-list">
            <li v-for="bullet in message.bullets" :key="bullet.text">{{ bullet.text }}</li>
          </ul>
        </div>
      </article>

      <div v-if="conversation.isThinking" class="thinking-row" aria-live="polite">
        <span></span>
        <span></span>
        <span></span>
        <strong>{{ conversation.thinkingLabel }}</strong>
      </div>

      <div v-if="isDragActive" class="drop-overlay" aria-hidden="true">
        <div class="drop-overlay__card">
          <span class="material-symbols-outlined">upload_file</span>
          <strong>CSV 파일을 여기에 놓으세요</strong>
          <p>드롭한 파일은 입력창에 첨부되고 전송 시 함께 분석됩니다.</p>
        </div>
      </div>
    </div>

    <footer class="composer-shell">
      <div class="composer-chips">
        <span
          v-for="chip in composer.chips"
          :key="chip.label"
          class="composer-chip"
          :class="`composer-chip--${chip.tone ?? 'neutral'}`"
        >
          <span class="material-symbols-outlined">{{ chip.icon }}</span>
          {{ chip.label }}
        </span>
      </div>

      <p v-if="errorMessage" class="composer-error">{{ errorMessage }}</p>

      <div v-if="attachedFileName" class="composer-attachment">
        <div>
          <strong>{{ attachedFileName }}</strong>
          <span>{{ attachedFileMeta ?? '메시지와 함께 전송 예정' }}</span>
        </div>
        <button type="button" :disabled="attachDisabled" @click="emit('removeAttachment')">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <div class="composer-box">
        <button
          type="button"
          class="composer-icon-button"
          aria-label="Attach file"
          :disabled="attachDisabled"
          @click="emit('attach')"
        >
          <span class="material-symbols-outlined">attach_file</span>
        </button>
        <textarea
          v-model="draft"
          rows="1"
          :placeholder="composer.placeholder"
          :disabled="sendDisabled"
          @keydown="onKeydown"
        ></textarea>
        <button
          type="button"
          class="composer-send-button"
          aria-label="Send message"
          :disabled="!canSend"
          @click="submit"
        >
          <span class="material-symbols-outlined">send</span>
        </button>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.conversation-shell {
  position: relative;
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(244, 247, 251, 0.78);
  overflow: hidden;
  transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

.conversation-shell--drag-active {
  border-color: rgba(24, 74, 140, 0.36);
  box-shadow: 0 0 0 4px rgba(24, 74, 140, 0.08);
  transform: translateY(-1px);
}

.conversation-scroll {
  position: relative;
  min-height: 0;
  padding: 28px;
  overflow-y: auto;
  display: grid;
  gap: 24px;
}

.drop-overlay {
  position: absolute;
  inset: 16px;
  display: grid;
  place-items: center;
  border-radius: 24px;
  background: rgba(235, 243, 253, 0.88);
  border: 2px dashed rgba(24, 74, 140, 0.28);
  backdrop-filter: blur(4px);
}

.drop-overlay__card {
  padding: 22px 24px;
  border-radius: 22px;
  text-align: center;
  color: var(--color-primary-strong);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 16px 34px rgba(16, 56, 104, 0.12);
}

.drop-overlay__card .material-symbols-outlined {
  font-size: 2rem;
}

.drop-overlay__card strong {
  display: block;
  margin-top: 10px;
  font-size: 1rem;
}

.drop-overlay__card p {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 0.86rem;
}

.message-row {
  display: flex;
  align-items: flex-start;
}

.message-row--user {
  justify-content: flex-end;
}

.message-card {
  display: inline-block;
  max-width: min(92%, 760px);
  padding: 20px;
  border-radius: 22px;
  box-shadow: 0 12px 26px rgba(20, 31, 48, 0.06);
}

.message-card--user {
  align-self: flex-start;
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, #245fa7 100%);
  border-top-right-radius: 8px;
}

.message-card--assistant {
  align-self: flex-start;
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.92);
  border-top-left-radius: 8px;
}

.message-author {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  color: var(--color-primary-strong);
  font-size: 0.76rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.message-author__badge {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: #fff;
  background: var(--color-primary);
  font-size: 1rem;
}

.message-text {
  margin: 0;
  line-height: 1.72;
}

.code-card {
  margin-top: 18px;
  padding: 18px;
  border-left: 4px solid var(--color-primary);
  border-radius: 18px;
  background: var(--color-surface-muted);
  overflow-x: auto;
}

.code-language {
  display: inline-block;
  margin-bottom: 10px;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 700;
}

.code-card pre,
.code-card code {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 0.85rem;
  line-height: 1.65;
  white-space: pre-wrap;
}

.message-list {
  margin: 18px 0 0;
  padding-left: 18px;
  color: var(--color-text-muted);
}

.message-list li + li {
  margin-top: 8px;
}

.thinking-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.thinking-row span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--color-primary);
  animation: pulse 1.3s ease-in-out infinite;
}

.thinking-row span:nth-child(2) {
  animation-delay: 0.15s;
}

.thinking-row span:nth-child(3) {
  animation-delay: 0.3s;
}

.composer-shell {
  padding: 20px 24px 24px;
  border-top: 1px solid var(--color-border);
  background: rgba(242, 246, 250, 0.94);
}

.composer-error {
  margin: 0 0 12px;
  color: #9b3b3b;
  font-size: 0.82rem;
}

.composer-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
}

.composer-attachment {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(24, 74, 140, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
}

.composer-attachment strong,
.composer-attachment span {
  display: block;
}

.composer-attachment strong {
  color: var(--color-text);
  font-size: 0.85rem;
}

.composer-attachment span {
  margin-top: 4px;
  color: var(--color-text-soft);
  font-size: 0.74rem;
}

.composer-attachment button {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 12px;
  color: var(--color-text-soft);
  background: rgba(24, 74, 140, 0.08);
  cursor: pointer;
}

.composer-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
}

.composer-chip--primary {
  color: var(--color-primary-strong);
  background: var(--color-secondary-soft);
}

.composer-chip--neutral {
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.72);
}

.composer-box {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
  padding: 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: 24px;
  background: var(--color-surface-strong);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.composer-icon-button,
.composer-send-button {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  border: 0;
  cursor: pointer;
}

.composer-icon-button {
  color: var(--color-text-soft);
  background: transparent;
  transition: transform 180ms ease, background-color 180ms ease, box-shadow 180ms ease, color 180ms ease;
}

.composer-icon-button:hover:not(:disabled) {
  color: var(--color-primary-strong);
  background: rgba(24, 74, 140, 0.08);
  box-shadow: 0 8px 18px rgba(16, 56, 104, 0.14);
  transform: translateY(-1px);
}

.composer-send-button {
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
}

.composer-send-button:disabled,
.composer-box textarea:disabled,
.composer-icon-button:disabled {
  opacity: 0.65;
  cursor: default;
}

.composer-box textarea {
  min-height: 44px;
  max-height: 140px;
  padding-top: 10px;
  border: 0;
  resize: vertical;
  background: transparent;
  color: var(--color-text);
}

.composer-box textarea:focus {
  outline: none;
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(0.7);
    opacity: 0.5;
  }

  50% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (max-width: 720px) {
  .conversation-scroll {
    padding: 18px;
  }

  .composer-shell {
    padding: 16px;
  }
}
</style>
