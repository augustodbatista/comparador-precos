import { useCallback, useEffect, useRef, useState } from 'react'
import jsQR from 'jsqr'
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera'
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
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonPage,
  IonSpinner,
  IonTitle,
  IonToolbar,
  IonToast,
} from '@ionic/react'
import { cameraOutline, closeCircleOutline, scanOutline } from 'ionicons/icons'
import { parseNfceQr, type NfceData } from '../utils/parseNfceQr'
import { API_URL } from '../config/api'
import { apiFetch } from '../services/apiClient'
import { errorFeedback, successFeedback, tapFeedback } from '../services/interactionFeedback'
import { BrandTitle } from './BrandTitle'

const SCANNER_ID = 'qr-reader-container'
const SCAN_INTERVAL_MS = 90

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

function ScannerView({ onScan }: { onScan: (data: NfceData | null) => void | Promise<void> }) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const lastScanRef = useRef(0)
  const isScannerVisibleRef = useRef(true)
  const scannedRef = useRef(false)
  const [cameraStatus, setCameraStatus] = useState<'idle' | 'opening' | 'ready' | 'error'>('idle')
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [scanHint, setScanHint] = useState('Abra a camera para iniciar a leitura.')

  const stopCamera = useCallback(() => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null

    if (videoRef.current) {
      videoRef.current.pause()
      videoRef.current.srcObject = null
    }
  }, [])

  const closeCamera = useCallback((message = 'Abra a camera para iniciar a leitura.') => {
    stopCamera()
    scannedRef.current = false
    setCameraStatus('idle')
    setCameraError(null)
    setScanHint(message)
  }, [stopCamera])

  const markScannerHidden = useCallback(() => {
    isScannerVisibleRef.current = false
    closeCamera()
  }, [closeCamera])

  const markScannerVisible = useCallback(() => {
    isScannerVisibleRef.current = true
  }, [])

  useEffect(() => {
    function handleVisibilityChange() {
      if (document.hidden) {
        markScannerHidden()
      } else {
        markScannerVisible()
      }
    }

    function handleTabsWillChange(event: Event) {
      const nextTab = (event as CustomEvent<{ tab?: string }>).detail?.tab
      if (!nextTab) return
      if (nextTab === 'scanner') {
        markScannerVisible()
      } else {
        markScannerHidden()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    document.addEventListener('ionTabsWillChange', handleTabsWillChange)
    window.addEventListener('pagehide', markScannerHidden)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      document.removeEventListener('ionTabsWillChange', handleTabsWillChange)
      window.removeEventListener('pagehide', markScannerHidden)
      stopCamera()
    }
  }, [markScannerHidden, markScannerVisible, stopCamera])

  function decodeCanvas(width: number, height: number) {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d', { willReadFrequently: true })
    if (!canvas || !context) return null

    const imageData = context.getImageData(0, 0, width, height)
    return jsQR(imageData.data, width, height, { inversionAttempts: 'attemptBoth' })
  }

  async function handleDecodedText(text: string) {
    const data = parseNfceQr(text)

    if (!data) {
      setScanHint('QR encontrado, mas nao parece ser NFC-e. Tente enquadrar o QR do cupom fiscal.')
      return
    }

    scannedRef.current = true
    setScanHint('QR lido. Buscando nota...')
    stopCamera()
    await onScan(data)
  }

  function scanFrame() {
    const video = videoRef.current
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d', { willReadFrequently: true })

    if (!video || !canvas || !context || scannedRef.current) return

    const now = performance.now()
    const width = video.videoWidth
    const height = video.videoHeight

    if (width > 0 && height > 0 && now - lastScanRef.current >= SCAN_INTERVAL_MS) {
      lastScanRef.current = now
      setScanHint('Procurando QR Code...')

      const cropSize = Math.floor(Math.min(width, height) * 0.92)
      const cropX = Math.floor((width - cropSize) / 2)
      const cropY = Math.floor((height - cropSize) / 2)

      canvas.width = cropSize
      canvas.height = cropSize
      context.drawImage(video, cropX, cropY, cropSize, cropSize, 0, 0, cropSize, cropSize)

      const croppedResult = decodeCanvas(cropSize, cropSize)
      if (croppedResult?.data) {
        void handleDecodedText(croppedResult.data)
        return
      }

      canvas.width = width
      canvas.height = height
      context.drawImage(video, 0, 0, width, height)

      const fullFrameResult = decodeCanvas(width, height)
      if (fullFrameResult?.data) {
        void handleDecodedText(fullFrameResult.data)
        return
      }
    }

    animationFrameRef.current = requestAnimationFrame(scanFrame)
  }

  async function scanImageSource(imageUrl: string, revokeAfterScan = false) {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d', { willReadFrequently: true })
    if (!canvas || !context) return

    const image = new Image()

    try {
      setScanHint('Lendo imagem...')
      await new Promise<void>((resolve, reject) => {
        image.onload = () => resolve()
        image.onerror = () => reject(new Error('Nao foi possivel carregar a imagem.'))
        image.src = imageUrl
      })

      const maxSize = 1800
      const scale = Math.min(1, maxSize / Math.max(image.naturalWidth, image.naturalHeight))
      const width = Math.max(1, Math.floor(image.naturalWidth * scale))
      const height = Math.max(1, Math.floor(image.naturalHeight * scale))
      canvas.width = width
      canvas.height = height
      context.drawImage(image, 0, 0, width, height)

      const result = decodeCanvas(width, height)
      if (!result?.data) {
        setCameraStatus('error')
        setCameraError('Nao consegui ler QR Code nessa imagem. Tente tirar a foto mais perto e com boa luz.')
        return
      }

      await handleDecodedText(result.data)
    } catch (error) {
      setCameraStatus('error')
      setCameraError(formatError(error, 'Nao foi possivel ler a imagem.'))
    } finally {
      if (revokeAfterScan) URL.revokeObjectURL(imageUrl)
    }
  }

  async function openNativeCamera() {
    void tapFeedback()
    try {
      stopCamera()
      isScannerVisibleRef.current = true
      setCameraStatus('opening')
      setCameraError(null)
      setScanHint('Abrindo camera do Android...')

      const photo = await Camera.getPhoto({
        quality: 100,
        correctOrientation: true,
        resultType: CameraResultType.DataUrl,
        source: CameraSource.Camera,
        saveToGallery: false,
      })

      if (!photo.dataUrl) {
        throw new Error('A camera nao retornou uma imagem para leitura.')
      }

      if (!isScannerVisibleRef.current) return
      await scanImageSource(photo.dataUrl)
    } catch (error) {
      setCameraStatus('error')
      setCameraError(formatError(error, 'Nao foi possivel abrir a camera do Android.'))
      setScanHint('Tente novamente com boa luz e o QR Code preenchendo bem a foto.')
    }
  }

  async function startScanner() {
    void tapFeedback()
    stopCamera()
    isScannerVisibleRef.current = true
    setCameraStatus('opening')
    setCameraError(null)
    setScanHint('Abrindo camera...')
    scannedRef.current = false

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraStatus('error')
      setCameraError('Este Android/WebView nao liberou acesso a camera para o app.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      })

      if (!isScannerVisibleRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }

      const video = videoRef.current
      if (!video) {
        stream.getTracks().forEach((track) => track.stop())
        throw new Error('Preview da camera nao encontrado.')
      }

      streamRef.current = stream
      video.srcObject = stream
      video.setAttribute('playsinline', 'true')
      await video.play()
      setCameraStatus('ready')
      setScanHint('Aponte para o QR Code e mantenha o celular parado.')
      animationFrameRef.current = requestAnimationFrame(scanFrame)
    } catch (error) {
      stopCamera()
      setCameraStatus('error')
      setCameraError(formatError(error, 'Nao foi possivel abrir a camera.'))
    }
  }

  return (
    <IonCard>
      <IonCardHeader>
        <IonCardTitle>Scanner NFC-e</IonCardTitle>
      </IonCardHeader>
      <IonCardContent>
        <p className="muted centered">Aponte a câmera para o QR Code do cupom fiscal</p>
        <div className="scanner-actions">
          {cameraStatus !== 'ready' && (
            <IonButton
              expand="block"
              onClick={startScanner}
              disabled={cameraStatus === 'opening'}
              data-testid="open-camera-btn"
            >
              <IonIcon icon={scanOutline} slot="start" />
              {cameraStatus === 'opening' ? 'Abrindo camera...' : 'Abrir camera'}
            </IonButton>
          )}
          {cameraStatus === 'ready' && (
            <IonButton
              expand="block"
              fill="outline"
              onClick={() => {
                void tapFeedback()
                closeCamera('Camera fechada.')
              }}
            >
              <IonIcon icon={closeCircleOutline} slot="start" />
              Fechar camera
            </IonButton>
          )}
          <IonButton
            expand="block"
            fill="outline"
            onClick={openNativeCamera}
          >
            <IonIcon icon={cameraOutline} slot="start" />
            Abrir camera do Android
          </IonButton>
        </div>
        {cameraStatus === 'error' && (
          <div className="inline-alert" role="alert">
            {cameraError}
          </div>
        )}
        <p className="scanner-hint" aria-live="polite">{scanHint}</p>
        <div id={SCANNER_ID} className="scanner-box">
          <video
            ref={videoRef}
            className="scanner-video"
            muted
            playsInline
            data-testid="scanner-video"
          />
          <div className="scanner-frame" aria-hidden="true" />
          <canvas ref={canvasRef} className="scanner-canvas" aria-hidden="true" />
        </div>
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
            {receipt.items.map((item) => (
              <IonItem key={`${item.code}-${item.description}-${item.total}`} data-testid="receipt-item">
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
    if (!receipt || isSaving || saveStatus === 'success' || saveStatus === 'already_saved') return
    void tapFeedback()
    setIsSaving(true)
    setSaveStatus('idle')
    setSaveError(null)

    try {
      const response = await apiFetch(`${API_URL}/receipts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(receipt),
        timeoutMs: 45000,
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({})) as { detail?: unknown }
        throw new Error(typeof errData.detail === 'string' ? errData.detail : `Erro ao salvar (${response.status})`)
      }

      setSaveStatus(response.status === 201 ? 'success' : 'already_saved')
      void successFeedback()
    } catch (error) {
      setSaveError(formatError(error, 'Erro de conexão ao salvar a nota.'))
      setSaveStatus('error')
      void errorFeedback()
    } finally {
      setIsSaving(false)
    }
  }

  function handleReset() {
    void tapFeedback()
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
            <BrandTitle />
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
