<script setup lang="ts">
defineProps<{
  datasetsCount: number;
}>();

const emit = defineEmits<{
  uploadFile: [];
}>();
</script>

<template>
  <section class="source-workspace">
    <section class="panel-card source-summary">
      <div>
        <p>등록된 원천 데이터</p>
        <strong>{{ datasetsCount }}개</strong>
        <span>파일 업로드와 DB 연결 소스가 이 영역에 함께 표시될 예정입니다.</span>
      </div>
    </section>

    <div class="source-action-grid">
      <article class="panel-card source-action-card source-action-card--primary">
        <div class="source-action-card__icon">
          <span class="material-symbols-outlined">upload_file</span>
        </div>
        <div class="source-action-card__body">
          <p>파일 업로드</p>
          <h3>CSV, Excel 파일을 원천 데이터로 등록</h3>
          <span>업로드된 파일은 데이터셋 카탈로그에서 분석용 데이터셋으로 연결할 수 있습니다.</span>
        </div>
        <button
          type="button"
          class="toolbar-button toolbar-button--primary"
          @click="emit('uploadFile')"
        >
          파일 선택
        </button>
      </article>

      <article class="panel-card source-action-card">
        <div class="source-action-card__icon">
          <span class="material-symbols-outlined">dns</span>
        </div>
        <div class="source-action-card__body">
          <p>DB 연결</p>
          <h3>운영 DB 또는 분석 DB를 원천 데이터로 연결</h3>
          <span>연결 정보와 테이블 선택 기능은 준비 중입니다.</span>
        </div>
        <button type="button" class="toolbar-button" disabled>연결 준비중</button>
      </article>
    </div>
  </section>
</template>

<style scoped>
.source-workspace {
  display: grid;
  gap: 16px;
}

.panel-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--color-shadow);
}

.source-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
}

.source-summary p {
  margin: 0 0 6px;
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.source-summary strong {
  display: block;
  margin-bottom: 4px;
  color: var(--color-text);
  font-family: var(--font-heading);
  font-size: 1.45rem;
}

.source-summary span,
.source-action-card__body span {
  color: var(--color-text-muted);
}

.source-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.source-action-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.source-action-card--primary {
  border-color: rgba(24, 74, 140, 0.28);
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.96),
    rgba(247, 250, 255, 0.92)
  );
}

.source-action-card__icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  color: var(--color-primary);
  background: rgba(24, 74, 140, 0.1);
}

.source-action-card__icon .material-symbols-outlined {
  font-size: 1.4rem;
}

.source-action-card__body {
  min-width: 0;
}

.source-action-card__body p {
  margin: 0 0 6px;
  color: var(--color-text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.source-action-card__body h3 {
  margin: 0 0 6px;
  color: var(--color-text);
  font-size: 1rem;
  line-height: 1.35;
}

.toolbar-button {
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface-muted);
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
}

.toolbar-button--primary {
  border-color: var(--color-primary);
  color: #fff;
  background: var(--color-primary);
}

.toolbar-button:disabled {
  opacity: 0.55;
  cursor: default;
}

@media (max-width: 900px) {
  .source-summary {
    display: grid;
  }

  .source-action-grid {
    grid-template-columns: 1fr;
  }

  .source-action-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .source-action-card .toolbar-button {
    grid-column: 1 / -1;
    justify-self: start;
  }
}

@media (max-width: 640px) {
  .source-action-card,
  .source-summary {
    padding: 16px;
  }
}
</style>
