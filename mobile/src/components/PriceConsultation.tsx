import { useEffect, useState } from 'react'
import {
  IonAccordion,
  IonAccordionGroup,
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonHeader,
  IonInput,
  IonItem,
  IonLabel,
  IonList,
  IonPage,
  IonSpinner,
  IonTitle,
  IonToolbar,
} from '@ionic/react'
import { API_URL } from '../config/api'
import { apiFetch } from '../services/apiClient'

interface ProductItem {
  description?: string
  normalized_name: string | null
}

export interface PriceData {
  product_id: string
  description: string
  normalized_name: string | null
  unit_price: number
  quantity: number
  unit: string
  total_value: number
  purchase_date: string
  invoice_number: string
  invoice_series: string
  invoice_model: string
  issuer_name: string
  issuer_cnpj: string
  issuer_address: string
  receipt_access_key: string
  receipt_url: string
}

type Status = 'idle' | 'loading' | 'success' | 'empty' | 'error'
type PriceKind = 'latest' | 'lowest'

function formatCurrency(value: number) {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR')
}

function formatDateShort(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR')
}

function productLabel(product: ProductItem) {
  return product.normalized_name || product.description || ''
}

async function fetchPrice(kind: PriceKind, productId: string): Promise<PriceData | null> {
  const response = await apiFetch(`${API_URL}/prices/${kind}?product_id=${encodeURIComponent(productId)}`)
  if (response.status === 404) return null
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(typeof errorData.detail === 'string' ? errorData.detail : `Erro (${response.status})`)
  }
  return response.json() as Promise<PriceData>
}

async function fetchHistory(productId: string): Promise<PriceData[]> {
  const response = await apiFetch(`${API_URL}/prices/history?product_id=${encodeURIComponent(productId)}&limit=50`)
  if (!response.ok) return []
  return response.json() as Promise<PriceData[]>
}

async function fetchProducts(): Promise<ProductItem[]> {
  const response = await apiFetch(`${API_URL}/products`)
  if (!response.ok) return []
  return response.json() as Promise<ProductItem[]>
}

function computeByStore(history: PriceData[]) {
  const seen = new Set<string>()
  const result: { store: string; price: number; date: string }[] = []

  for (const item of history) {
    if (!seen.has(item.issuer_name)) {
      seen.add(item.issuer_name)
      result.push({ store: item.issuer_name, price: item.unit_price, date: item.purchase_date })
    }
  }

  return result.sort((a, b) => a.price - b.price)
}

function PriceResultCard({ price, testId }: { price: PriceData; testId: string }) {
  const displayName = price.normalized_name && price.normalized_name !== price.description
    ? price.normalized_name
    : price.description

  return (
    <article data-testid={testId} className="price-result">
      <strong className="price-value">{formatCurrency(price.unit_price)}</strong>
      <h3>{displayName}</h3>
      {price.normalized_name && price.normalized_name !== price.description && (
        <p className="muted">{price.description}</p>
      )}
      <IonList inset>
        <IonItem>
          <IonLabel>Loja</IonLabel>
          <IonLabel slot="end" className="ion-text-end">{price.issuer_name}</IonLabel>
        </IonItem>
        <IonItem>
          <IonLabel>Compra</IonLabel>
          <IonLabel slot="end" className="ion-text-end">{formatDate(price.purchase_date)}</IonLabel>
        </IonItem>
        <IonItem>
          <IonLabel>Quantidade</IonLabel>
          <IonLabel slot="end">{price.quantity} {price.unit}</IonLabel>
        </IonItem>
        <IonItem>
          <IonLabel>Total</IonLabel>
          <IonLabel slot="end">{formatCurrency(price.total_value)}</IonLabel>
        </IonItem>
      </IonList>
      <a href={price.receipt_url} target="_blank" rel="noreferrer">
        Ver cupom (chave ...{price.receipt_access_key.slice(-8)})
      </a>
    </article>
  )
}

