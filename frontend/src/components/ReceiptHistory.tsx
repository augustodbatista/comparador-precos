import { useEffect, useState } from 'react'
import { API_URL } from '../config/api'
import type { ReceiptData } from './QrReader'

/** Busca o histórico de cupons salvos no banco (mais recente primeiro). */
async function fetchReceipts(): Promise<ReceiptData[]> {
  const response = await fetch(`${API_URL}/receipts?limit=50`)
  if (!response.ok) return []
  return response.json()
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR')
}

function formatCurrency(value: number) {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/** Card de um cupom — mostra cabeçalho e expande para exibir os itens. */
function ReceiptCard({ receipt }: { receipt: ReceiptData }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <article className="card" style={{ marginBottom: '0.75rem' }}>
      {/* Cabeçalho clicável: loja, data e total */}
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%', background: 'none', border: 'none', cursor: 'pointer',
          textAlign: 'left', padding: 0,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '1rem' }}>{receipt.issuer.name}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
              {formatDate(receipt.invoice.issued_at)}
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <div style={{ fontWeight: 700, color: '#2563eb' }}>{formatCurrency(receipt.totals.paid)}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              {receipt.totals.items_count} {receipt.totals.items_count === 1 ? 'item' : 'itens'}
            </div>
          </div>
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
          {expanded ? '▲ Ocultar itens' : '▼ Ver itens'}
        </div>
      </button>

      {/* Lista de itens — visível apenas quando expandido */}
      {expanded && (
        <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: '0.3rem 0.4rem' }}>Produto</th>
                <th style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>Qtd</th>
                <th style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>Unit.</th>
                <th style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {receipt.items.map((item, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.3rem 0.4rem' }}>
                    {/* Mostra nome normalizado se disponível; senão, a descrição bruta */}
                    {(item as any).normalized_name || item.description}
                  </td>
                  <td style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>
                    {item.qty} {item.unit}
                  </td>
                  <td style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>
                    {formatCurrency(item.unit_price)}
                  </td>
                  <td style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>
                    {formatCurrency(item.total)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Endereço da loja e link para o cupom */}
          <div style={{ marginTop: '0.6rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            <div>{receipt.issuer.address}</div>
            <div>CNPJ: {receipt.issuer.cnpj}</div>
            <a
              href={receipt.url}
              target="_blank"
              rel="noreferrer"
              style={{ display: 'inline-block', marginTop: '0.3rem' }}
            >
              Ver cupom original ↗
            </a>
          </div>
        </div>
      )}
    </article>
  )
}

/** Tela de histórico de compras — lista todos os cupons salvos no banco. */
export function ReceiptHistory() {
  const [receipts, setReceipts] = useState<ReceiptData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchReceipts().then(data => {
      setReceipts(data)
      setLoading(false)
    })
  }, [])

  if (loading) {
    return (
      <section className="card loading-container">
        <div className="spinner"></div>
        <p className="loading-text">Carregando histórico...</p>
      </section>
    )
  }

  if (receipts.length === 0) {
    return (
      <section className="card">
        <p style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>
          Nenhum cupom salvo ainda. Escaneie e salve uma nota primeiro.
        </p>
      </section>
    )
  }

  return (
    <section>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
        {receipts.length} {receipts.length === 1 ? 'cupom salvo' : 'cupons salvos'} — clique para ver os itens
      </p>
      {receipts.map(r => (
        <ReceiptCard key={r.access_key} receipt={r} />
      ))}
    </section>
  )
}
