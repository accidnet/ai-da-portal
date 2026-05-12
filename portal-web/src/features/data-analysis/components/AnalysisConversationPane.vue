<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import type { ComposerData, ConversationData } from '../types'

const props = defineProps<{
  conversation: ConversationData
  composer: ComposerData
  sendDisabled?: boolean
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  send: [message: string]
}>()

const draft = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const canSend = computed(
  () => draft.value.trim().length > 0 && !props.sendDisabled,
)

const inlineThinkingMessageIndex = computed(() => {
  if (!props.conversation.isThinking) return -1
  const lastIndex = props.conversation.messages.length - 1
  if (lastIndex < 0) return -1

  const lastMessage = props.conversation.messages[lastIndex]
  if (lastMessage.role !== 'assistant') return -1
  if (lastMessage.text.trim()) return -1
  return lastIndex
})

function shouldRenderInlineThinking(index: number): boolean {
  return inlineThinkingMessageIndex.value === index
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function applyInlineMarkdown(value: string): string {
  return value
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|\W)\*([^*]+)\*(?=\W|$)/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
}

function renderMarkdown(value: string): string {
  const lines = value.split(/\r?\n/)
  const blocks: string[] = []
  let paragraph: string[] = []
  let listItems: string[] = []

  const flushParagraph = () => {
    if (!paragraph.length) {
      return
    }

    blocks.push(`<p>${applyInlineMarkdown(paragraph.join('<br />'))}</p>`)
    paragraph = []
  }

  const flushList = () => {
    if (!listItems.length) {
      return
    }

    blocks.push(`<ul>${listItems.map((item) => `<li>${applyInlineMarkdown(item)}</li>`).join('')}</ul>`)
    listItems = []
  }

  for (const rawLine of lines) {
    const line = escapeHtml(rawLine.trimEnd())
    const trimmed = line.trim()

    if (!trimmed) {
      flushParagraph()
      flushList()
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/)
    if (headingMatch) {
      flushParagraph()
      flushList()
      const level = headingMatch[1].length
      blocks.push(`<h${level}>${applyInlineMarkdown(headingMatch[2])}</h${level}>`)
      continue
    }

    const listMatch = trimmed.match(/^[-*]\s+(.*)$/)
    if (listMatch) {
      flushParagraph()
      listItems.push(listMatch[1])
      continue
    }

    flushList()
    paragraph.push(trimmed)
  }

  flushParagraph()
  flushList()

  return blocks.join('')
}

function formatPlanStepStatus(status: 'pending' | 'in_progress' | 'completed'): string {
  if (status === 'completed') return '완료'
  if (status === 'in_progress') return '진행 중'
  return '대기'
}

function formatPlanStepMarker(status: 'pending' | 'in_progress' | 'completed'): string {
  if (status === 'completed') return 'check_circle'
  if (status === 'in_progress') return 'schedule'
  return 'radio_button_unchecked'
}

