import { useState } from 'react'
import { API_URL, apiFetch, setToken } from '../config/api'

type Mode = 'login' | 'signup'

export function Auth({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (mode === 'signup' && password.length < 8) {
      setError('A senha deve ter pelo menos 8 caracteres.')
      return
    }

    setIsSubmitting(true)
    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/signup'
      const response = await apiFetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Erro (${response.status})`)
      }

      const data = await response.json()
      setToken(data.access_token)
      onAuthenticated(data.access_token)
    } catch (err: any) {
      setError(err.message || 'Erro de conexão.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="card" style={{ maxWidth: '360px', margin: '2rem auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>{mode === 'login' ? 'Entrar' : 'Criar conta'}</h2>

      {error && (
        <div className="alert alert-danger" role="alert" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '0.75rem' }}>
          <label htmlFor="auth-email" style={{ display: 'block', marginBottom: '0.25rem' }}>E-mail</label>
          <input
            id="auth-email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            style={{ width: '100%', padding: '0.5rem 0.75rem', border: '1px solid var(--border-color)', borderRadius: '6px' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="auth-password" style={{ display: 'block', marginBottom: '0.25rem' }}>Senha</label>
          <input
            id="auth-password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{ width: '100%', padding: '0.5rem 0.75rem', border: '1px solid var(--border-color)', borderRadius: '6px' }}
          />
        </div>

        <button className="btn btn-primary" type="submit" disabled={isSubmitting} style={{ width: '100%' }}>
          {isSubmitting ? 'Aguarde...' : mode === 'login' ? 'Entrar' : 'Cadastrar'}
        </button>
      </form>

      <button
        type="button"
        onClick={() => { setMode(m => m === 'login' ? 'signup' : 'login'); setError(null) }}
        style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', marginTop: '1rem', width: '100%', textAlign: 'center' }}
      >
        {mode === 'login' ? 'Criar conta' : 'Já tenho conta'}
      </button>
    </div>
  )
}
