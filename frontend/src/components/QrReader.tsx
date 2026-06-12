import { useEffect, useRef, useState } from 'react'
import { Html5QrcodeScanner } from 'html5-qrcode'
import { parseNfceQr, type NfceData } from '../utils/parseNfceQr'

const SCANNER_ID = 'qr-reader-container'

function ScannerView({ onScan }: { onScan: (data: NfceData | null) => void }) {
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    const scanner = new Html5QrcodeScanner(
      SCANNER_ID,
      { fps: 10, qrbox: { width: 280, height: 280 } },
      false,
    )

    scanner.render(
      (text) => onScan(parseNfceQr(text)),
      () => {},
    )

    return () => {
      scanner.clear().catch(() => {})
    }
  }, [onScan])

  return (
    <div>
      <p style={{ marginBottom: '0.75rem', color: '#555' }}>
        Aponte a câmera para o QR Code do cupom fiscal
      </p>
      <div id={SCANNER_ID} />
    </div>
  )
}

function ResultView({ data, onReset }: { data: NfceData; onReset: () => void }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(data.url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const btnStyle: React.CSSProperties = {
    display: 'block',
    width: '100%',
    padding: '0.75rem',
    marginTop: '0.75rem',
    borderRadius: 8,
    border: 'none',
    cursor: 'pointer',
    fontSize: '1rem',
  }

  return (
    <div>
      <h2 style={{ color: '#1a7a1a', marginBottom: '1rem' }}>QR Code lido com sucesso!</h2>

      <div style={{ marginBottom: '0.75rem' }}>
        <strong>Chave de acesso</strong>
        <p
          data-testid="access-key"
          style={{ wordBreak: 'break-all', background: '#f4f4f4', padding: '0.5rem', borderRadius: 4 }}
        >
          {data.accessKey}
        </p>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <strong>URL da NFC-e</strong>
        <p
          data-testid="nfce-url"
          style={{ wordBreak: 'break-all', background: '#f4f4f4', padding: '0.5rem', borderRadius: 4, fontSize: '0.8rem' }}
        >
          {data.url}
        </p>
      </div>

      <button onClick={handleCopy} style={{ ...btnStyle, background: '#1a7a1a', color: '#fff' }}>
        {copied ? 'Copiado!' : 'Copiar URL'}
      </button>
      <button onClick={onReset} style={{ ...btnStyle, background: '#eee', color: '#333' }}>
        Escanear novamente
      </button>
    </div>
  )
}

export function QrReader() {
  const [scanData, setScanData] = useState<NfceData | null>(null)
  const [hasError, setHasError] = useState(false)
  const [scanKey, setScanKey] = useState(0)

  function handleScan(data: NfceData | null) {
    if (data) {
      setScanData(data)
      setHasError(false)
    } else {
      setHasError(true)
    }
  }

  function handleReset() {
    setScanData(null)
    setHasError(false)
    setScanKey((k) => k + 1)
  }

  if (scanData) return <ResultView data={scanData} onReset={handleReset} />

  return (
    <div>
      {hasError && (
        <p role="alert" style={{ color: '#c00', marginBottom: '0.75rem' }}>
          QR Code não reconhecido como NFC-e. Tente novamente.
        </p>
      )}
      <ScannerView key={scanKey} onScan={handleScan} />
    </div>
  )
}
