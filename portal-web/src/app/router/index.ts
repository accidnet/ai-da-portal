import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import PortalLayout from '@/layouts/portal/PortalLayout.vue'
import AnalysisPage from '@/pages/AnalysisPage.vue'
import DataSourcesPage from '@/pages/DataSourcesPage.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: PortalLayout,
    children: [
      {
        path: '',
        redirect: { name: 'analysis' },
      },
      {
        path: 'analysis',
        name: 'analysis',
        component: AnalysisPage,
      },
      {
        path: 'data-sources',
        name: 'data-sources',
        component: DataSourcesPage,
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
