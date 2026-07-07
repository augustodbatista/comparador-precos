import { Capacitor, CapacitorHttp, type HttpOptions } from '@capacitor/core'

type JsonBody = string | FormData | URLSearchParams | Record<string, unknown> | null | undefined
const TOKEN_KEY = 'auth_token'
let onUnauthorized: (() => void) | null = null

export interface ApiResponse {
  ok: boolean
  status: number
  json: () => Promise<unknown>
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
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
  const headers = new Headers(init.headers)
  const token = getToken()

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  if (!Capacitor.isNativePlatform()) {
    const response = await fetch(url, { ...init, headers })
    if (response.status === 401) {
      clearToken()
      onUnauthorized?.()
    }
    return response
  }

  const options: HttpOptions = {
    url,
    method: init.method || 'GET',
    headers: Object.fromEntries(headers.entries()),
    data: parseBody(init.body as JsonBody),
    connectTimeout: 60000,
    readTimeout: 60000,
  }

  const response = await CapacitorHttp.request(options)
  if (response.status === 401) {
    clearToken()
    onUnauthorized?.()
  }

  return {
    ok: response.status >= 200 && response.status < 300,
    status: response.status,
    json: async () => response.data,
  }
}
