import { ANALYSIS_SHARE_STORAGE_PREFIX } from '../constants/analysisPage'
import type { SharedAnalysisSnapshot } from '../types'

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function shareStorageKey(id: string): string {
  return `${ANALYSIS_SHARE_STORAGE_PREFIX}${id}`
}

export function createSharedAnalysisSnapshot(payload: {
  title: string
  fileName: string
  content: string
}): SharedAnalysisSnapshot {
  const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`

  return {
    id,
    title: payload.title,
    fileName: payload.fileName,
    content: payload.content,
    createdAt: new Date().toISOString(),
  }
}

export function saveSharedAnalysisSnapshot(snapshot: SharedAnalysisSnapshot) {
  window.localStorage.setItem(shareStorageKey(snapshot.id), JSON.stringify(snapshot))
}

export function loadSharedAnalysisSnapshot(shareId: string): SharedAnalysisSnapshot | null {
  const raw = window.localStorage.getItem(shareStorageKey(shareId))
  if (!raw) return null

  try {
    return JSON.parse(raw) as SharedAnalysisSnapshot
  } catch {
    return null
  }
}

export function buildSharedAnalysisUrl(shareId: string): string {
  const url = new URL(window.location.href)
  url.searchParams.set('share', shareId)
  url.pathname = '/analysis'
  url.hash = ''
  return url.toString()
}

export function getSharedAnalysisIdFromUrl(): string | null {
  return new URL(window.location.href).searchParams.get('share')
}

export async function copyTextToClipboard(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value)
    return true
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.setAttribute('readonly', 'true')
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.append(textarea)
    textarea.select()

    try {
      const result = document.execCommand('copy')
      textarea.remove()
      return result
    } catch {
      textarea.remove()
      return false
    }
  }
}

export function openAnalysisPreview(snapshot: Pick<SharedAnalysisSnapshot, 'title' | 'fileName' | 'content' | 'createdAt'>): boolean {
  const previewWindow = window.open('', '_blank', 'noopener,noreferrer')
  if (!previewWindow) {
    return false
  }

  const reportBlob = new Blob([snapshot.content], { type: 'text/markdown;charset=utf-8' })
  const reportUrl = window.URL.createObjectURL(reportBlob)
  const html = `<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(snapshot.title)} 미리보기</title>
    <style>
      :root { color-scheme: light; }
      body { margin: 0; font-family: Inter, system-ui, sans-serif; background: #f4f6f8; color: #16202b; }
      .shell { max-width: 960px; margin: 0 auto; padding: 32px 20px 56px; }
      .card { background: #fff; border: 1px solid #dde4ec; border-radius: 24px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08); overflow: hidden; }
      .header { padding: 24px 28px; border-bottom: 1px solid #e8edf3; display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
      .header h1 { margin: 0; font-size: 1.4rem; }
      .meta { margin-top: 6px; color: #607080; font-size: 0.9rem; }
      .actions { display: flex; gap: 10px; flex-wrap: wrap; }
      .button { display: inline-flex; align-items: center; justify-content: center; min-height: 42px; padding: 0 16px; border-radius: 12px; border: 1px solid #d6dee8; background: #fff; color: #16202b; text-decoration: none; font-weight: 700; }
      .button--primary { background: #1f5ca8; border-color: #1f5ca8; color: #fff; }
      pre { margin: 0; padding: 28px; white-space: pre-wrap; word-break: break-word; line-height: 1.7; font-size: 0.95rem; }
      @media (max-width: 720px) { .header { padding: 20px; display: grid; } pre { padding: 20px; } }
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="card">
        <header class="header">
          <div>
            <h1>${escapeHtml(snapshot.title)}</h1>
            <div class="meta">생성 시각 ${escapeHtml(new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(snapshot.createdAt)))}</div>
          </div>
          <div class="actions">
            <a class="button button--primary" href="${reportUrl}" download="${escapeHtml(snapshot.fileName)}">다운로드</a>
            <button class="button" type="button" onclick="window.print()">인쇄</button>
          </div>
        </header>
        <pre>${escapeHtml(snapshot.content)}</pre>
      </section>
    </main>
  </body>
</html>`

  previewWindow.document.open()
  previewWindow.document.write(html)
  previewWindow.document.close()
  return true
}
