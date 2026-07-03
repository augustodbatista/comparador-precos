import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import App from './App'

vi.mock('./components/QrReader', () => ({
  QrReader: () => <div>Scanner mock</div>,
}))

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockClear()
  // Default behavior: resolve with empty response for any fetch
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({}) })
})

describe('App', () => {
  it('mostra a tela de login quando não há token salvo', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /entrar/i })).toBeInTheDocument()
    expect(screen.queryByText('Scanner mock')).not.toBeInTheDocument()
  })

  it('login bem-sucedido revela o app principal', async () => {
    let callCount = 0
    fetchMock.mockImplementation((url: string) => {
      callCount++
      // First call is typically health check, return empty object
      // Second call should be auth login, return token
      if (callCount === 1) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
      }
      if (url.includes('/auth/login')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ access_token: 'tok123', token_type: 'bearer', email: 'user@example.com' }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
    })
    render(<App />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText('Senha'), 'senha1234')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))

    expect(await screen.findByText('Scanner mock')).toBeInTheDocument()
  })

  it('alterna entre scanner e consulta de preços quando autenticado', async () => {
    localStorage.setItem('auth_token', 'tok123')
    render(<App />)

    expect(screen.getByText('Scanner mock')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /preços/i }))

    expect(screen.getByRole('heading', { name: /consulta de preços/i })).toBeInTheDocument()
    expect(screen.queryByText('Scanner mock')).not.toBeInTheDocument()
  })

  it('logout limpa o token e volta pra tela de login', async () => {
    localStorage.setItem('auth_token', 'tok123')
    render(<App />)
    expect(screen.getByText('Scanner mock')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /sair/i }))

    expect(screen.getByRole('heading', { name: /entrar/i })).toBeInTheDocument()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
})
