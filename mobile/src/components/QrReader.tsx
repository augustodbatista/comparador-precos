import { useEffect, useRef, useState } from 'react'
import { Html5QrcodeScanner } from 'html5-qrcode'
import {
  IonAlert,
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonGrid,
  IonHeader,
  IonItem,
  IonLabel,
  IonList,
  IonPage,
  IonSpinner,
  IonTitle,
  IonToolbar,
  IonToast,
} from '@ionic/react'
import { parseNfceQr, type NfceData } from '../utils/parseNfceQr'
import { API_URL } from '../config/api'
import { apiFetch } from '../services/apiClient'

const SCANNER_ID = 'qr-reader-container'

export interface IssuerData {
  name: string
  cnpj: string
  address: string
}

export interface ItemData {
  code: string
  description: string
  normalized_name?: string | null
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

function formatCurrency(value: number) {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
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
      () => {},
    )

    return () => {
      scanner.clear().catch(() => {})
    }
  }, [onScan])

  return (
    <IonCard>
      <IonCardHeader>
        <IonCardTitle>Scanner NFC-e</IonCardTitle>
      </IonCardHeader>
      <IonCardContent>
        <p className="muted centered">Aponte a câmera para o QR Code do cupom fiscal</p>
        <div id={SCANNER_ID} className="scanner-box" />
      </IonCardContent>
    </IonCard>
  )
}

function ResultView({
  receipt,
  onReset,
  onSave,
  isSaving,
  saveStatus,
  saveError,
  ollamaStatus,
}: {
  receipt: ReceiptData
  onReset: () => void
  onSave: () => void
  isSaving: boolean
  saveStatus: 'idle' | 'success' | 'already_saved' | 'error'
  saveError: string | null
  ollamaStatus: 'unknown' | 'ok' | 'offline'
}) {
  return (
    <>
      <IonCard>
        <IonCardHeader>
          <IonCardTitle data-testid="store-name">{receipt.issuer.name}</IonCardTitle>
          <div className="receipt-meta">
            <p>CNPJ: {receipt.issuer.cnpj}</p>
            <p>{receipt.issuer.address}</p>
            <p>Emissão: {new Date(receipt.invoice.issued_at).toLocaleString('pt-BR')}</p>
          </div>
        </IonCardHeader>
        <IonCardContent>
          {ollamaStatus !== 'unknown' && (
            <IonBadge
              color={ollamaStatus === 'ok' ? 'success' : 'warning'}
              data-testid="ollama-badge"
              className="status-badge"
            >
              {ollamaStatus === 'ok'
                ? 'Normalização ativa'
                : 'Normalização inativa: produtos serão salvos sem normalização'}
            </IonBadge>
          )}

          <IonList inset>
            {receipt.items.map((item, index) => (
              <IonItem key={`${item.code}-${index}`} data-testid="receipt-item">
                <IonLabel>
                  <h3>{item.normalized_name || item.description}</h3>
                  {item.normalized_name && item.normalized_name !== item.description && (
                    <p>{item.description}</p>
                  )}
                  <p>Cód: {item.code}</p>
                  <p>{item.qty} {item.unit} x {formatCurrency(item.unit_price)}</p>
                </IonLabel>
                <IonBadge color="primary" slot="end">{formatCurrency(item.total)}</IonBadge>
              </IonItem>
            ))}
          </IonList>

          <div className="receipt-total">
            <span>{receipt.totals.items_count} itens</span>
            <strong data-testid="total-paid">{formatCurrency(receipt.totals.paid)}</strong>
          </div>

          {saveStatus === 'success' && (
            <div className="inline-success" role="alert">
              Nota fiscal salva com sucesso no banco de dados.
            </div>
          )}

          {saveStatus === 'already_saved' && (
            <div className="inline-info" role="alert">
              Esta nota já estava salva. Nenhum cupom duplicado foi criado.
            </div>
          )}

          {saveStatus === 'error' && (
            <div className="inline-alert" role="alert">
              {saveError || 'Não foi possível salvar a nota fiscal.'}
            </div>
          )}

          <IonGrid className="action-grid">
            {saveStatus !== 'success' && saveStatus !== 'already_saved' && (
              <IonButton expand="block" onClick={onSave} disabled={isSaving} data-testid="save-btn">
                {isSaving ? 'Salvando...' : 'Salvar cupom'}
              </IonButton>
            )}
            <IonButton expand="block" fill="outline" onClick={onReset} disabled={isSaving}>
              Escanear novamente
            </IonButton>
          </IonGrid>
        </IonCardContent>
      </IonCard>

      <IonAlert
        isOpen={saveStatus === 'error'}
        header="Erro"
        message={saveError || 'Não foi possível salvar a nota fiscal.'}
        buttons={['OK']}
      />
      <IonToast
        isOpen={saveStatus === 'success'}
        message="Nota fiscal salva com sucesso no banco de dados."
        duration={2500}
        color="success"
      />
      <IonToast
        isOpen={saveStatus === 'already_saved'}
        message="Esta nota já estava salva. Nenhum cupom duplicado foi criado."
        duration={2500}
        color="primary"
      />
    </>
  )
}

