import { useEffect, useState } from 'react'
import { QrReader } from './components/QrReader'
import { PriceConsultation } from './components/PriceConsultation'
import { ReceiptHistory } from './components/ReceiptHistory'

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

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('scanner')
  const [dark, toggleTheme] = useDarkMode()

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
