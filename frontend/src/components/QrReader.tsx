import { useEffect, useRef, useState } from 'react'
import { Html5QrcodeScanner } from 'html5-qrcode'
import { parseNfceQr, type NfceData } from '../utils/parseNfceQr'

// @ts-ignore
const API_URL = (import.meta.env && import.meta.env.VITE_API_URL) || 'https://comparador-precos-yiqd.onrender.com'
const SCANNER_ID = 'qr-reader-container'

export interface IssuerData {
  name: string
  cnpj: string
  address: string
}

export interface ItemData {
  code: string
  description: string
  qty: number
  unit: string
  unit_price: number
  total: number
}

export interface TotalsData {
  total: number
  paid: number
  items_count: number
}

export interface InvoiceData {
  model: string
  series: string
  number: string
  issued_at: string
}

export interface ReceiptData {
  access_key: string
  url: string
  issuer: IssuerData
  items: ItemData[]
  totals: TotalsData
  invoice: InvoiceData
}

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
      () => {}, // erros de frame individuais são ignorados; só o sucesso importa
    )

    return () => {
      scanner.clear().catch(() => {})
    }
  }, [onScan])

  return (
    <div>
      <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
        Aponte a câmera para o QR Code do cupom fiscal
      </p>
      <div id={SCANNER_ID} />
    </div>
  )
}

function ResultView({
  receipt,
  onReset,
  onSave,
  isSaving,
  saveStatus,
  saveError,
}: {
  receipt: ReceiptData
  onReset: () => void
  onSave: () => void
  isSaving: boolean
  saveStatus: 'idle' | 'success' | 'error'
  saveError: string | null
}) {
  return (
    <div className="card">
      <div className="receipt-header">
        <h2 className="store-name" data-testid="store-name">
          {receipt.issuer.name}
        </h2>
        <div className="store-meta">
          <p>CNPJ: {receipt.issuer.cnpj}</p>
          <p>{receipt.issuer.address}</p>
          <p style={{ marginTop: '0.5rem' }}>
            <strong>Emissão:</strong> {new Date(receipt.invoice.issued_at).toLocaleString('pt-BR')}
          </p>
        </div>
      </div>

      <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '1rem 0 0.5rem' }}>Itens da Nota</h3>
      <div className="items-table-container">
        <table className="items-table">
          <thead>
            <tr>
              <th>Produto</th>
              <th style={{ textAlign: 'right' }}>Qtd</th>
              <th style={{ textAlign: 'right' }}>Unit</th>
              <th style={{ textAlign: 'right' }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {receipt.items.map((item, index) => (
              <tr key={index} data-testid="receipt-item">
                <td>
                  <div className="item-desc">{item.description}</div>
                  <div className="item-meta">Cód: {item.code}</div>
                </td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {item.qty} {item.unit}
                </td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {item.unit_price.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                </td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {item.total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="receipt-totals">
        <div className="total-row">
          <span>Qtd. total de itens:</span>
          <span>{receipt.totals.items_count}</span>
        </div>
        <div className="total-row grand-total">
          <span>Valor total:</span>
          <span data-testid="total-paid">
            {receipt.totals.paid.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
          </span>
        </div>
      </div>

      {saveStatus === 'success' && (
        <div className="alert alert-success" role="alert" style={{ marginBottom: '1.5rem' }}>
          <strong>Sucesso!</strong> Nota fiscal salva com sucesso no banco de dados.
        </div>
      )}

      {saveStatus === 'error' && (
        <div className="alert alert-danger" role="alert" style={{ marginBottom: '1.5rem' }}>
          <strong>Erro:</strong> {saveError || 'Não foi possível salvar a nota fiscal.'}
        </div>
      )}

      <div className="actions-grid">
        {saveStatus !== 'success' && (
          <button
            className="btn btn-primary"
            onClick={onSave}
            disabled={isSaving}
            data-testid="save-btn"
          >
            {isSaving ? 'Salvando...' : 'Salvar'}
          </button>
        )}
        <button className="btn btn-outline" onClick={onReset} disabled={isSaving}>
          Escanear novamente
        </button>
      </div>
    </div>
  )
}

export function QrReader() {
  const [status, setStatus] = useState<'scanning' | 'loading' | 'success' | 'error'>('scanning')
  const [receipt, setReceipt] = useState<ReceiptData | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [scanKey, setScanKey] = useState(0)

  async function handleScan(data: NfceData | null) {
    if (!data) {
      setErrorMsg('QR Code não reconhecido como NFC-e. Tente novamente.')
      setStatus('error')
      return
    }

    setStatus('loading')
    setErrorMsg(null)
    setSaveStatus('idle')
    setSaveError(null)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => {
      controller.abort()
    }, 60000)

    try {
      const response = await fetch(`${API_URL}/receipts?url=${encodeURIComponent(data.url)}`, {
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

      if (!response.ok) {
        if (response.status === 504) {
          throw new Error('Timeout ao acessar a SEFAZ. Tente novamente mais tarde.')
        }
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Erro do servidor (${response.status})`)
      }

      const receiptData = await response.json()
      setReceipt(receiptData)
      setStatus('success')
    } catch (err: any) {
      clearTimeout(timeoutId)
      if (err.name === 'AbortError') {
        setErrorMsg('O servidor demorou muito para responder (Timeout). Tente novamente.')
      } else {
        setErrorMsg(err.message || 'Erro de conexão com o servidor.')
      }
      setStatus('error')
    }
  }

  async function handleSave() {
    if (!receipt) return
    setIsSaving(true)
    setSaveStatus('idle')
    setSaveError(null)

    try {
      const response = await fetch(`${API_URL}/receipts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(receipt),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Erro ao salvar (${response.status})`)
      }

      setSaveStatus('success')
    } catch (err: any) {
      setSaveError(err.message || 'Erro de conexão ao salvar a nota.')
      setSaveStatus('error')
    } finally {
      setIsSaving(false)
    }
  }

  function handleReset() {
    setReceipt(null)
    setErrorMsg(null)
    setSaveStatus('idle')
    setSaveError(null)
    setStatus('scanning')
    setScanKey((k) => k + 1)
  }

  if (status === 'loading') {
    return (
      <div className="card loading-container" data-testid="loader">
        <div className="spinner"></div>
        <p className="loading-text">Buscando nota na SEFAZ...</p>
        <p className="loading-subtext">Isso pode levar até 50 segundos no cold start da API.</p>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="card">
        <div className="alert alert-danger" role="alert">
          {errorMsg || 'Ocorreu um erro desconhecido.'}
        </div>
        <button className="btn btn-outline" onClick={handleReset}>
          Escanear novamente
        </button>
      </div>
    )
  }

  if (status === 'success' && receipt) {
    return (
      <ResultView
        receipt={receipt}
        onReset={handleReset}
        onSave={handleSave}
        isSaving={isSaving}
        saveStatus={saveStatus}
        saveError={saveError}
      />
    )
  }

  return (
    <div className="card">
      <ScannerView key={scanKey} onScan={handleScan} />
    </div>
  )
}
