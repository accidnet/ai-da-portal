import type { AnalyticsChartPayload, ChartPoint } from '../../types'

export interface VisualizationPoint {
  label: string
  value: number
}

// 백엔드 값이 문자열이어도 안전하게 숫자로 변환합니다.
export function normalizeNumber(value: number | string | null | undefined): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export function resolveSeriesPoints(chart: AnalyticsChartPayload | null, fallbackPoints: ChartPoint[]): VisualizationPoint[] {
  if (chart && chart.x.length > 0 && chart.series.length > 0) {
    const series = chart.series[0]
    return chart.x.map((label, index) => ({
      label,
      value: normalizeNumber(series.data[index]),
    }))
  }

  return fallbackPoints.map((point) => ({
    label: point.label,
    value: point.spend,
  }))
}

export function resolveChartBadge(chart: AnalyticsChartPayload | null, fallbackBadge: string): string {
  return chart?.series[0]?.data.length || chart?.points?.length ? '실시간 백엔드 결과' : fallbackBadge
}

export function resolveLinePath(points: VisualizationPoint[]): string {
  if (points.length === 0) return ''

  const maxValue = Math.max(...points.map((point) => point.value), 1)
  if (points.length === 1) return 'M 0 50 L 100 50'

  return points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 100
      const y = 100 - (point.value / maxValue) * 100
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
}

export function resolveAreaPath(points: VisualizationPoint[]): string {
  const linePath = resolveLinePath(points)
  if (!linePath || points.length < 2) return ''
  return `${linePath} L 100 100 L 0 100 Z`
}

export function resolveScatterBounds(chart: AnalyticsChartPayload | null) {
  const points = chart?.points ?? []
  const maxX = Math.max(...points.map((point) => point.x), 1)
  const maxY = Math.max(...points.map((point) => point.y), 1)
  const minX = Math.min(...points.map((point) => point.x), 0)
  const minY = Math.min(...points.map((point) => point.y), 0)

  return {
    minX,
    minY,
    spanX: Math.max(maxX - minX, 1),
    spanY: Math.max(maxY - minY, 1),
  }
}

export function resolveDonutSegments(chart: AnalyticsChartPayload | null) {
  const labels = chart?.x ?? []
  const values = chart?.series[0]?.data.map((value) => normalizeNumber(value)) ?? []
  const total = Math.max(values.reduce((sum, value) => sum + value, 0), 1)

  return values.map((value, index) => ({
    label: labels[index] ?? `항목 ${index + 1}`,
    value,
    ratio: value / total,
  }))
}
