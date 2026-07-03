// URL base da API. Em desenvolvimento local usa a variável de ambiente VITE_API_URL;
// em produção (Vercel), cai no fallback apontando para o backend no Render.
export const API_URL = import.meta.env.VITE_API_URL || 'https://comparador-precos-yiqd.onrender.com'

const TOKEN_KEY = 'auth_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

/** Wrapper de fetch: injeta Authorization automaticamente e trata 401 globalmente. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(input, { ...init, headers })
  if (response.status === 401) {
    clearToken()
    onUnauthorized?.()
  }
  return response
}
