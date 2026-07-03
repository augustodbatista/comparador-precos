import { useEffect, useState } from 'react'
import { QrReader } from './components/QrReader'
import { PriceConsultation } from './components/PriceConsultation'
import { ReceiptHistory } from './components/ReceiptHistory'
import { Auth } from './components/Auth'
import { API_URL, clearToken, getToken, setUnauthorizedHandler } from './config/api'

type AppView = 'scanner' | 'prices' | 'history'

function useDarkMode() {
  const getInitial = () => {
    const stored = localStorage.getItem('theme')
    if (stored === 'dark') return true
    if (stored === 'light') return false
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  const [dark, setDark] = useState(getInitial)

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return [dark, () => setDark(d => !d)] as const
}

function useAuth() {
  const [token, setTokenState] = useState<string | null>(() => getToken())

  useEffect(() => {
    setUnauthorizedHandler(() => setTokenState(null))
  }, [])

  function login(newToken: string) {
    setTokenState(newToken)
  }

  function logout() {
    clearToken()
    setTokenState(null)
  }

  return { token, login, logout }
}

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('scanner')
  const [dark, toggleTheme] = useDarkMode()
  const { token, login, logout } = useAuth()

  // Acorda o backend no Render (free tier dorme após ~15 min sem uso).
  // O ping é fire-and-forget: erros são silenciados. Endpoint público — não exige login.
  useEffect(() => {
    fetch(`${API_URL}/health/ollama`).catch(() => {})
  }, [])

  if (!token) {
    return (
      <main className="app-container">
        <Auth onAuthenticated={login} />
      </main>
    )
  }

  return (
    <main className="app-container">
      <header className="app-header">
        <h1>Comparador de Preços NFC-e</h1>

        <nav className="app-tabs" aria-label="Navegação principal">
          <button
            className={activeView === 'scanner' ? 'app-tab active' : 'app-tab'}
            type="button"
            onClick={() => setActiveView('scanner')}
          >
            Scanner
          </button>
          <button
            className={activeView === 'prices' ? 'app-tab active' : 'app-tab'}
            type="button"
            onClick={() => setActiveView('prices')}
          >
            Preços
          </button>
          <button
            className={activeView === 'history' ? 'app-tab active' : 'app-tab'}
            type="button"
            onClick={() => setActiveView('history')}
          >
            Histórico
          </button>
        </nav>

        <button className="btn btn-outline" type="button" onClick={logout} style={{ marginLeft: 'auto' }}>
          Sair
        </button>
      </header>

      {activeView === 'scanner' && <QrReader />}
      {activeView === 'prices' && <PriceConsultation />}
      {activeView === 'history' && <ReceiptHistory />}

      <button
        className="theme-toggle"
        type="button"
        onClick={toggleTheme}
        aria-label={dark ? 'Ativar modo claro' : 'Ativar modo escuro'}
        title={dark ? 'Modo claro' : 'Modo escuro'}
      >
        {dark ? '☀' : '☾'}
      </button>
    </main>
  )
}
