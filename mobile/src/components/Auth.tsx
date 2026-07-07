import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonHeader,
  IonInput,
  IonPage,
  IonText,
  IonTitle,
  IonToolbar,
} from '@ionic/react'
import { API_URL } from '../config/api'
import { BrandTitle } from './BrandTitle'
import { apiFetch, setToken } from '../services/apiClient'

type Mode = 'login' | 'signup'
type Strength = { label: string; level: 'weak' | 'medium' | 'strong' }

function passwordStrength(password: string): Strength {
  let score = 0
  if (password.length >= 8) score += 1
  if (password.length >= 12) score += 1
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1
  if (/\d/.test(password)) score += 1
  if (/[^a-zA-Z0-9]/.test(password)) score += 1

  if (score <= 2) return { label: 'Fraca', level: 'weak' }
  if (score <= 4) return { label: 'Media', level: 'medium' }
  return { label: 'Forte', level: 'strong' }
}

function parseError(error: unknown) {
  return error instanceof Error ? error.message : 'Erro de conexao.'
}

export function Auth({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isSignup = mode === 'signup'
  const strength = passwordStrength(password)
  const passwordType = showPassword ? 'text' : 'password'

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    if (isSignup) {
      if (password.length < 8) {
        setError('A senha deve ter pelo menos 8 caracteres.')
        return
      }

      if (password !== confirmPassword) {
        setError('As senhas nao coincidem.')
        return
      }
    }

    setIsSubmitting(true)
    try {
      const endpoint = isSignup ? '/auth/signup' : '/auth/login'
      const body = isSignup ? { email, password, phone } : { email, password }
      const response = await apiFetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({})) as { detail?: unknown }
        throw new Error(typeof errorData.detail === 'string' ? errorData.detail : `Erro (${response.status})`)
      }

      const data = await response.json() as { access_token: string }
      setToken(data.access_token)
      onAuthenticated(data.access_token)
    } catch (submitError) {
      setError(parseError(submitError))
    } finally {
      setIsSubmitting(false)
    }
  }

  function toggleMode() {
    setMode((current) => current === 'login' ? 'signup' : 'login')
    setError(null)
    setConfirmPassword('')
  }

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>
            <BrandTitle />
          </IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen className="ion-padding auth-content">
        <IonCard className="auth-card">
          <IonCardHeader>
            <IonCardTitle>{isSignup ? 'Criar conta' : 'Entrar'}</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            {error && (
              <div className="inline-alert" role="alert">
                {error}
              </div>
            )}

            <form className="auth-form" onSubmit={handleSubmit}>
              <IonInput
                label="E-mail"
                labelPlacement="stacked"
                type="email"
                value={email}
                autocomplete="email"
                required
                onIonInput={(event) => setEmail(String(event.detail.value ?? ''))}
              />

              {isSignup && (
                <IonInput
                  label="Telefone"
                  labelPlacement="stacked"
                  type="tel"
                  value={phone}
                  placeholder="(11) 91234-5678"
                  autocomplete="tel"
                  required
                  onIonInput={(event) => setPhone(String(event.detail.value ?? ''))}
                />
              )}

              <IonInput
                label="Senha"
                labelPlacement="stacked"
                type={passwordType}
                value={password}
                autocomplete={isSignup ? 'new-password' : 'current-password'}
                required
                onIonInput={(event) => setPassword(String(event.detail.value ?? ''))}
              />

              {isSignup && password.length > 0 && (
                <div className="password-meter" data-strength={strength.level} data-testid="password-strength">
                  <span />
                  <IonText>Forca: {strength.label}</IonText>
                </div>
              )}

              {isSignup && (
                <IonInput
                  label="Confirmar senha"
                  labelPlacement="stacked"
                  type={passwordType}
                  value={confirmPassword}
                  autocomplete="new-password"
                  required
                  onIonInput={(event) => setConfirmPassword(String(event.detail.value ?? ''))}
                />
              )}

              <IonButton fill="clear" type="button" onClick={() => setShowPassword((current) => !current)}>
                {showPassword ? 'Ocultar senha' : 'Mostrar senha'}
              </IonButton>

              <IonButton expand="block" type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Aguarde...' : isSignup ? 'Cadastrar' : 'Entrar'}
              </IonButton>
            </form>

            <IonButton className="auth-switch" expand="block" fill="clear" type="button" onClick={toggleMode}>
              {isSignup ? 'Ja tenho conta' : 'Criar conta'}
            </IonButton>
          </IonCardContent>
        </IonCard>
      </IonContent>
    </IonPage>
  )
}