export function QrReader() {
  const [status, setStatus] = useState<'scanning' | 'loading' | 'success' | 'error'>('scanning')
  const [receipt, setReceipt] = useState<ReceiptData | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [ollamaStatus, setOllamaStatus] = useState<'unknown' | 'ok' | 'offline'>('unknown')
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'already_saved' | 'error'>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [scanKey, setScanKey] = useState(0)

  useEffect(() => {
    if (status !== 'success') return
    apiFetch(`${API_URL}/health/ollama`)
      .then(r => r.json())
      .then(data => setOllamaStatus((data as { status?: string }).status === 'ok' ? 'ok' : 'offline'))
      .catch(() => setOllamaStatus('offline'))
  }, [status])

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
    const timeoutId = setTimeout(() => controller.abort(), 60000)

    try {
      const response = await apiFetch(`${API_URL}/receipts?url=${encodeURIComponent(data.url)}`, {
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

      if (!response.ok) {
        if (response.status === 504) {
          throw new Error('Timeout ao acessar a SEFAZ. Tente novamente mais tarde.')
        }
        const errData = await response.json().catch(() => ({})) as { detail?: unknown }
        throw new Error(typeof errData.detail === 'string' ? errData.detail : `Erro do servidor (${response.status})`)
      }

      setReceipt(await response.json() as ReceiptData)
      setStatus('success')
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof DOMException && error.name === 'AbortError') {
        setErrorMsg('O servidor demorou muito para responder (Timeout). Tente novamente.')
      } else {
        setErrorMsg(formatError(error, 'Erro de conexão com o servidor.'))
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
      const response = await apiFetch(`${API_URL}/receipts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(receipt),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({})) as { detail?: unknown }
        throw new Error(typeof errData.detail === 'string' ? errData.detail : `Erro ao salvar (${response.status})`)
      }

      setSaveStatus(response.status === 201 ? 'success' : 'already_saved')
    } catch (error) {
      setSaveError(formatError(error, 'Erro de conexão ao salvar a nota.'))
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
    setOllamaStatus('unknown')
    setStatus('scanning')
    setScanKey((key) => key + 1)
  }

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>
            <img className="toolbar-logo" src="/assets/comparador-precos-logo.png" alt="Comparador de Preços" />
          </IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen className="ion-padding">
        {status === 'loading' && (
          <IonCard className="loading-card" data-testid="loader">
            <IonSpinner name="crescent" />
            <p className="loading-text">Buscando nota na SEFAZ...</p>
            <p className="muted centered">Isso pode levar até 50 segundos no cold start da API.</p>
          </IonCard>
        )}

        {status === 'error' && (
          <IonCard>
            <IonCardContent>
              <div className="inline-alert" role="alert">{errorMsg || 'Ocorreu um erro desconhecido.'}</div>
              <IonButton expand="block" fill="outline" onClick={handleReset}>
                Escanear novamente
              </IonButton>
            </IonCardContent>
          </IonCard>
        )}

        {status === 'success' && receipt && (
          <ResultView
            receipt={receipt}
            onReset={handleReset}
            onSave={handleSave}
            isSaving={isSaving}
            saveStatus={saveStatus}
            saveError={saveError}
            ollamaStatus={ollamaStatus}
          />
        )}

        {status === 'scanning' && <ScannerView key={scanKey} onScan={handleScan} />}
      </IonContent>
    </IonPage>
  )
}
