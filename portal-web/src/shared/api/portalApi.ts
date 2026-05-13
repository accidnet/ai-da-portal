export interface HealthcheckResponse {
  status: string
}

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

/** 백엔드 API 기준 URL을 환경 변수 기준으로 계산합니다. */
export function getPortalApiBaseUrl(): string {
  return (import.meta.env.VITE_PORTAL_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '')
}

/** FastAPI 오류 응답에서 사용자에게 보여줄 detail 값을 추출합니다. */
export async function readPortalApiErrorDetail(response: Response): Promise<string> {
  try {
    const errorBody = (await response.json()) as { detail?: string }
    return errorBody.detail?.trim() ?? ''
  } catch {
    return ''
  }
}

/** 포털 백엔드 연결 상태를 확인합니다. */
export async function fetchHealthcheck(signal?: AbortSignal): Promise<HealthcheckResponse> {
  const response = await fetch(`${getPortalApiBaseUrl()}/api/v1/health`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(`Healthcheck failed with status ${response.status}`)
  }

  return (await response.json()) as HealthcheckResponse
}
