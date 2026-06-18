import { FormEvent, useState } from 'react'
import { API_URL } from '../config/api'

export interface PriceData {
  product_id: string
  description: string
  unit_price: number
  quantity: number
  unit: string
  total_value: number
  purchase_date: string
  issuer_name: string
  issuer_cnpj: string
  receipt_access_key: string
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

async function fetchPrice(kind: PriceKind, productId: string): Promise<PriceData | null> {
  const response = await fetch(`${API_URL}/prices/${kind}?product_id=${encodeURIComponent(productId)}`)

  if (response.status === 404) {
    return null
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Erro ao consultar preços (${response.status})`)
  }

  return response.json()
}

function PriceResultCard({
  title,
  price,
  testId,
}: {
  title: string
  price: PriceData
  testId: string
}) {
  return (
    <article className="card price-result-card" data-testid={testId}>
      <div className="price-result-header">
        <span className="price-result-label">{title}</span>
        <strong className="price-value">{formatCurrency(price.unit_price)}</strong>
      </div>

      <div className="price-product-name">{price.description}</div>

      <dl className="price-details">
        <div>
          <dt>Loja</dt>
          <dd>{price.issuer_name}</dd>
        </div>
        <div>
          <dt>Compra</dt>
          <dd>{formatDate(price.purchase_date)}</dd>
        </div>
        <div>
          <dt>Quantidade</dt>
          <dd>
            {price.quantity} {price.unit}
          </dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd>{formatCurrency(price.total_value)}</dd>
        </div>
      </dl>

      <p className="price-meta">
        Produto {price.product_id} - Cupom final {price.receipt_access_key.slice(-8)}
      </p>
    </article>
  )
}

export function PriceConsultation() {
  const [productId, setProductId] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [latestPrice, setLatestPrice] = useState<PriceData | null>(null)
  const [lowestPrice, setLowestPrice] = useState<PriceData | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedProductId = productId.trim()

    if (!normalizedProductId) {
      setStatus('error')
      setErrorMessage('Informe o código do produto.')
      setLatestPrice(null)
      setLowestPrice(null)
      return
    }

    setStatus('loading')
    setErrorMessage(null)
    setLatestPrice(null)
    setLowestPrice(null)

    try {
      const [latest, lowest] = await Promise.all([
        fetchPrice('latest', normalizedProductId),
        fetchPrice('lowest', normalizedProductId),
      ])

      setLatestPrice(latest)
      setLowestPrice(lowest)
      setStatus(latest || lowest ? 'success' : 'empty')
    } catch (error) {
      setStatus('error')
      setErrorMessage(error instanceof Error ? error.message : 'Erro de conexão com o servidor.')
    }
  }

  return (
    <>
      <section className="card price-query-card">
        <h2>Consulta de preços</h2>
        <form className="price-search-form" onSubmit={handleSubmit}>
          <label htmlFor="product-id">Código do produto</label>
          <div className="price-search-row">
            <input
              id="product-id"
              value={productId}
              onChange={(event) => setProductId(event.target.value)}
              placeholder="Ex: 5173"
              autoComplete="off"
              disabled={status === 'loading'}
            />
            <button className="btn btn-primary price-search-button" type="submit" disabled={status === 'loading'}>
              {status === 'loading' ? 'Consultando...' : 'Consultar'}
            </button>
          </div>
        </form>
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
        <section className="price-results" aria-label="Resultado da consulta">
          {latestPrice && (
            <PriceResultCard title="Último preço" price={latestPrice} testId="latest-price-card" />
          )}
          {lowestPrice && (
            <PriceResultCard title="Menor preço" price={lowestPrice} testId="lowest-price-card" />
          )}
        </section>
      )}
    </>
  )
}
