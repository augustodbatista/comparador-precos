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

function productLabel(p: ProductItem): string {
  return p.normalized_name
}

async function fetchPrice(kind: PriceKind, productId: string): Promise<PriceData | null> {
  const response = await fetch(`${API_URL}/prices/${kind}?product_id=${encodeURIComponent(productId)}`)
  if (response.status === 404) return null
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Erro ao consultar preços (${response.status})`)
  }
  return response.json()
}

async function fetchHistory(productId: string): Promise<PriceData[]> {
  const response = await fetch(`${API_URL}/prices/history?product_id=${encodeURIComponent(productId)}&limit=50`)
  if (!response.ok) return []
  return response.json()
}

async function fetchProducts(): Promise<ProductItem[]> {
  const response = await fetch(`${API_URL}/products`)
  if (!response.ok) return []
  return response.json()
}

function PriceResultCard({ title, price, testId }: { title: string; price: PriceData; testId: string }) {
  const displayName = price.normalized_name && price.normalized_name !== price.description
    ? price.normalized_name
    : price.description

  return (
    <article className="card price-result-card" data-testid={testId}>
      <div className="price-result-header">
        <span className="price-result-label">{title}</span>
        <strong className="price-value">{formatCurrency(price.unit_price)}</strong>
      </div>

      <div className="price-product-name">{displayName}</div>
      {price.normalized_name && price.normalized_name !== price.description && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
          {price.description}
        </div>
      )}

      <dl className="price-details">
        <div>
          <dt>Loja</dt>
          <dd>{price.issuer_name}</dd>
        </div>
        <div>
          <dt>Endereço</dt>
          <dd>{price.issuer_address}</dd>
        </div>
        <div>
          <dt>Compra</dt>
          <dd>{formatDate(price.purchase_date)}</dd>
        </div>
        <div>
          <dt>Quantidade</dt>
          <dd>{price.quantity} {price.unit}</dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd>{formatCurrency(price.total_value)}</dd>
        </div>
        <div>
          <dt>NF</dt>
          <dd>Mod.{price.invoice_model} Série {price.invoice_series} Nº {price.invoice_number}</dd>
        </div>
      </dl>

      <p className="price-meta">
        <a href={price.receipt_url} target="_blank" rel="noreferrer">
          Ver cupom (chave …{price.receipt_access_key.slice(-8)})
        </a>
      </p>
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
  const [showHistory, setShowHistory] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)

  useEffect(() => {
    fetchProducts().then(setProducts).catch(() => {})
  }, [])

  const filtered = filter.trim().length >= 1
    ? products.filter(p =>
        productLabel(p).toLowerCase().includes(filter.toLowerCase())
      )
    : products

  async function search(key: string) {
    setStatus('loading')
    setErrorMessage(null)
    setLatestPrice(null)
    setLowestPrice(null)

    try {
      const [latest, lowest] = await Promise.all([
        fetchPrice('latest', key),
        fetchPrice('lowest', key),
      ])
      setLatestPrice(latest)
      setLowestPrice(lowest)
      setStatus(latest || lowest ? 'success' : 'empty')
    } catch (error) {
      setStatus('error')
      setErrorMessage(error instanceof Error ? error.message : 'Erro de conexão com o servidor.')
    }
  }

  async function handleSelect(product: ProductItem) {
    setSelected(product)
    setFilter(productLabel(product))
    setHistory([])
    setShowHistory(false)
    await search(product.normalized_name)
  }

  async function handleSearch() {
    if (!selected) return
    setHistory([])
    setShowHistory(false)
    await search(selected.normalized_name)
  }

  function handleClear() {
    setFilter('')
    setSelected(null)
    setStatus('idle')
    setLatestPrice(null)
    setLowestPrice(null)
    setErrorMessage(null)
    setHistory([])
    setShowHistory(false)
  }

  async function handleToggleHistory() {
    if (showHistory) {
      setShowHistory(false)
      return
    }
    if (history.length > 0) {
      setShowHistory(true)
      return
    }
    if (!selected) return
    setLoadingHistory(true)
    const data = await fetchHistory(selected.normalized_name)
    setHistory(data)
    setLoadingHistory(false)
    setShowHistory(true)
  }

  const showList = !selected && filter.trim().length >= 1 && filtered.length > 0

  return (
    <>
      <section className="card price-query-card">
        <h2>Consulta de preços</h2>

        <div style={{ marginBottom: '0.75rem' }}>
          <label htmlFor="product-filter" style={{ display: 'block', marginBottom: '0.4rem' }}>
            Buscar produto
          </label>
          <input
            id="product-filter"
            value={filter}
            onChange={e => {
              const value = e.target.value
              setFilter(value)
              if (selected && value !== productLabel(selected)) {
                setSelected(null)
                setStatus('idle')
                setLatestPrice(null)
                setLowestPrice(null)
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
                <button
                  type="button"
                  onClick={() => handleSelect(p)}
                  style={{
                    width: '100%', textAlign: 'left', padding: '0.6rem 0.75rem',
                    background: 'none', border: 'none', cursor: 'pointer',
                    borderBottom: i < filtered.length - 1 ? '1px solid var(--border)' : 'none',
                    fontSize: '0.9rem',
                  }}
                >
                  {productLabel(p)}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={handleSearch}
            disabled={!selected || status === 'loading'}
            style={{ flex: 1, padding: '0.7rem', fontSize: '1rem', cursor: selected ? 'pointer' : 'not-allowed' }}
          >
            Buscar
          </button>
          <button
            type="button"
            onClick={handleClear}
            disabled={status === 'loading'}
            style={{ padding: '0.7rem 1rem', fontSize: '1rem', cursor: 'pointer', background: 'var(--bg-secondary, #eee)', border: '1px solid var(--border)', borderRadius: '6px' }}
          >
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
        <section className="alert alert-danger" role="alert">
          Nenhum preço encontrado para esse produto.
        </section>
      )}

      {status === 'success' && (
        <>
          <section className="price-results" aria-label="Resultado da consulta">
            {lowestPrice && <PriceResultCard title="Menor preço" price={lowestPrice} testId="lowest-price-card" />}
            {latestPrice && <PriceResultCard title="Último preço" price={latestPrice} testId="latest-price-card" />}
          </section>

          <div style={{ textAlign: 'center', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={handleToggleHistory}
              disabled={loadingHistory}
              style={{ padding: '0.6rem 1.2rem', fontSize: '0.95rem', cursor: 'pointer' }}
            >
              {loadingHistory ? 'Carregando...' : showHistory ? 'Ocultar histórico' : 'Ver todos os preços'}
            </button>
          </div>

          {showHistory && history.length > 0 && (
            <section className="card" style={{ marginTop: '0.75rem' }}>
              <h3 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>Histórico de preços</h3>
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
            </section>
          )}
        </>
      )}
    </>
  )
}
