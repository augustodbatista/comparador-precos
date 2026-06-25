import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

// Ponto de entrada da aplicação React.
// StrictMode ativa verificações extras em desenvolvimento (dupla renderização intencional).
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
