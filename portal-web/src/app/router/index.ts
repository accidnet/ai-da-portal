import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import PortalLayout from '@/layouts/portal/PortalLayout.vue'
import DataAnalysisPage from '@/pages/DataAnalysisPage.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: PortalLayout,
    children: [
      {
        path: '',
        name: 'data-analysis',
        component: DataAnalysisPage,
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
