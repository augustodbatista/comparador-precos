import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const fetchMock = vi.fn()

vi.mock('./components/QrReader', () => ({
  QrReader: () => <div>Scanner mock</div>,
}))

describe('App', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.pushState({}, '', '/')
    localStorage.clear()
    localStorage.setItem('auth_token', 'test-token')
  })

  it('alterna entre scanner e consulta de preços', async () => {
    render(<App />)

    expect(await screen.findByText('Scanner mock')).toBeInTheDocument()

    const pricesTab = document.querySelector('ion-tab-button[tab="prices"]')
    expect(pricesTab).not.toBeNull()
    await userEvent.click(pricesTab!)

    expect(await screen.findByRole('heading', { name: /consulta de pre/i })).toBeInTheDocument()
    expect(screen.queryByText('Scanner mock')).not.toBeInTheDocument()
  })

  it('limpa o token e volta para o login ao sair', async () => {
    render(<App />)

    expect(await screen.findByText('Scanner mock')).toBeInTheDocument()

    const logoutTab = document.querySelector('ion-tab-button[tab="logout"]')
    expect(logoutTab).not.toBeNull()
    await userEvent.click(logoutTab!)

    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(await screen.findByRole('heading', { name: /entrar/i })).toBeInTheDocument()
  })
})
