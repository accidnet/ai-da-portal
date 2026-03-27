export interface HealthcheckResponse {
  status: string
}

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export function getPortalApiBaseUrl(): string {
  return (import.meta.env.VITE_PORTAL_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '')
}

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
