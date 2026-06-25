import { useState } from 'react'
import { QrReader } from './components/QrReader'
import { PriceConsultation } from './components/PriceConsultation'
import { ReceiptHistory } from './components/ReceiptHistory'

// Tipo que controla qual tela está ativa na navegação por abas
type AppView = 'scanner' | 'prices' | 'history'

export default function App() {
  // Estado da aba ativa — inicia na tela de scanner
  const [activeView, setActiveView] = useState<AppView>('scanner')

  return (
    <main className="app-container">
      <header className="app-header">
        <img
          className="app-logo"
          src="/assets/comparador-precos-logo.png"
          alt="Comparador de Preços"
        />
        <h1>Comparador de Preços NFC-e</h1>

        {/* Navegação por abas: Scanner, Preços e Histórico */}
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

      {/* Renderiza o componente da aba ativa */}
      {activeView === 'scanner' && <QrReader />}
      {activeView === 'prices' && <PriceConsultation />}
      {activeView === 'history' && <ReceiptHistory />}
    </main>
  )
}
