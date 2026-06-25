import { useEffect, useRef, useState } from 'react'
import { Html5QrcodeScanner } from 'html5-qrcode'
import { parseNfceQr, type NfceData } from '../utils/parseNfceQr'
import { API_URL } from '../config/api'

// ID do elemento HTML onde a biblioteca html5-qrcode injeta a câmera
const SCANNER_ID = 'qr-reader-container'

// ---------------------------------------------------------------------------
// Interfaces — espelham os modelos Pydantic do backend
// ---------------------------------------------------------------------------

export interface IssuerData {
  name: string
  cnpj: string
  address: string
}

export interface ItemData {
  code: string       // código interno da loja
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
  issued_at: string  // formato ISO: "YYYY-MM-DDTHH:MM:SS"
}

export interface ReceiptData {
  access_key: string
  url: string
  issuer: IssuerData
  items: ItemData[]
  totals: TotalsData
  invoice: InvoiceData
}

// ---------------------------------------------------------------------------
// Componente interno: tela de scanner de QR Code
// ---------------------------------------------------------------------------

function ScannerView({ onScan }: { onScan: (data: NfceData | null) => void }) {
  // useRef evita que o scanner seja inicializado duas vezes no StrictMode do React
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    // Inicializa o scanner com câmera a 10 fps e viewfinder de 280x280px
    const scanner = new Html5QrcodeScanner(
      SCANNER_ID,
      { fps: 10, qrbox: { width: 280, height: 280 } },
      false,
    )

    scanner.render(
      (text) => onScan(parseNfceQr(text)),  // sucesso: parseia o QR Code e notifica o pai
      () => {},                              // erro de frame individual: ignorado (ocorre a cada frame sem QR)
    )

    // Cleanup: libera a câmera quando o componente é desmontado
    return () => {
      scanner.clear().catch(() => {})
    }
  }, [onScan])

  return (
    <div>
      <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
        Aponte a câmera para o QR Code do cupom fiscal
      </p>
      {/* O scanner injeta a câmera dentro deste div via o SCANNER_ID */}
      <div id={SCANNER_ID} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Componente interno: tela de resultado após escanear o QR Code
// ---------------------------------------------------------------------------

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
  saveStatus: 'idle' | 'success' | 'already_saved' | 'error'
  saveError: string | null
}) {
  return (
    <div className="card">
      {/* Cabeçalho: nome da loja, CNPJ, endereço e data de emissão */}
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

      {/* Tabela de itens da nota */}
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

      {/* Totais da nota */}
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

      {/* Alertas de resultado do salvamento */}
      {saveStatus === 'success' && (
        <div className="alert alert-success" role="alert" style={{ marginBottom: '1.5rem' }}>
          <strong>Sucesso!</strong> Nota fiscal salva com sucesso no banco de dados.
        </div>
      )}

      {saveStatus === 'already_saved' && (
        <div className="alert alert-info" role="alert" style={{ marginBottom: '1.5rem' }}>
          <strong>Esta nota já estava salva.</strong> Nenhum cupom duplicado foi criado.
        </div>
      )}

      {saveStatus === 'error' && (
        <div className="alert alert-danger" role="alert" style={{ marginBottom: '1.5rem' }}>
          <strong>Erro:</strong> {saveError || 'Não foi possível salvar a nota fiscal.'}
        </div>
      )}

      {/* Botões de ação — Salvar some após sucesso para evitar duplo clique */}
      <div className="actions-grid">
        {saveStatus !== 'success' && saveStatus !== 'already_saved' && (
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

// ---------------------------------------------------------------------------
// Componente principal: gerencia o fluxo completo de scan → exibição → salvamento
// ---------------------------------------------------------------------------

export function QrReader() {
  // Estado da tela: scanning (câmera ativa), loading (buscando na SEFAZ), success, error
  const [status, setStatus] = useState<'scanning' | 'loading' | 'success' | 'error'>('scanning')
  const [receipt, setReceipt] = useState<ReceiptData | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Estados do salvamento (separados do status principal para não esconder o recibo)
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'already_saved' | 'error'>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)

  // Chave para forçar remontagem do ScannerView (reinicia a câmera ao escanear novamente)
  const [scanKey, setScanKey] = useState(0)

  /**
   * Chamado quando o scanner detecta um QR Code.
   * Busca os dados da nota na SEFAZ via GET /receipts?url=...
   * Timeout de 60s no cliente para cobrir o cold start do Render (~50s).
   */
  async function handleScan(data: NfceData | null) {
    if (!data) {
      // QR Code não reconhecido como NFC-e (pode ser outro tipo de QR Code)
      setErrorMsg('QR Code não reconhecido como NFC-e. Tente novamente.')
      setStatus('error')
      return
    }

    setStatus('loading')
    setErrorMsg(null)
    setSaveStatus('idle')
    setSaveError(null)

    // AbortController para cancelar a requisição se ultrapassar 60 segundos
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
        // AbortController disparou — o servidor demorou mais de 60s
        setErrorMsg('O servidor demorou muito para responder (Timeout). Tente novamente.')
      } else {
        setErrorMsg(err.message || 'Erro de conexão com o servidor.')
      }
      setStatus('error')
    }
  }

  /**
   * Chamado quando o usuário clica em "Salvar".
   * Envia o recibo via POST /receipts para persistir no banco com normalização.
   * 201 = cupom novo | 200 = cupom já existia (idempotente).
   */
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

      // 201: cupom salvo agora | 200: cupom já estava no banco (idempotente)
      setSaveStatus(response.status === 201 ? 'success' : 'already_saved')
    } catch (err: any) {
      setSaveError(err.message || 'Erro de conexão ao salvar a nota.')
      setSaveStatus('error')
    } finally {
      setIsSaving(false)
    }
  }

  /**
   * Reseta todos os estados e incrementa scanKey para forçar remontagem do scanner.
   * Incrementar a key faz o React desmontar e remontar o ScannerView, reiniciando a câmera.
   */
  function handleReset() {
    setReceipt(null)
    setErrorMsg(null)
    setSaveStatus('idle')
    setSaveError(null)
    setStatus('scanning')
    setScanKey((k) => k + 1)
  }

  // Tela de carregamento — exibida enquanto busca a nota na SEFAZ
  if (status === 'loading') {
    return (
      <div className="card loading-container" data-testid="loader">
        <div className="spinner"></div>
        <p className="loading-text">Buscando nota na SEFAZ...</p>
        <p className="loading-subtext">Isso pode levar até 50 segundos no cold start da API.</p>
      </div>
    )
  }

  // Tela de erro — exibida se o QR Code for inválido ou a SEFAZ retornar erro
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

  // Tela de resultado — exibida após receber os dados da nota com sucesso
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

  // Tela padrão — scanner de QR Code ativo
  // scanKey força remontagem do ScannerView ao escanear novamente
  return (
    <div className="card">
      <ScannerView key={scanKey} onScan={handleScan} />
    </div>
  )
}
