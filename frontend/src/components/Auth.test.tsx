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
    await userEvent.type(screen.getByLabelText('Senha'), 'senha1234')
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
    await userEvent.type(screen.getByLabelText('Senha'), 'senhaerrada')
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
    await userEvent.type(screen.getByLabelText(/telefone/i), '11912345678')
    await userEvent.type(screen.getByLabelText('Senha'), 'senha1234')
    await userEvent.type(screen.getByLabelText(/confirmar senha/i), 'senha1234')
    await userEvent.click(screen.getByRole('button', { name: /cadastrar/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/e-mail já cadastrado/i)
    })
  })

  it('cadastro envia o telefone no corpo da requisição', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve({ access_token: 'tok', token_type: 'bearer', email: 'user@example.com' }),
    })
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.click(screen.getByText(/criar conta/i))
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/telefone/i), '11912345678')
    await userEvent.type(screen.getByLabelText('Senha'), 'senha1234')
    await userEvent.type(screen.getByLabelText(/confirmar senha/i), 'senha1234')
    await userEvent.click(screen.getByRole('button', { name: /cadastrar/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const signupCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/auth/signup'))!
    const sentBody = JSON.parse(signupCall[1].body)
    expect(sentBody.phone).toBe('11912345678')
    expect(sentBody.email).toBe('user@example.com')
  })

  it('bloqueia o cadastro quando a confirmação de senha não bate', async () => {
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.click(screen.getByText(/criar conta/i))
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/telefone/i), '11912345678')
    await userEvent.type(screen.getByLabelText('Senha'), 'senha1234')
    await userEvent.type(screen.getByLabelText(/confirmar senha/i), 'senha9999')
    await userEvent.click(screen.getByRole('button', { name: /cadastrar/i }))

    expect(screen.getByRole('alert')).toHaveTextContent(/senhas não coincidem/i)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('permite mostrar e ocultar a senha', async () => {
    render(<Auth onAuthenticated={vi.fn()} />)

    // Login: senha começa oculta, botão de olho revela e volta a ocultar
    const pw = screen.getByLabelText('Senha')
    expect(pw).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: /mostrar senha/i }))
    expect(pw).toHaveAttribute('type', 'text')
    await userEvent.click(screen.getByRole('button', { name: /ocultar senha/i }))
    expect(pw).toHaveAttribute('type', 'password')

    // O toggle também existe na tela de cadastro
    await userEvent.click(screen.getByText(/criar conta/i))
    expect(screen.getByRole('button', { name: /mostrar senha/i })).toBeInTheDocument()
  })

  it('medidor de força mostra Fraca / Média / Forte conforme a senha no cadastro', async () => {
    render(<Auth onAuthenticated={vi.fn()} />)
    await userEvent.click(screen.getByText(/criar conta/i))
    const pw = screen.getByLabelText('Senha')

    await userEvent.type(pw, 'abc')
    expect(screen.getByTestId('password-strength')).toHaveTextContent(/fraca/i)

    await userEvent.clear(pw)
    await userEvent.type(pw, 'Abcdef1!')
    expect(screen.getByTestId('password-strength')).toHaveTextContent(/média/i)

    await userEvent.clear(pw)
    await userEvent.type(pw, 'Abcdefgh1234!')
    expect(screen.getByTestId('password-strength')).toHaveTextContent(/forte/i)
  })

  it('medidor de força não aparece no modo login', async () => {
    render(<Auth onAuthenticated={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('Senha'), 'Abcdef1!')
    expect(screen.queryByTestId('password-strength')).not.toBeInTheDocument()
  })

  it('desabilita o botão enquanto a requisição está pendente', async () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}))
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText('Senha'), 'senha1234')
    const btn = screen.getByRole('button', { name: /entrar/i })
    await userEvent.click(btn)

    expect(btn).toBeDisabled()
  })
})
