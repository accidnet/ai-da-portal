<script setup lang="ts">
import type { SidebarData } from '../types'

defineProps<{
  sidebar: SidebarData
}>()
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

    <nav class="nav-group" aria-label="Primary navigation">
      <a
        v-for="item in sidebar.primaryNav"
        :key="item.label"
        href="#"
        class="nav-item"
        :class="{ 'nav-item--active': item.active }"
      >
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </a>
    </nav>

    <div class="sessions-block">
      <p class="section-label">Recent Sessions</p>
      <a v-for="session in sidebar.recentSessions" :key="session.title" href="#" class="session-item">
        {{ session.title }}
      </a>
    </div>

    <nav class="nav-group nav-group--secondary" aria-label="Secondary navigation">
      <a v-for="item in sidebar.secondaryNav" :key="item.label" href="#" class="nav-item nav-item--secondary">
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </a>
    </nav>

    <div class="profile-card">
      <div class="avatar">{{ sidebar.profile.initials }}</div>
      <div>
        <strong>{{ sidebar.profile.name }}</strong>
        <span>{{ sidebar.profile.plan }}</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-card {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  backdrop-filter: blur(18px);
  box-shadow: var(--color-shadow);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-icon {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
}

.brand-block h1 {
  margin: 0;
  font: 800 1.15rem/1.1 var(--font-heading);
  color: var(--color-primary-strong);
}

.brand-block p {
  margin: 4px 0 0;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.68rem;
  font-weight: 700;
}

.nav-group {
  display: grid;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  border-radius: 16px;
  color: var(--color-text-muted);
  transition: background-color 180ms ease, color 180ms ease, transform 180ms ease;
}

.nav-item:hover {
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
  transform: translateX(2px);
}

.nav-item--active {
  color: var(--color-primary-strong);
  background: var(--color-surface-strong);
  box-shadow: inset 0 0 0 1px rgba(24, 74, 140, 0.12);
  font-weight: 700;
}

.sessions-block {
  display: grid;
  gap: 10px;
}

.section-label {
  margin: 0;
  padding: 0 14px;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.7rem;
  font-weight: 700;
}

.session-item {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 12px 14px;
  border-radius: 14px;
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.48);
}

.session-item:hover {
  background: var(--color-surface-strong);
  color: var(--color-text);
}

.nav-group--secondary {
  margin-top: auto;
  padding-top: 18px;
  border-top: 1px solid var(--color-border);
}

.nav-item--secondary {
  padding-block: 11px;
}

.profile-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.86) 0%, rgba(233, 237, 242, 0.84) 100%);
}

.avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary-strong);
  background: var(--color-secondary-soft);
  font: 800 0.94rem/1 var(--font-heading);
}

.profile-card strong,
.profile-card span {
  display: block;
}

.profile-card strong {
  font-size: 0.94rem;
}

.profile-card span {
  margin-top: 4px;
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

@media (max-width: 960px) {
  .sidebar-card {
    height: auto;
  }
}
</style>
