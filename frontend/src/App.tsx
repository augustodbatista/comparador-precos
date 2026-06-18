import { useState } from 'react'
import { QrReader } from './components/QrReader'
import { PriceConsultation } from './components/PriceConsultation'

type AppView = 'scanner' | 'prices'

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('scanner')

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
        </nav>
      </header>

      {activeView === 'scanner' ? <QrReader /> : <PriceConsultation />}
    </main>
  )
}
