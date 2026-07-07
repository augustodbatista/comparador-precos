import { Capacitor, CapacitorHttp, type HttpOptions } from '@capacitor/core'

type JsonBody = string | FormData | URLSearchParams | Record<string, unknown> | null | undefined
type ApiFetchOptions = RequestInit & {
  skipAuth?: boolean
  timeoutMs?: number
}

const TOKEN_KEY = 'auth_token'
let onUnauthorized: (() => void) | null = null
const warmUpRequests = new Map<string, Promise<void>>()

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

export function setUnauthorizedHandler(handler: (() => void) | null): void {
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

function createTimedSignal(timeoutMs?: number) {
  if (!timeoutMs || typeof AbortController === 'undefined') return {}

  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  return { signal: controller.signal, timeoutId }
}

export function warmUpApi(baseUrl: string): Promise<void> {
  if (import.meta.env.MODE === 'test') return Promise.resolve()

  const normalizedBaseUrl = baseUrl.replace(/\/+$/, '')
  const existing = warmUpRequests.get(normalizedBaseUrl)
  if (existing) return existing

  const request = apiFetch(`${normalizedBaseUrl}/health`, {
    skipAuth: true,
    timeoutMs: 10000,
  }).then(() => undefined).catch(() => undefined)

  warmUpRequests.set(normalizedBaseUrl, request)
  return request
}

export async function apiFetch(url: string, init: ApiFetchOptions = {}): Promise<ApiResponse> {
  const { skipAuth, timeoutMs, ...requestInit } = init
  const headers = new Headers(init.headers)
  const token = skipAuth ? null : getToken()

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  if (!Capacitor.isNativePlatform()) {
    const hasRequestInit = Object.keys(requestInit).length > 0
    const timed = requestInit.signal ? {} : createTimedSignal(timeoutMs)

    try {
      const response = token || hasRequestInit || timed.signal
        ? await fetch(url, { ...requestInit, headers, signal: requestInit.signal || timed.signal })
        : await fetch(url)
      if (!skipAuth && response.status === 401) {
        clearToken()
        onUnauthorized?.()
      }
      return response
    } finally {
      if (timed.timeoutId) window.clearTimeout(timed.timeoutId)
    }
  }

  const options: HttpOptions = {
    url,
    method: requestInit.method || 'GET',
    headers: Object.fromEntries(headers.entries()),
    data: parseBody(requestInit.body as JsonBody),
    connectTimeout: timeoutMs || 60000,
    readTimeout: timeoutMs || 60000,
  }

  const response = await CapacitorHttp.request(options)
  if (!skipAuth && response.status === 401) {
    clearToken()
    onUnauthorized?.()
  }

  return {
    ok: response.status >= 200 && response.status < 300,
    status: response.status,
    json: async () => response.data,
  }
}
