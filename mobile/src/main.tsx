import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import '@ionic/react/css/core.css'
import '@ionic/react/css/normalize.css'
import '@ionic/react/css/structure.css'
import '@ionic/react/css/typography.css'
import '@ionic/react/css/padding.css'
import '@ionic/react/css/flex-utils.css'
import './index.css'

// Ponto de entrada da aplicação React.
// StrictMode ativa verificações extras em desenvolvimento (dupla renderização intencional).
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