export function PriceConsultation() {
  const [products, setProducts] = useState<ProductItem[]>([])
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<ProductItem | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [latestPrice, setLatestPrice] = useState<PriceData | null>(null)
  const [lowestPrice, setLowestPrice] = useState<PriceData | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [history, setHistory] = useState<PriceData[]>([])

  useEffect(() => {
    fetchProducts().then(setProducts).catch(() => {})
  }, [])

  const filtered = filter.trim().length >= 1
    ? products.filter(product => productLabel(product).toLowerCase().includes(filter.toLowerCase()))
    : products
  const showList = !selected && filtered.length > 0
  const byStore = computeByStore(history)

  async function search(key: string) {
    setStatus('loading')
    setErrorMessage(null)
    setLatestPrice(null)
    setLowestPrice(null)
    setHistory([])

    try {
      const [latest, lowest] = await Promise.all([fetchPrice('latest', key), fetchPrice('lowest', key)])
      setLatestPrice(latest)
      setLowestPrice(lowest)
      setStatus(latest || lowest ? 'success' : 'empty')
      if (latest || lowest) fetchHistory(key).then(setHistory).catch(() => {})
    } catch (error) {
      setStatus('error')
      setErrorMessage(error instanceof Error ? error.message : 'Erro de conexão com o servidor.')
    }
  }

  async function handleSelect(product: ProductItem) {
    setSelected(product)
    setFilter(productLabel(product))
    await search(productLabel(product))
  }

  async function handleSearch() {
    if (!selected) return
    await search(productLabel(selected))
  }

  function handleClear() {
    setFilter('')
    setSelected(null)
    setStatus('idle')
    setLatestPrice(null)
    setLowestPrice(null)
    setErrorMessage(null)
    setHistory([])
  }

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>
            <span className="toolbar-brand">
              <img className="toolbar-logo-small" src="/assets/comparador-precos-logo.png" alt="" />
              Preços
            </span>
          </IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen className="ion-padding">
        <IonCard>
          <IonCardHeader>
            <IonCardTitle aria-hidden="true">Consulta de preços</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <h2 className="section-heading">Consulta de preços</h2>
            <IonInput
              aria-label="Buscar produto"
              label="Buscar produto"
              labelPlacement="stacked"
              value={filter}
              placeholder={products.length === 0 ? 'Carregando produtos...' : 'Digite para filtrar...'}
              disabled={status === 'loading'}
              onIonInput={(event) => {
                const value = String(event.detail.value ?? '')
                setFilter(value)
                if (selected && value !== productLabel(selected)) {
                  setSelected(null)
                  setStatus('idle')
                  setLatestPrice(null)
                  setLowestPrice(null)
                }
              }}
            />

            {showList && (
              <IonList inset className="product-list">
                {filtered.map((product, index) => (
                  <IonItem button key={`${product.normalized_name}-${index}`} onClick={() => handleSelect(product)}>
                    <IonLabel>{productLabel(product)}</IonLabel>
                  </IonItem>
                ))}
              </IonList>
            )}

            <div className="button-row">
              <IonButton expand="block" onClick={handleSearch} disabled={!selected || status === 'loading'}>
                Buscar
              </IonButton>
              <IonButton expand="block" fill="outline" onClick={handleClear} disabled={status === 'loading'}>
                Limpar
              </IonButton>
            </div>

            {products.length === 0 && (
              <p className="muted">Nenhum cupom salvo ainda. Escaneie e salve uma nota primeiro.</p>
            )}
          </IonCardContent>
        </IonCard>

        {status === 'loading' && (
          <IonCard className="loading-card" data-testid="price-loader">
            <IonSpinner name="crescent" />
            <p className="loading-text">Consultando preços...</p>
          </IonCard>
        )}

        {status === 'error' && (
          <div className="inline-alert" role="alert">{errorMessage || 'Não foi possível consultar os preços.'}</div>
        )}

        {status === 'empty' && (
          <div className="inline-alert" role="alert">Nenhum preço encontrado para esse produto.</div>
        )}

        {status === 'success' && (
          <IonAccordionGroup multiple value={['lowest', 'latest']}>
            {lowestPrice && (
              <IonAccordion value="lowest">
                <IonItem slot="header">
                  <IonLabel>Menor preço</IonLabel>
                  <IonBadge slot="end" color="success">{formatCurrency(lowestPrice.unit_price)}</IonBadge>
                </IonItem>
                <div slot="content" className="accordion-content">
                  <PriceResultCard price={lowestPrice} testId="lowest-price-card" />
                </div>
              </IonAccordion>
            )}

            {latestPrice && (
              <IonAccordion value="latest">
                <IonItem slot="header">
                  <IonLabel>Último preço</IonLabel>
                  <IonBadge slot="end">{formatCurrency(latestPrice.unit_price)}</IonBadge>
                </IonItem>
                <div slot="content" className="accordion-content">
                  <PriceResultCard price={latestPrice} testId="latest-price-card" />
                </div>
              </IonAccordion>
            )}

            <IonAccordion value="stores">
              <IonItem slot="header">
                <IonLabel>Por loja</IonLabel>
                {byStore.length > 0 && <IonBadge slot="end">{byStore.length} lojas</IonBadge>}
              </IonItem>
              <IonList slot="content" inset>
                {byStore.length === 0 ? (
                  <IonItem><IonLabel className="muted">Carregando...</IonLabel></IonItem>
                ) : byStore.map((store, index) => (
                  <IonItem key={`${store.store}-${store.date}`}>
                    <IonLabel>
                      <h3>{store.store}</h3>
                      <p>{formatDateShort(store.date)}</p>
                    </IonLabel>
                    <IonBadge color={index === 0 ? 'success' : 'medium'} slot="end">
                      {formatCurrency(store.price)}
                    </IonBadge>
                  </IonItem>
                ))}
              </IonList>
            </IonAccordion>

            <IonAccordion value="history">
              <IonItem slot="header">
                <IonLabel>Histórico completo</IonLabel>
                {history.length > 0 && <IonBadge slot="end">{history.length} registros</IonBadge>}
              </IonItem>
              <IonList slot="content" inset>
                {history.length === 0 ? (
                  <IonItem><IonLabel className="muted">Carregando...</IonLabel></IonItem>
                ) : history.map((item, index) => (
                  <IonItem key={`${item.receipt_access_key}-${index}`}>
                    <IonLabel>
                      <h3>{item.issuer_name}</h3>
                      <p>{formatDateShort(item.purchase_date)}</p>
                    </IonLabel>
                    <IonBadge slot="end">{formatCurrency(item.unit_price)}</IonBadge>
                  </IonItem>
                ))}
              </IonList>
            </IonAccordion>
          </IonAccordionGroup>
        )}
      </IonContent>
    </IonPage>
  )
}
