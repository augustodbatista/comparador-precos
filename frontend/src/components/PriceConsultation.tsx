import { useEffect, useState } from 'react'
import { API_URL } from '../config/api'

// Produto retornado por GET /products
interface ProductItem {
  normalized_name: string  // nome normalizado pelo Ollama (usado como product_id nas queries)
}

// Resposta completa de GET /prices/latest, /prices/lowest e /prices/history
export interface PriceData {
  product_id: string
  description: string         // nome bruto original da SEFAZ
  normalized_name: string | null
  unit_price: number
  quantity: number
  unit: string
  total_value: number
  purchase_date: string       // data de emissão da nota (ISO format)
  invoice_number: string
  invoice_series: string
  invoice_model: string
  issuer_name: string
  issuer_cnpj: string
  issuer_address: string
  receipt_access_key: string
  receipt_url: string
}

// Status da consulta de preços
type Status = 'idle' | 'loading' | 'success' | 'empty' | 'error'

// Tipo de preço a consultar
type PriceKind = 'latest' | 'lowest'

// ---------------------------------------------------------------------------
// Funções utilitárias de formatação
// ---------------------------------------------------------------------------

/** Formata um número como moeda BRL (ex: R$ 7,99). */
function formatCurrency(value: number) {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/** Formata uma string ISO para data e hora no padrão brasileiro (ex: 07/06/2026 11:36:44). */
function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR')
}

/** Formata uma string ISO para data curta (ex: 07/06/2026) — usada na tabela de histórico. */
function formatDateShort(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR')
}

/** Retorna o rótulo de exibição do produto (o normalized_name). */
function productLabel(p: ProductItem): string {
  return p.normalized_name
}

// ---------------------------------------------------------------------------
// Funções de comunicação com a API
// ---------------------------------------------------------------------------

