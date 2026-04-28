import { onUnmounted, ref, watch } from 'vue'

import { ANALYTICS_PANE_WIDTH_STORAGE_KEY, SIDEBAR_WIDTH_STORAGE_KEY } from '../constants/analysisPage'
import { clampAnalyticsPaneWidth, clampSidebarWidth } from '../utils/analysisPageHelpers'

export function useAnalysisPaneLayout() {
  const sidebarWidth = ref(288)
  const analyticsPaneWidth = ref(420)
  const isResizingSidebar = ref(false)
  const isResizingAnalyticsPane = ref(false)
  const isAnalyticsFullscreen = ref(false)

  function handleSidebarResize(event: PointerEvent) {
    if (!isResizingSidebar.value || window.innerWidth <= 960) {
      return
    }

    sidebarWidth.value = clampSidebarWidth(event.clientX - 24)
  }

  function stopSidebarResize() {
    isResizingSidebar.value = false
    window.removeEventListener('pointermove', handleSidebarResize)
    window.removeEventListener('pointerup', stopSidebarResize)
  }

  function startSidebarResize(event: PointerEvent) {
    if (window.innerWidth <= 960) {
      return
    }

    event.preventDefault()
    isResizingSidebar.value = true
    window.addEventListener('pointermove', handleSidebarResize)
    window.addEventListener('pointerup', stopSidebarResize)
  }

  function handleAnalyticsPaneResize(event: PointerEvent) {
    if (!isResizingAnalyticsPane.value || window.innerWidth <= 1280) {
      return
    }

    analyticsPaneWidth.value = clampAnalyticsPaneWidth(window.innerWidth - event.clientX - 48)
  }

  function stopAnalyticsPaneResize() {
    isResizingAnalyticsPane.value = false
    window.removeEventListener('pointermove', handleAnalyticsPaneResize)
    window.removeEventListener('pointerup', stopAnalyticsPaneResize)
  }

  function startAnalyticsPaneResize(event: PointerEvent) {
    if (window.innerWidth <= 1280) {
      return
    }

    event.preventDefault()
    isResizingAnalyticsPane.value = true
    window.addEventListener('pointermove', handleAnalyticsPaneResize)
    window.addEventListener('pointerup', stopAnalyticsPaneResize)
  }

  function restoreAnalyticsPaneWidth() {
    const storedWidth = window.localStorage.getItem(ANALYTICS_PANE_WIDTH_STORAGE_KEY)
    if (!storedWidth) {
      return
    }

    const parsedWidth = Number(storedWidth)
    if (!Number.isFinite(parsedWidth)) {
      return
    }

    analyticsPaneWidth.value = clampAnalyticsPaneWidth(parsedWidth)
  }

  function restoreSidebarWidth() {
    const storedWidth = window.localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY)
    if (!storedWidth) {
      return
    }

    const parsedWidth = Number(storedWidth)
    if (!Number.isFinite(parsedWidth)) {
      return
    }

    sidebarWidth.value = clampSidebarWidth(parsedWidth)
  }

  function toggleAnalyticsFullscreen() {
    isAnalyticsFullscreen.value = !isAnalyticsFullscreen.value
  }

  watch(sidebarWidth, (width) => {
    window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, String(clampSidebarWidth(width)))
  })

  watch(analyticsPaneWidth, (width) => {
    window.localStorage.setItem(ANALYTICS_PANE_WIDTH_STORAGE_KEY, String(clampAnalyticsPaneWidth(width)))
  })

  onUnmounted(() => {
    stopSidebarResize()
    stopAnalyticsPaneResize()
  })

  return {
    sidebarWidth,
    isResizingSidebar,
    analyticsPaneWidth,
    isResizingAnalyticsPane,
    isAnalyticsFullscreen,
    restoreSidebarWidth,
    restoreAnalyticsPaneWidth,
    startSidebarResize,
    stopSidebarResize,
    startAnalyticsPaneResize,
    stopAnalyticsPaneResize,
    toggleAnalyticsFullscreen,
  }
}
