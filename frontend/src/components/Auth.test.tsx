import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { Auth } from './Auth'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  fetchMock.mockClear()
})

describe('Auth', () => {
  it('renderiza o modo login por padrão', () => {
    render(<Auth onAuthenticated={vi.fn()} />)
    expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument()
  })

  it('alterna para o modo cadastro e volta', async () => {
    render(<Auth onAuthenticated={vi.fn()} />)
    await userEvent.click(screen.getByText(/criar conta/i))
    expect(screen.getByRole('button', { name: /cadastrar/i })).toBeInTheDocument()

    await userEvent.click(screen.getByText(/já tenho conta/i))
    expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument()
  })

  it('login bem-sucedido chama onAuthenticated com token e email', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ access_token: 'tok123', token_type: 'bearer', email: 'user@example.com' }),
    })
    const onAuthenticated = vi.fn()
    render(<Auth onAuthenticated={onAuthenticated} />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senha1234')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))

    await waitFor(() => {
      expect(onAuthenticated).toHaveBeenCalledWith('tok123')
    })
  })

  it('exibe erro em credenciais inválidas', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'E-mail ou senha inválidos' }),
    })
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senhaerrada')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/e-mail ou senha inválidos/i)
    })
  })

  it('exibe erro em cadastro com email duplicado', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ detail: 'E-mail já cadastrado' }),
    })
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.click(screen.getByText(/criar conta/i))
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senha1234')
    await userEvent.click(screen.getByRole('button', { name: /cadastrar/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/e-mail já cadastrado/i)
    })
  })

  it('desabilita o botão enquanto a requisição está pendente', async () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}))
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senha1234')
    const btn = screen.getByRole('button', { name: /entrar/i })
    await userEvent.click(btn)

    expect(btn).toBeDisabled()
  })
})
