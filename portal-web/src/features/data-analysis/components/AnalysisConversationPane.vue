<script setup lang="ts">
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";
import markdownItKatex from "markdown-it-katex";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { ComposerData, ConversationData } from "../types";

const props = defineProps<{
  conversation: ConversationData;
  composer: ComposerData;
  sendDisabled?: boolean;
  errorMessage?: string | null;
}>();

const emit = defineEmits<{
  send: [message: string];
}>();

// 입력창 위에 노출할 기본 추천 질문 목록입니다.
const recommendedQuestions = [
  "모든 데이터에 대해 핵심을 간략히 분석해줘",
  "유의미한 연구 주제를 제안해줘",
  "데이터에 적절한 차원 축소 기법좀 적용해줘",
  "머신러닝 모델 설계를 제안해줄래?",
] as const;

const draft = ref("");
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const conversationScrollRef = ref<HTMLDivElement | null>(null);
const shouldFollowStreamingResponse = ref(false);

const markdownRenderer = new MarkdownIt({
  breaks: true,
  html: false,
  linkify: true,
  typographer: true,
}).use(markdownItKatex, {
  throwOnError: false,
  strict: "ignore",
  trust: false,
});
const defaultLinkOpenRenderer =
  markdownRenderer.renderer.rules.link_open ??
  ((tokens, index, options, _env, self) =>
    self.renderToken(tokens, index, options));

markdownRenderer.renderer.rules.link_open = (
  tokens,
  index,
  options,
  env,
  self,
) => {
  const token = tokens[index];

  // AI 응답 링크는 현재 작업 흐름을 유지하도록 새 탭으로 열고 referrer를 넘기지 않습니다.
  token.attrSet("target", "_blank");
  token.attrSet("rel", "noreferrer");

  return defaultLinkOpenRenderer(tokens, index, options, env, self);
};

const canSend = computed(
  () => draft.value.trim().length > 0 && !props.sendDisabled,
);

const thinkingMessageIndex = computed(() => {
  if (!props.conversation.isThinking) return -1;
  for (
    let index = props.conversation.messages.length - 1;
    index >= 0;
    index -= 1
  ) {
    if (props.conversation.messages[index].role === "assistant") {
      return index;
    }
  }
  return -1;
});

function shouldRenderThinking(index: number): boolean {
  return thinkingMessageIndex.value === index;
}

/** AI 응답 Markdown을 표준 파서로 렌더링하고 v-html 주입 전에 정화합니다. */
function renderMarkdown(value: string): string {
  return DOMPurify.sanitize(
    markdownRenderer.render(normalizeMathDelimiters(value)),
    {
      ADD_ATTR: ["aria-hidden", "class", "style"],
      USE_PROFILES: { html: true, mathMl: true },
    },
  );
}

/** AI가 자주 쓰는 LaTeX delimiter를 KaTeX 플러그인이 처리하는 형식으로 맞춥니다. */
function normalizeMathDelimiters(value: string): string {
  return value
    .replace(/\\\[/g, "$$")
    .replace(/\\\]/g, "$$")
    .replace(/\\\(/g, "$")
    .replace(/\\\)/g, "$");
}

function formatPlanStepStatus(
  status: "pending" | "in_progress" | "completed",
): string {
  if (status === "completed") return "완료";
  if (status === "in_progress") return "진행 중";
  return "대기";
}

function formatPlanStepMarker(
  status: "pending" | "in_progress" | "completed",
): string {
  if (status === "completed") return "check_circle";
  if (status === "in_progress") return "schedule";
  return "radio_button_unchecked";
}

/** 사용자 전송 직후 응답 스트리밍 자동 추적을 다시 활성화합니다. */
function submit() {
  const message = draft.value.trim();
  if (!message || props.sendDisabled) {
    return;
  }
  shouldFollowStreamingResponse.value = true;
  scrollConversationToBottom();
  emit("send", message);
  draft.value = "";
  nextTick(syncTextareaHeight);
}

