import { Capacitor, CapacitorHttp, type HttpOptions } from '@capacitor/core'

type JsonBody = string | FormData | URLSearchParams | Record<string, unknown> | null | undefined

export interface ApiResponse {
  ok: boolean
  status: number
  json: () => Promise<unknown>
}

function parseBody(body: JsonBody) {
  if (typeof body !== 'string') return body

  try {
    return JSON.parse(body)
  } catch {
    return body
  }
}

export async function apiFetch(url: string, init: RequestInit = {}): Promise<ApiResponse> {
  if (!Capacitor.isNativePlatform()) {
    if (Object.keys(init).length === 0) {
      return fetch(url)
    }

    return fetch(url, init)
  }

  const options: HttpOptions = {
    url,
    method: init.method || 'GET',
    headers: init.headers as Record<string, string> | undefined,
    data: parseBody(init.body as JsonBody),
    connectTimeout: 60000,
    readTimeout: 60000,
  }

  const response = await CapacitorHttp.request(options)

  return {
    ok: response.status >= 200 && response.status < 300,
    status: response.status,
    json: async () => response.data,
  }
}
