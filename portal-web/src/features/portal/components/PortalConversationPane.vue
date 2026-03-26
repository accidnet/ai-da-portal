<script setup lang="ts">
import type { ComposerData, ConversationData } from '../types'

defineProps<{
  conversation: ConversationData
  composer: ComposerData
}>()
</script>

<template>
  <section class="conversation-shell">
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

      <div class="thinking-row" aria-live="polite">
        <span></span>
        <span></span>
        <span></span>
        <strong>{{ conversation.thinkingLabel }}</strong>
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

      <div class="composer-box">
        <button type="button" class="composer-icon-button" aria-label="Attach file">
          <span class="material-symbols-outlined">attach_file</span>
        </button>
        <textarea rows="1" :placeholder="composer.placeholder"></textarea>
        <button type="button" class="composer-send-button" aria-label="Send message">
          <span class="material-symbols-outlined">send</span>
        </button>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.conversation-shell {
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(244, 247, 251, 0.78);
  overflow: hidden;
}

.conversation-scroll {
  min-height: 0;
  padding: 28px;
  overflow-y: auto;
  display: grid;
  gap: 24px;
}

.message-row {
  display: flex;
}

.message-row--user {
  justify-content: flex-end;
}

.message-card {
  max-width: min(92%, 760px);
  padding: 20px;
  border-radius: 22px;
  box-shadow: 0 12px 26px rgba(20, 31, 48, 0.06);
}

.message-card--user {
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, #245fa7 100%);
  border-top-right-radius: 8px;
}

.message-card--assistant {
  width: 100%;
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

.composer-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
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
  cursor: pointer;
}

.composer-icon-button {
  color: var(--color-text-soft);
}

.composer-send-button {
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
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