function selectRecommendedQuestion(question: string) {
  // 추천 질문 클릭 시 사용자가 전송 전 수정할 수 있도록 입력창에만 반영합니다.
  draft.value = question;
  nextTick(() => {
    syncTextareaHeight();
    textareaRef.value?.focus();
  });
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

function syncTextareaHeight() {
  const textarea = textareaRef.value;
  if (!textarea) return;

  textarea.style.height = "auto";
  const lineHeight = 24;
  const maxHeight = lineHeight * 5;
  const nextHeight = Math.min(textarea.scrollHeight, maxHeight);
  textarea.style.height = `${nextHeight}px`;
  textarea.style.overflowY =
    textarea.scrollHeight > maxHeight ? "auto" : "hidden";
}

/** 응답 스트리밍 중 새 버블 높이에 맞춰 대화 영역 하단을 유지합니다. */
function scrollConversationToBottom() {
  nextTick(() => {
    requestAnimationFrame(() => {
      const scrollContainer = conversationScrollRef.value;
      if (!scrollContainer || !shouldFollowStreamingResponse.value) return;

      scrollContainer.scrollTop = scrollContainer.scrollHeight;
    });
  });
}

/** 사용자가 화면 어디든 직접 누르면 다음 전송 전까지 자동 추적을 멈춥니다. */
function stopFollowingOnUserClick() {
  if (!shouldFollowStreamingResponse.value) return;
  shouldFollowStreamingResponse.value = false;
}

watch(draft, () => {
  nextTick(syncTextareaHeight);
});

watch(
  () => props.conversation.messages,
  () => {
    scrollConversationToBottom();
  },
  { deep: true },
);

onMounted(() => {
  syncTextareaHeight();
  document.addEventListener("pointerdown", stopFollowingOnUserClick, {
    capture: true,
  });
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", stopFollowingOnUserClick, {
    capture: true,
  });
});
</script>

<template>
  <section class="conversation-shell">
    <div ref="conversationScrollRef" class="conversation-scroll">
      <article
        v-for="(message, index) in conversation.messages"
        :key="`${message.role}-${index}`"
        class="message-row"
        :class="`message-row--${message.role}`"
      >
        <div class="message-card" :class="`message-card--${message.role}`">
          <div v-if="message.author" class="message-author">
            <span class="message-author__badge material-symbols-outlined"
              >architecture</span
            >
            <span>{{ message.author }}</span>
          </div>

          <div
            v-if="message.text.trim()"
            class="message-text"
            v-html="renderMarkdown(message.text)"
          ></div>

          <div
            v-if="shouldRenderThinking(index)"
            class="thinking-row thinking-row--inline"
            aria-live="polite"
          >
            <span></span>
            <span></span>
            <span></span>
            <strong>{{ conversation.thinkingLabel }}</strong>
          </div>

          <div
            v-if="message.planExplanation || message.plan?.length"
            class="message-plan-card"
          >
            <strong
              v-if="message.planExplanation"
              class="message-plan-card__title"
              >{{ message.planExplanation }}</strong
            >
            <ul v-if="message.plan?.length" class="message-plan-list">
              <li
                v-for="planStep in message.plan"
                :key="`${planStep.step}-${planStep.status}`"
                class="message-plan-list__item"
                :class="`message-plan-list__item--${planStep.status}`"
              >
                <div class="message-plan-step">
                  <span
                    class="message-plan-step__marker material-symbols-outlined"
                    >{{ formatPlanStepMarker(planStep.status) }}</span
                  >
                  <span class="message-plan-step__text">{{
                    planStep.step
                  }}</span>
                </div>
                <span class="message-plan-status">{{
                  formatPlanStepStatus(planStep.status)
                }}</span>
              </li>
            </ul>
          </div>

          <div
            v-if="message.attachmentStatus"
            class="message-attachment-status"
          >
            <span class="material-symbols-outlined">description</span>
            <div>
              <strong>{{ message.attachmentStatus.filename }}</strong>
              <span>{{
                message.attachmentStatus.meta ?? "메시지와 함께 전송됨"
              }}</span>
            </div>
          </div>

          <div
            v-if="message.attachmentPreview"
            class="message-attachment-preview"
          >
            <div class="message-attachment-preview__header">
              <div>
                <strong>{{ message.attachmentPreview.filename }}</strong>
                <span>{{
                  message.attachmentPreview.meta ?? "첨부 파일 미리보기"
                }}</span>
              </div>
              <span class="material-symbols-outlined">table_view</span>
            </div>

            <div
              v-if="
                message.attachmentPreview.columns.length &&
                message.attachmentPreview.rows.length
              "
              class="message-attachment-preview__table"
            >
              <table>
                <thead>
                  <tr>
                    <th
                      v-for="column in message.attachmentPreview.columns"
                      :key="column"
                    >
                      {{ column }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, rowIndex) in message.attachmentPreview.rows"
                    :key="rowIndex"
                  >
                    <td
                      v-for="column in message.attachmentPreview.columns"
                      :key="column"
                    >
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
            <li v-for="bullet in message.bullets" :key="bullet.text">
              {{ bullet.text }}
            </li>
          </ul>
        </div>
      </article>
    </div>

    <div class="recommended-question-bar" aria-label="추천 질문">
      <button
        v-for="question in recommendedQuestions"
        :key="question"
        type="button"
        class="recommended-question-button"
        :disabled="sendDisabled"
        @click="selectRecommendedQuestion(question)"
      >
        {{ question }}
      </button>
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
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
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
.message-text :deep(ol),
.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(blockquote),
.message-text :deep(pre),
.message-text :deep(table) {
  margin: 0;
}

