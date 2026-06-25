import { useEffect, useState } from 'react'
import { API_URL } from '../config/api'

interface ProductItem {
  normalized_name: string
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

function productLabel(p: ProductItem) { return p.normalized_name }

async function fetchPrice(kind: PriceKind, productId: string): Promise<PriceData | null> {
  const r = await fetch(`${API_URL}/prices/${kind}?product_id=${encodeURIComponent(productId)}`)
  if (r.status === 404) return null
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Erro (${r.status})`) }
  return r.json()
}

async function fetchHistory(productId: string): Promise<PriceData[]> {
  const r = await fetch(`${API_URL}/prices/history?product_id=${encodeURIComponent(productId)}&limit=50`)
  if (!r.ok) return []
  return r.json()
}

async function fetchProducts(): Promise<ProductItem[]> {
  const r = await fetch(`${API_URL}/products`)
  if (!r.ok) return []
  return r.json()
}

/** Agrupa o histórico por loja e retorna o preço mais recente de cada uma, ordenado pelo menor preço. */
function computeByStore(history: PriceData[]) {
  const seen = new Set<string>()
  const result: { store: string; price: number; date: string }[] = []
  // history já vem ordenado por data desc — primeira ocorrência de cada loja é a mais recente
  for (const h of history) {
    if (!seen.has(h.issuer_name)) {
      seen.add(h.issuer_name)
      result.push({ store: h.issuer_name, price: h.unit_price, date: h.purchase_date })
    }
  }
  return result.sort((a, b) => a.price - b.price)
}

// ---------------------------------------------------------------------------
// Componente auxiliar: seção colapsável com header clicável
// ---------------------------------------------------------------------------

function Section({ title, expanded, onToggle, badge, children }: {
  title: string
  expanded: boolean
  onToggle: () => void
  badge?: string
  children: React.ReactNode
}) {
  return (
    <div className="card" style={{ marginBottom: '0.75rem' }}>
      <button
        type="button"
        onClick={onToggle}
        style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
      >
        <span style={{ fontWeight: 600, fontSize: '1rem' }}>{title}</span>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          {badge && <span style={{ background: '#2563eb', color: '#fff', borderRadius: '99px', padding: '0.1rem 0.5rem', fontSize: '0.75rem' }}>{badge}</span>}
          {expanded ? '▲' : '▼'}
        </span>
      </button>
      {expanded && <div style={{ marginTop: '0.75rem' }}>{children}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Card de resultado de preço (menor ou último)
// ---------------------------------------------------------------------------

function PriceResultCard({ price, testId }: { price: PriceData; testId: string }) {
  const displayName = price.normalized_name && price.normalized_name !== price.description
    ? price.normalized_name : price.description

  return (
    <article data-testid={testId}>
      <div className="price-result-header">
        <strong className="price-value">{formatCurrency(price.unit_price)}</strong>
      </div>
      <div className="price-product-name">{displayName}</div>
      {price.normalized_name && price.normalized_name !== price.description && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>{price.description}</div>
      )}
      <dl className="price-details">
        <div><dt>Loja</dt><dd>{price.issuer_name}</dd></div>
        <div><dt>Endereço</dt><dd>{price.issuer_address}</dd></div>
        <div><dt>Compra</dt><dd>{formatDate(price.purchase_date)}</dd></div>
        <div><dt>Quantidade</dt><dd>{price.quantity} {price.unit}</dd></div>
        <div><dt>Total</dt><dd>{formatCurrency(price.total_value)}</dd></div>
        <div><dt>NF</dt><dd>Mod.{price.invoice_model} Série {price.invoice_series} Nº {price.invoice_number}</dd></div>
      </dl>
      <p className="price-meta">
        <a href={price.receipt_url} target="_blank" rel="noreferrer">
          Ver cupom (chave …{price.receipt_access_key.slice(-8)})
        </a>
      </p>
    </article>
  )
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export function PriceConsultation() {
  const [products, setProducts] = useState<ProductItem[]>([])
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<ProductItem | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [latestPrice, setLatestPrice] = useState<PriceData | null>(null)
  const [lowestPrice, setLowestPrice] = useState<PriceData | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [history, setHistory] = useState<PriceData[]>([])

  // Visibilidade de cada seção de resultado
  const [showLowest, setShowLowest] = useState(true)
  const [showLatest, setShowLatest] = useState(true)
  const [showByStore, setShowByStore] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  useEffect(() => { fetchProducts().then(setProducts).catch(() => {}) }, [])

  const filtered = filter.trim().length >= 1
    ? products.filter(p => productLabel(p).toLowerCase().includes(filter.toLowerCase()))
    : products

  async function search(key: string) {
    setStatus('loading')
    setErrorMessage(null)
    setLatestPrice(null)
    setLowestPrice(null)
    setHistory([])
    // Reseta seções para estado padrão a cada nova busca
    setShowLowest(true)
    setShowLatest(true)
    setShowByStore(false)
    setShowHistory(false)

    try {
      const [latest, lowest] = await Promise.all([fetchPrice('latest', key), fetchPrice('lowest', key)])
      setLatestPrice(latest)
      setLowestPrice(lowest)
      setStatus(latest || lowest ? 'success' : 'empty')
      // Busca histórico em segundo plano para alimentar "Por loja" e "Histórico completo"
      if (latest || lowest) fetchHistory(key).then(setHistory).catch(() => {})
    } catch (error) {
      setStatus('error')
      setErrorMessage(error instanceof Error ? error.message : 'Erro de conexão com o servidor.')
    }
  }

  async function handleSelect(product: ProductItem) {
    setSelected(product)
    setFilter(productLabel(product))
    await search(product.normalized_name)
  }

  async function handleSearch() {
    if (!selected) return
    await search(selected.normalized_name)
  }

  function handleClear() {
    setFilter(''); setSelected(null); setStatus('idle')
    setLatestPrice(null); setLowestPrice(null); setErrorMessage(null); setHistory([])
  }

  const showList = !selected && filter.trim().length >= 1 && filtered.length > 0
  const byStore = computeByStore(history)

  return (
    <>
      {/* Card de busca */}
      <section className="card price-query-card">
        <h2>Consulta de preços</h2>
        <div style={{ marginBottom: '0.75rem' }}>
          <label htmlFor="product-filter" style={{ display: 'block', marginBottom: '0.4rem' }}>Buscar produto</label>
          <input
            id="product-filter"
            value={filter}
            onChange={e => {
              const value = e.target.value
              setFilter(value)
              if (selected && value !== productLabel(selected)) {
                setSelected(null); setStatus('idle'); setLatestPrice(null); setLowestPrice(null)
              }
            }}
            placeholder={products.length === 0 ? 'Carregando produtos...' : 'Digite para filtrar...'}
            autoComplete="off"
            disabled={status === 'loading'}
            style={{ width: '100%', fontSize: '1.1rem', height: '2.8rem', padding: '0 0.75rem' }}
          />
        </div>

        {showList && (
          <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 0.75rem', maxHeight: '240px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '6px' }}>
            {filtered.map((p, i) => (
              <li key={i}>
                <button type="button" onClick={() => handleSelect(p)} style={{ width: '100%', textAlign: 'left', padding: '0.6rem 0.75rem', background: 'none', border: 'none', cursor: 'pointer', borderBottom: i < filtered.length - 1 ? '1px solid var(--border)' : 'none', fontSize: '0.9rem' }}>
                  {productLabel(p)}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="button" onClick={handleSearch} disabled={!selected || status === 'loading'} style={{ flex: 1, padding: '0.7rem', fontSize: '1rem', cursor: selected ? 'pointer' : 'not-allowed', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px' }}>
            Buscar
          </button>
          <button type="button" onClick={handleClear} disabled={status === 'loading'} style={{ padding: '0.7rem 1rem', fontSize: '1rem', cursor: 'pointer', background: 'var(--bg-secondary, #eee)', border: '1px solid var(--border)', borderRadius: '6px' }}>
            Limpar
          </button>
        </div>

        {products.length === 0 && (
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.5rem' }}>
            Nenhum cupom salvo ainda. Escaneie e salve uma nota primeiro.
          </p>
        )}
      </section>

      {status === 'loading' && (
        <section className="card loading-container" data-testid="price-loader">
          <div className="spinner"></div>
          <p className="loading-text">Consultando preços...</p>
        </section>
      )}

      {status === 'error' && (
        <section className="alert alert-danger" role="alert">
          {errorMessage || 'Não foi possível consultar os preços.'}
        </section>
      )}

      {status === 'empty' && (
        <section className="alert alert-danger" role="alert">Nenhum preço encontrado para esse produto.</section>
      )}

      {status === 'success' && (
        <>
          {/* Seção: Menor preço */}
          {lowestPrice && (
            <Section title="Menor preço" expanded={showLowest} onToggle={() => setShowLowest(s => !s)} badge={formatCurrency(lowestPrice.unit_price)}>
              <PriceResultCard price={lowestPrice} testId="lowest-price-card" />
            </Section>
          )}

          {/* Seção: Último preço */}
          {latestPrice && (
            <Section title="Último preço" expanded={showLatest} onToggle={() => setShowLatest(s => !s)} badge={formatCurrency(latestPrice.unit_price)}>
              <PriceResultCard price={latestPrice} testId="latest-price-card" />
            </Section>
          )}

          {/* Seção: Por loja */}
          <Section title="Por loja" expanded={showByStore} onToggle={() => setShowByStore(s => !s)} badge={byStore.length ? `${byStore.length} loja${byStore.length > 1 ? 's' : ''}` : undefined}>
            {byStore.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Carregando...</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>Loja</th>
                    <th style={{ textAlign: 'right', padding: '0.4rem 0.5rem' }}>Último preço</th>
                    <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>Data</th>
                  </tr>
                </thead>
                <tbody>
                  {byStore.map((s, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.4rem 0.5rem' }}>{s.store}</td>
                      <td style={{ textAlign: 'right', padding: '0.4rem 0.5rem', fontWeight: i === 0 ? 700 : 400, color: i === 0 ? '#2563eb' : undefined }}>{formatCurrency(s.price)}</td>
                      <td style={{ padding: '0.4rem 0.5rem', color: 'var(--text-secondary)' }}>{formatDateShort(s.date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>

          {/* Seção: Histórico completo */}
          <Section title="Histórico completo" expanded={showHistory} onToggle={() => setShowHistory(s => !s)} badge={history.length ? `${history.length} registros` : undefined}>
            {history.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Carregando...</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>Data</th>
                    <th style={{ textAlign: 'right', padding: '0.4rem 0.5rem' }}>Preço unit.</th>
                    <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem' }}>Loja</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.4rem 0.5rem' }}>{formatDateShort(h.purchase_date)}</td>
                      <td style={{ textAlign: 'right', padding: '0.4rem 0.5rem' }}>{formatCurrency(h.unit_price)}</td>
                      <td style={{ padding: '0.4rem 0.5rem', color: 'var(--text-secondary)' }}>{h.issuer_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
        </>
      )}
    </>
  )
}