/** Busca o preço (latest ou lowest) de um produto pelo product_id. */
async function fetchPrice(kind: PriceKind, productId: string): Promise<PriceData | null> {
  const response = await fetch(`${API_URL}/prices/${kind}?product_id=${encodeURIComponent(productId)}`)
  if (response.status === 404) return null  // produto sem preço registrado
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Erro ao consultar preços (${response.status})`)
  }
  return response.json()
}

/** Busca o histórico completo de preços de um produto (até 50 registros). */
async function fetchHistory(productId: string): Promise<PriceData[]> {
  const response = await fetch(`${API_URL}/prices/history?product_id=${encodeURIComponent(productId)}&limit=50`)
  if (!response.ok) return []
  return response.json()
}

/** Busca a lista de todos os produtos do catálogo para popular o campo de busca. */
async function fetchProducts(): Promise<ProductItem[]> {
  const response = await fetch(`${API_URL}/products`)
  if (!response.ok) return []
  return response.json()
}

// ---------------------------------------------------------------------------
// Componente interno: card de resultado de preço (menor ou último)
// ---------------------------------------------------------------------------

function PriceResultCard({ title, price, testId }: { title: string; price: PriceData; testId: string }) {
  // Exibe o nome normalizado se diferente da descrição bruta; senão, exibe a descrição
  const displayName = price.normalized_name && price.normalized_name !== price.description
    ? price.normalized_name
    : price.description

  return (
    <article className="card price-result-card" data-testid={testId}>
      {/* Cabeçalho do card: tipo de preço (Menor / Último) e valor unitário em destaque */}
      <div className="price-result-header">
        <span className="price-result-label">{title}</span>
        <strong className="price-value">{formatCurrency(price.unit_price)}</strong>
      </div>

      {/* Nome do produto */}
      <div className="price-product-name">{displayName}</div>

      {/* Descrição bruta em cinza, exibida apenas quando diferente do nome normalizado */}
      {price.normalized_name && price.normalized_name !== price.description && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
          {price.description}
        </div>
      )}

      {/* Detalhes da compra: loja, endereço, data, quantidade, total, nota fiscal */}
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

      {/* Link direto para o cupom na SEFAZ — abre em nova aba */}
      <p className="price-meta">
        <a href={price.receipt_url} target="_blank" rel="noreferrer">
          Ver cupom (chave …{price.receipt_access_key.slice(-8)})
        </a>
      </p>
    </article>
  )
}

// ---------------------------------------------------------------------------
// Componente principal: tela de consulta de preços
// ---------------------------------------------------------------------------

export function PriceConsultation() {
  // Lista de todos os produtos do catálogo
  const [products, setProducts] = useState<ProductItem[]>([])

  // Texto digitado no campo de busca
  const [filter, setFilter] = useState('')

  // Produto selecionado na lista (null = nenhum selecionado ainda)
  const [selected, setSelected] = useState<ProductItem | null>(null)

  // Status da consulta de preços
  const [status, setStatus] = useState<Status>('idle')

  // Resultados da consulta (último preço e menor preço)
  const [latestPrice, setLatestPrice] = useState<PriceData | null>(null)
  const [lowestPrice, setLowestPrice] = useState<PriceData | null>(null)

  // Mensagem de erro da consulta
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Histórico completo de preços (carregado ao clicar em "Ver todos os preços")
  const [history, setHistory] = useState<PriceData[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)

  // Carrega o catálogo de produtos ao montar o componente
  useEffect(() => {
    fetchProducts().then(setProducts).catch(() => {})
  }, [])

  // Filtra a lista de produtos pelo texto digitado
  const filtered = filter.trim().length >= 1
    ? products.filter(p =>
        productLabel(p).toLowerCase().includes(filter.toLowerCase())
      )
    : products

  /**
   * Executa a consulta de preços para um product_id.
   * Busca último e menor preço em paralelo para minimizar a latência.
   */
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

  /**
   * Chamado ao clicar em um item da lista suspensa.
   * Seleciona o produto E dispara a busca imediatamente (comportamento de autocomplete).
   */
  async function handleSelect(product: ProductItem) {
    setSelected(product)
    setFilter(productLabel(product))  // preenche o input com o nome selecionado
    setHistory([])
    setShowHistory(false)
    await search(product.normalized_name)
  }

  /**
   * Chamado ao clicar no botão "Buscar".
   * Permite rebuscar o produto já selecionado sem precisar clicar na lista novamente.
   */
  async function handleSearch() {
    if (!selected) return
    setHistory([])
    setShowHistory(false)
    await search(selected.normalized_name)
  }

  /** Reseta todos os estados para o estado inicial. */
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

  /**
   * Alterna a visibilidade do histórico de preços.
   * Na primeira abertura, busca os dados da API; nas seguintes usa o cache local.
   */
  async function handleToggleHistory() {
    if (showHistory) {
      setShowHistory(false)
      return
    }
    // Usa o cache se já foi carregado antes
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

  // A lista suspensa aparece apenas quando há texto no input E nenhum produto foi selecionado ainda
  const showList = !selected && filter.trim().length >= 1 && filtered.length > 0

  return (
    <>
      {/* Card de busca: input de produto + lista suspensa + botões */}
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
              // Se o usuário editar o campo após selecionar, limpa a seleção para exibir a lista novamente
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

        {/* Lista suspensa de sugestões — aparece ao digitar e some ao selecionar */}
        {showList && (
          <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 0.75rem', maxHeight: '240px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '6px' }}>
            {filtered.map((p, i) => (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => handleSelect(p)}  // seleciona e busca imediatamente
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

        {/* Botões de ação: Buscar (azul, desabilitado sem seleção) e Limpar */}
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={handleSearch}
            disabled={!selected || status === 'loading'}
            style={{
              flex: 1, padding: '0.7rem', fontSize: '1rem',
              cursor: selected ? 'pointer' : 'not-allowed',
              background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px',
            }}
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

        {/* Aviso quando não há cupons salvos ainda */}
        {products.length === 0 && (
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.5rem' }}>
            Nenhum cupom salvo ainda. Escaneie e salve uma nota primeiro.
          </p>
        )}
      </section>

      {/* Estado: carregando */}
      {status === 'loading' && (
        <section className="card loading-container" data-testid="price-loader">
          <div className="spinner"></div>
          <p className="loading-text">Consultando preços...</p>
        </section>
      )}

      {/* Estado: erro na consulta */}
      {status === 'error' && (
        <section className="alert alert-danger" role="alert">
          {errorMessage || 'Não foi possível consultar os preços.'}
        </section>
      )}

      {/* Estado: nenhum preço encontrado */}
      {status === 'empty' && (
        <section className="alert alert-danger" role="alert">
          Nenhum preço encontrado para esse produto.
        </section>
      )}

      {/* Estado: sucesso — exibe menor preço primeiro, depois último preço */}
      {status === 'success' && (
        <>
          <section className="price-results" aria-label="Resultado da consulta">
            {/* Menor preço primeiro para facilitar a comparação visual */}
            {lowestPrice && <PriceResultCard title="Menor preço" price={lowestPrice} testId="lowest-price-card" />}
            {latestPrice && <PriceResultCard title="Último preço" price={latestPrice} testId="latest-price-card" />}
          </section>

          {/* Botão para abrir/fechar o histórico completo de preços */}
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

          {/* Tabela de histórico: data, preço unitário e loja — compacta e legível */}
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