.message-text :deep(p + p),
.message-text :deep(p + ul),
.message-text :deep(p + ol),
.message-text :deep(ul + p),
.message-text :deep(ol + p),
.message-text :deep(ul + ul),
.message-text :deep(ol + ol),
.message-text :deep(ul + ol),
.message-text :deep(ol + ul),
.message-text :deep(h1 + p),
.message-text :deep(h2 + p),
.message-text :deep(h3 + p),
.message-text :deep(p + h1),
.message-text :deep(p + h2),
.message-text :deep(p + h3),
.message-text :deep(p + blockquote),
.message-text :deep(blockquote + p),
.message-text :deep(p + pre),
.message-text :deep(pre + p),
.message-text :deep(p + table),
.message-text :deep(table + p) {
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

.message-text :deep(ol) {
  padding-left: 20px;
}

.message-text :deep(li + li) {
  margin-top: 6px;
}

.message-text :deep(code) {
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(24, 74, 140, 0.08);
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    monospace;
  font-size: 0.82em;
}

.message-text :deep(pre) {
  overflow-x: auto;
  padding: 14px;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
}

.message-text :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: 0.78rem;
  line-height: 1.65;
}

.message-text :deep(blockquote) {
  padding-left: 12px;
  border-left: 3px solid rgba(24, 74, 140, 0.28);
  color: var(--color-text-muted);
}

.message-text :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
}

.message-text :deep(th),
.message-text :deep(td) {
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  text-align: left;
  white-space: nowrap;
}

.message-text :deep(th) {
  background: rgba(24, 74, 140, 0.08);
  color: var(--color-text);
  font-weight: 700;
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
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    monospace;
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
  margin-top: 10px;
}

.message-text + .thinking-row--inline {
  margin-top: 14px;
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

.recommended-question-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 14px 24px 0;
  border-top: 1px solid var(--color-border);
  background: rgba(242, 246, 250, 0.94);
}

.recommended-question-button {
  min-height: 36px;
  padding: 8px 14px;
  border: 1px solid rgba(24, 74, 140, 0.16);
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: rgba(255, 255, 255, 0.78);
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 700;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    transform 160ms ease;
}

.recommended-question-button:hover:not(:disabled),
.recommended-question-button:focus-visible:not(:disabled) {
  border-color: rgba(24, 74, 140, 0.34);
  background: var(--color-surface-strong);
  transform: translateY(-1px);
}

.recommended-question-button:focus-visible {
  outline: 2px solid rgba(24, 74, 140, 0.28);
  outline-offset: 2px;
}

.recommended-question-button:disabled {
  opacity: 0.65;
  cursor: default;
}

.composer-shell {
  padding: 14px 24px 24px;
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

  .recommended-question-bar {
    padding: 12px 16px 0;
  }

  .recommended-question-button {
    flex: 1 1 100%;
  }

  .composer-shell {
    padding: 12px 16px 16px;
  }
}
</style>
