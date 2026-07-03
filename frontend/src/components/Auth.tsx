import { useState } from 'react'
import { API_URL, apiFetch, setToken } from '../config/api'

type Mode = 'login' | 'signup'

type Strength = { label: string; level: 'fraca' | 'media' | 'forte' }

/** Medidor simples de força: pontua tamanho + variedade de caracteres. Só informativo (não bloqueia). */
function passwordStrength(pw: string): Strength {
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++
  if (/\d/.test(pw)) score++
  if (/[^a-zA-Z0-9]/.test(pw)) score++
  if (score <= 2) return { label: 'Fraca', level: 'fraca' }
  if (score <= 4) return { label: 'Média', level: 'media' }
  return { label: 'Forte', level: 'forte' }
}

const STRENGTH_STYLE: Record<Strength['level'], { color: string; width: string }> = {
  fraca: { color: '#dc2626', width: '33%' },
  media: { color: '#f59e0b', width: '66%' },
  forte: { color: '#16a34a', width: '100%' },
}

const inputStyle = { width: '100%', padding: '0.5rem 0.75rem', border: '1px solid var(--border-color)', borderRadius: '6px' }

export function Auth({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [phone, setPhone] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const strength = passwordStrength(password)
  const pwType = showPassword ? 'text' : 'password'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (mode === 'signup') {
      if (password.length < 8) {
        setError('A senha deve ter pelo menos 8 caracteres.')
        return
      }
      if (password !== confirmPassword) {
        setError('As senhas não coincidem.')
        return
      }
    }

    setIsSubmitting(true)
    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/signup'
      const body = mode === 'signup' ? { email, password, phone } : { email, password }
      const response = await apiFetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
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

  const eyeButton = (
    <button
      type="button"
      onClick={() => setShowPassword(s => !s)}
      aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
      style={{ position: 'absolute', right: '0.5rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem', padding: 0 }}
    >
      {showPassword ? '🙈' : '👁'}
    </button>
  )

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
            style={inputStyle}
          />
        </div>

        {mode === 'signup' && (
          <div style={{ marginBottom: '0.75rem' }}>
            <label htmlFor="auth-phone" style={{ display: 'block', marginBottom: '0.25rem' }}>Telefone</label>
            <input
              id="auth-phone"
              type="tel"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              required
              placeholder="(11) 91234-5678"
              style={inputStyle}
            />
          </div>
        )}

        <div style={{ marginBottom: mode === 'signup' && password.length > 0 ? '0.5rem' : '1rem' }}>
          <label htmlFor="auth-password" style={{ display: 'block', marginBottom: '0.25rem' }}>Senha</label>
          <div style={{ position: 'relative' }}>
            <input
              id="auth-password"
              type={pwType}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{ ...inputStyle, paddingRight: '2.5rem' }}
            />
            {eyeButton}
          </div>
        </div>

        {/* Medidor de força — só no cadastro e enquanto há senha digitada. Apenas informativo. */}
        {mode === 'signup' && password.length > 0 && (
          <div data-testid="password-strength" style={{ marginBottom: '1rem' }}>
            <div style={{ height: '6px', background: 'var(--border-color)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: STRENGTH_STYLE[strength.level].width, background: STRENGTH_STYLE[strength.level].color, transition: 'width 0.2s' }} />
            </div>
            <span style={{ fontSize: '0.8rem', color: STRENGTH_STYLE[strength.level].color }}>
              Força: {strength.label}
            </span>
          </div>
        )}

        {mode === 'signup' && (
          <div style={{ marginBottom: '1rem' }}>
            <label htmlFor="auth-confirm-password" style={{ display: 'block', marginBottom: '0.25rem' }}>Confirmar senha</label>
            <input
              id="auth-confirm-password"
              type={pwType}
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              style={inputStyle}
            />
          </div>
        )}

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
