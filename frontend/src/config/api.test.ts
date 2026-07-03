import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiFetch, getToken, setToken, clearToken, setUnauthorizedHandler } from './api'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockClear()
  fetchMock.mockResolvedValue({ status: 200, ok: true })
  setUnauthorizedHandler(() => {})
})

afterEach(() => {
  localStorage.clear()
})

describe('token storage', () => {
  it('getToken retorna null quando não há token salvo', () => {
    expect(getToken()).toBeNull()
  })

  it('setToken/getToken fazem roundtrip', () => {
    setToken('abc123')
    expect(getToken()).toBe('abc123')
  })

  it('clearToken remove o token salvo', () => {
    setToken('abc123')
    clearToken()
    expect(getToken()).toBeNull()
  })
})

describe('apiFetch', () => {
  it('não anexa Authorization quando não há token', async () => {
    await apiFetch('https://api.test/x')
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBeNull()
  })

  it('anexa Authorization: Bearer quando há token', async () => {
    setToken('meutoken')
    await apiFetch('https://api.test/x')
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer meutoken')
  })

  it('chama o handler de unauthorized e limpa o token numa resposta 401', async () => {
    setToken('meutoken')
    fetchMock.mockResolvedValueOnce({ status: 401, ok: false })
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await apiFetch('https://api.test/x')

    expect(handler).toHaveBeenCalledOnce()
    expect(getToken()).toBeNull()
  })

  it('não chama o handler numa resposta 200', async () => {
    setToken('meutoken')
    fetchMock.mockResolvedValueOnce({ status: 200, ok: true })
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await apiFetch('https://api.test/x')

    expect(handler).not.toHaveBeenCalled()
  })
})
