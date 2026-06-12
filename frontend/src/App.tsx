import { QrReader } from './components/QrReader'

export default function App() {
  return (
    <main style={{ maxWidth: 480, margin: '0 auto', padding: '1rem', fontFamily: 'sans-serif' }}>
      <h1 style={{ fontSize: '1.25rem', marginBottom: '1rem' }}>Comparador de Preços NFC-e</h1>
      <QrReader />
    </main>
  )
}
