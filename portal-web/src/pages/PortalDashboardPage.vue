<script setup lang="ts">
import PortalAnalyticsPane from '../features/portal/components/PortalAnalyticsPane.vue'
import PortalConversationPane from '../features/portal/components/PortalConversationPane.vue'
import PortalHeader from '../features/portal/components/PortalHeader.vue'
import PortalSidebar from '../features/portal/components/PortalSidebar.vue'
import { portalDashboard } from '../features/portal/data/dashboard'
</script>

<template>
  <div class="portal-layout">
    <PortalSidebar :sidebar="portalDashboard.sidebar" />

    <div class="portal-main-shell">
      <PortalHeader :header="portalDashboard.header" />

      <div class="portal-main-grid">
        <PortalConversationPane
          :conversation="portalDashboard.conversation"
          :composer="portalDashboard.composer"
        />
        <PortalAnalyticsPane :analytics="portalDashboard.analytics" />
      </div>
    </div>

    <button class="floating-action" type="button" aria-label="Create new analysis">
      <span class="material-symbols-outlined">add</span>
    </button>
  </div>
</template>

<style scoped>
.portal-layout {
  position: relative;
  height: 100vh;
  display: grid;
  grid-template-columns: 288px minmax(0, 1fr);
  gap: 24px;
  padding: 24px;
  overflow: hidden;
}

.portal-main-shell {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 20px;
  overflow: hidden;
}

.portal-main-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 20px;
}

.floating-action {
  position: fixed;
  right: 28px;
  bottom: 28px;
  width: 60px;
  height: 60px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 20px;
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
  box-shadow: 0 18px 32px rgba(16, 56, 104, 0.24);
  cursor: pointer;
  transition: transform 180ms ease, box-shadow 180ms ease;
}

.floating-action:hover {
  transform: translateY(-2px);
  box-shadow: 0 22px 40px rgba(16, 56, 104, 0.28);
}

@media (max-width: 1280px) {
  .portal-layout {
    grid-template-columns: 248px minmax(0, 1fr);
  }

  .portal-main-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 960px) {
  .portal-layout {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
  }

  .floating-action {
    right: 18px;
    bottom: 18px;
    width: 54px;
    height: 54px;
    border-radius: 18px;
  }
}
</style>
