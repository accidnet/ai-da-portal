import { onUnmounted, ref, watch } from 'vue'

import { ANALYTICS_PANE_WIDTH_STORAGE_KEY } from '../constants/portalPage'
import { clampAnalyticsPaneWidth } from '../utils/portalPageHelpers'

export function usePortalAnalyticsPane() {
  const analyticsPaneWidth = ref(420)
  const isResizingAnalyticsPane = ref(false)
  const isAnalyticsFullscreen = ref(false)

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

  function toggleAnalyticsFullscreen() {
    isAnalyticsFullscreen.value = !isAnalyticsFullscreen.value
  }

  watch(analyticsPaneWidth, (width) => {
    window.localStorage.setItem(ANALYTICS_PANE_WIDTH_STORAGE_KEY, String(clampAnalyticsPaneWidth(width)))
  })

  onUnmounted(() => {
    stopAnalyticsPaneResize()
  })

  return {
    analyticsPaneWidth,
    isResizingAnalyticsPane,
    isAnalyticsFullscreen,
    restoreAnalyticsPaneWidth,
    startAnalyticsPaneResize,
    stopAnalyticsPaneResize,
    toggleAnalyticsFullscreen,
  }
}