function submit() {
  const message = draft.value.trim()
  if (!message || props.sendDisabled) {
    return
  }
  emit('send', message)
  draft.value = ''
  nextTick(syncTextareaHeight)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function syncTextareaHeight() {
  const textarea = textareaRef.value
  if (!textarea) return

  textarea.style.height = 'auto'
  const lineHeight = 24
  const maxHeight = lineHeight * 5
  const nextHeight = Math.min(textarea.scrollHeight, maxHeight)
  textarea.style.height = `${nextHeight}px`
  textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
}

watch(draft, () => {
  nextTick(syncTextareaHeight)
})

onMounted(() => {
  syncTextareaHeight()
})
</script>

<template>
  <section
    class="conversation-shell"
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

          <div v-if="message.text.trim()" class="message-text" v-html="renderMarkdown(message.text)"></div>

          <div v-else-if="shouldRenderInlineThinking(index)" class="thinking-row thinking-row--inline" aria-live="polite">
            <span></span>
            <span></span>
            <span></span>
            <strong>{{ conversation.thinkingLabel }}</strong>
          </div>

          <div v-if="message.planExplanation || message.plan?.length" class="message-plan-card">
            <strong v-if="message.planExplanation" class="message-plan-card__title">{{ message.planExplanation }}</strong>
            <ul v-if="message.plan?.length" class="message-plan-list">
              <li
                v-for="planStep in message.plan"
                :key="`${planStep.step}-${planStep.status}`"
                class="message-plan-list__item"
                :class="`message-plan-list__item--${planStep.status}`"
              >
                <div class="message-plan-step">
                  <span class="message-plan-step__marker material-symbols-outlined">{{ formatPlanStepMarker(planStep.status) }}</span>
                  <span class="message-plan-step__text">{{ planStep.step }}</span>
                </div>
                <span class="message-plan-status">{{ formatPlanStepStatus(planStep.status) }}</span>
              </li>
            </ul>
          </div>

          <div v-if="message.attachmentStatus" class="message-attachment-status">
            <span class="material-symbols-outlined">description</span>
            <div>
              <strong>{{ message.attachmentStatus.filename }}</strong>
              <span>{{ message.attachmentStatus.meta ?? '메시지와 함께 전송됨' }}</span>
            </div>
          </div>

          <div v-if="message.attachmentPreview" class="message-attachment-preview">
            <div class="message-attachment-preview__header">
              <div>
                <strong>{{ message.attachmentPreview.filename }}</strong>
                <span>{{ message.attachmentPreview.meta ?? '첨부 파일 미리보기' }}</span>
              </div>
              <span class="material-symbols-outlined">table_view</span>
            </div>

            <div
              v-if="message.attachmentPreview.columns.length && message.attachmentPreview.rows.length"
              class="message-attachment-preview__table"
            >
              <table>
                <thead>
                  <tr>
                    <th v-for="column in message.attachmentPreview.columns" :key="column">{{ column }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rowIndex) in message.attachmentPreview.rows" :key="rowIndex">
                    <td v-for="column in message.attachmentPreview.columns" :key="column">
                      {{ row[column] }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="message.codeBlock" class="code-card">
            <span class="code-language">{{ message.codeBlock.language }}</span>
            <pre><code>{{ message.codeBlock.content }}</code></pre>
          </div>

          <ul v-if="message.bullets?.length" class="message-list">
            <li v-for="bullet in message.bullets" :key="bullet.text">{{ bullet.text }}</li>
          </ul>
        </div>
      </article>

    </div>

    <footer class="composer-shell">
      <p v-if="errorMessage" class="composer-error">{{ errorMessage }}</p>

      <div class="composer-box">
        <textarea
          ref="textareaRef"
          v-model="draft"
          rows="1"
          :placeholder="composer.placeholder"
          :disabled="sendDisabled"
          @input="syncTextareaHeight"
          @keydown="onKeydown"
        ></textarea>
        <button
          type="button"
          class="composer-send-button"
          aria-label="메시지 전송"
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

.conversation-scroll {
  position: relative;
  min-height: 0;
  padding: 28px;
  overflow-y: auto;
  display: grid;
  gap: 24px;
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
  background: var(--color-primary);
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

.message-text :deep(p),
.message-text :deep(ul),
.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(blockquote) {
  margin: 0;
}

.message-text :deep(p + p),
.message-text :deep(p + ul),
.message-text :deep(ul + p),
.message-text :deep(h1 + p),
.message-text :deep(h2 + p),
.message-text :deep(h3 + p),
.message-text :deep(p + h1),
.message-text :deep(p + h2),
.message-text :deep(p + h3) {
  margin-top: 12px;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3) {
  color: var(--color-text);
  font-size: 0.95rem;
  line-height: 1.4;
}

.message-text :deep(ul) {
  padding-left: 18px;
}

.message-text :deep(li + li) {
  margin-top: 6px;
}

.message-text :deep(code) {
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(24, 74, 140, 0.08);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 0.82em;
}

.message-text :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.message-plan-card {
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding: 14px;
  border: 1px solid rgba(24, 74, 140, 0.12);
  border-radius: 16px;
  background: rgba(24, 74, 140, 0.04);
}

.message-plan-card__title {
  color: var(--color-text);
  font-size: 0.8rem;
}

.message-plan-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.message-plan-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.message-plan-step {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.message-plan-step__marker {
  flex-shrink: 0;
  font-size: 1rem;
}

.message-plan-step__text {
  min-width: 0;
  word-break: break-word;
}

.message-plan-list__item--completed .message-plan-step__marker {
  color: #1f9d57;
}

.message-plan-list__item--completed .message-plan-step__text {
  color: var(--color-text-soft);
  text-decoration: line-through;
}

.message-plan-list__item--in_progress .message-plan-step__marker {
  color: var(--color-primary-strong);
}

.message-plan-list__item--pending .message-plan-step__marker {
  color: var(--color-text-soft);
}

.message-plan-status {
  flex-shrink: 0;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(24, 74, 140, 0.08);
  color: var(--color-primary-strong);
  font-size: 0.68rem;
  font-weight: 700;
}

.message-attachment-status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(24, 74, 140, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
}

.message-attachment-status > span {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
}

.message-attachment-status div {
  min-width: 0;
}

.message-attachment-status strong,
.message-attachment-status div > span {
  display: block;
  overflow-wrap: anywhere;
}

.message-attachment-status strong {
  color: var(--color-text);
  font-size: 0.84rem;
}

.message-attachment-status div > span {
  margin-top: 4px;
  color: var(--color-text-soft);
  font-size: 0.73rem;
}

.message-attachment-preview {
  margin-top: 14px;
  border: 1px solid rgba(24, 74, 140, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  overflow: hidden;
}

.message-attachment-preview__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(24, 74, 140, 0.1);
}

.message-attachment-preview__header strong,
.message-attachment-preview__header span {
  display: block;
}

.message-attachment-preview__header strong {
  color: var(--color-text);
  font-size: 0.84rem;
}

.message-attachment-preview__header div > span {
  margin-top: 4px;
  color: var(--color-text-soft);
  font-size: 0.73rem;
}

.message-attachment-preview__table {
  overflow-x: auto;
}

.message-attachment-preview__table table {
  width: 100%;
  min-width: 420px;
  border-collapse: collapse;
}

.message-attachment-preview__table th,
.message-attachment-preview__table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(24, 74, 140, 0.08);
  text-align: left;
  font-size: 0.76rem;
  vertical-align: top;
}

.message-attachment-preview__table th {
  color: var(--color-text-soft);
  font-weight: 700;
  letter-spacing: 0.04em;
  background: rgba(24, 74, 140, 0.04);
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

.thinking-row--inline {
  min-height: 28px;
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

.composer-box {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
  padding: 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: 24px;
  background: var(--color-surface-strong);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

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

.composer-send-button {
  border: 0;
  color: #fff;
  background: var(--color-primary);
}

.composer-send-button:disabled,
.composer-box textarea:disabled {
  opacity: 0.65;
  cursor: default;
}

.composer-box textarea {
  min-height: 44px;
  max-height: 120px;
  padding-top: 10px;
  border: 0;
  resize: none;
  background: transparent;
  color: var(--color-text);
  line-height: 24px;
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
