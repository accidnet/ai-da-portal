import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import PortalLayout from '@/layouts/portal/PortalLayout.vue'

const LAST_PORTAL_ROUTE_STORAGE_KEY = 'portal:last-route-name'

/** 사용자가 마지막으로 머문 주요 화면 라우트를 복원합니다. */
function readLastPortalRouteName(): 'analysis' | 'data-sources' {
  if (typeof window === 'undefined') {
    return 'analysis'
  }

  const routeName = window.localStorage.getItem(LAST_PORTAL_ROUTE_STORAGE_KEY)
  return routeName === 'data-sources' ? 'data-sources' : 'analysis'
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: PortalLayout,
    children: [
      {
        path: '',
        redirect: () => ({ name: readLastPortalRouteName() }),
      },
      {
        path: 'analysis',
        name: 'analysis',
        component: () => import('@/pages/AnalysisPage.vue'),
      },
      {
        path: 'data-sources',
        name: 'data-sources',
        component: () => import('@/pages/DataSourcesPage.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

/** 앱의 페이지 전환을 담당하는 전역 라우터입니다. */
export const router = createRouter({
  history: createWebHistory(),
  routes,
})
