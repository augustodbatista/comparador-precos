import { useEffect, useState } from 'react'
import { API_URL } from '../config/api'
import type { ReceiptData } from './QrReader'

async function fetchReceipts(): Promise<ReceiptData[]> {
  const r = await fetch(`${API_URL}/receipts?limit=100`)
  if (!r.ok) return []
  return r.json()
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

function formatCurrency(value: number) {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/** Converte "2026-06" em "Jun/2026". */
function formatMonth(ym: string) {
  const [year, month] = ym.split('-')
  const months = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
  return `${months[parseInt(month) - 1]}/${year}`
}

/** Calcula resumo de gastos a partir da lista de cupons. */
function computeSummary(receipts: ReceiptData[]) {
  if (!receipts.length) return null

  const total = receipts.reduce((s, r) => s + r.totals.paid, 0)

  const storeMap: Record<string, number> = {}
  const monthMap: Record<string, number> = {}

  for (const r of receipts) {
    storeMap[r.issuer.name] = (storeMap[r.issuer.name] || 0) + r.totals.paid
    const month = r.invoice.issued_at.slice(0, 7) // YYYY-MM
    monthMap[month] = (monthMap[month] || 0) + r.totals.paid
  }

  return {
    total,
    ticketMedio: total / receipts.length,
    byStore: Object.entries(storeMap).sort((a, b) => b[1] - a[1]),
    byMonth: Object.entries(monthMap).sort((a, b) => b[0].localeCompare(a[0])),
  }
}

// ---------------------------------------------------------------------------
// Componente auxiliar: seção colapsável
// ---------------------------------------------------------------------------

function Section({ title, expanded, onToggle, badge, children }: {
  title: string; expanded: boolean; onToggle: () => void; badge?: string; children: React.ReactNode
}) {
  return (
    <div className="card" style={{ marginBottom: '0.75rem' }}>
      <button type="button" onClick={onToggle} style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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
// Card de cupom individual (expandível)
// ---------------------------------------------------------------------------

function ReceiptCard({ receipt }: { receipt: ReceiptData }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <article className="card" style={{ marginBottom: '0.75rem' }}>
      <button type="button" onClick={() => setExpanded(e => !e)} style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: 0 }}>
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
                  <td style={{ padding: '0.3rem 0.4rem' }}>{(item as any).normalized_name || item.description}</td>
                  <td style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>{item.qty} {item.unit}</td>
                  <td style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>{formatCurrency(item.unit_price)}</td>
                  <td style={{ textAlign: 'right', padding: '0.3rem 0.4rem', whiteSpace: 'nowrap' }}>{formatCurrency(item.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: '0.6rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            <div>{receipt.issuer.address} — CNPJ: {receipt.issuer.cnpj}</div>
            <a href={receipt.url} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: '0.3rem' }}>
              Ver cupom original ↗
            </a>
          </div>
        </div>
      )}
    </article>
  )
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export function ReceiptHistory() {
  const [receipts, setReceipts] = useState<ReceiptData[]>([])
  const [loading, setLoading] = useState(true)

  // Visibilidade das seções colapsáveis
  const [showSummary, setShowSummary] = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  // Estado dos filtros
  const [storeFilter, setStoreFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  useEffect(() => {
    fetchReceipts().then(data => { setReceipts(data); setLoading(false) })
  }, [])

  // Aplica os filtros client-side
  const filtered = receipts.filter(r => {
    if (storeFilter && !r.issuer.name.toLowerCase().includes(storeFilter.toLowerCase())) return false
    if (dateFrom && r.invoice.issued_at < dateFrom) return false
    if (dateTo && r.invoice.issued_at > dateTo + 'T23:59:59') return false
    return true
  })

  const summary = computeSummary(filtered)

  // Conta quantos filtros estão ativos para exibir no badge
  const activeFilters = [storeFilter, dateFrom, dateTo].filter(Boolean).length

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
    <div>
      {/* Seção: Resumo de gastos (dashboard) */}
      <Section
        title="Resumo de gastos"
        expanded={showSummary}
        onToggle={() => setShowSummary(s => !s)}
        badge={summary ? formatCurrency(summary.total) : undefined}
      >
        {summary && (
          <>
            {/* Totais gerais */}
            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: '120px', background: 'var(--bg-secondary, #f8f9fa)', borderRadius: '8px', padding: '0.75rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Total gasto</div>
                <div style={{ fontWeight: 700, fontSize: '1.1rem', color: '#2563eb' }}>{formatCurrency(summary.total)}</div>
              </div>
              <div style={{ flex: 1, minWidth: '120px', background: 'var(--bg-secondary, #f8f9fa)', borderRadius: '8px', padding: '0.75rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Ticket médio</div>
                <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{formatCurrency(summary.ticketMedio)}</div>
              </div>
              <div style={{ flex: 1, minWidth: '120px', background: 'var(--bg-secondary, #f8f9fa)', borderRadius: '8px', padding: '0.75rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Compras</div>
                <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{filtered.length}</div>
              </div>
            </div>

            {/* Por loja */}
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontWeight: 600, marginBottom: '0.4rem', fontSize: '0.9rem' }}>Por loja</div>
              {summary.byStore.map(([store, total], i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.3rem 0', borderBottom: '1px solid var(--border)', fontSize: '0.875rem' }}>
                  <span>{store}</span>
                  <span style={{ fontWeight: 600 }}>{formatCurrency(total)}</span>
                </div>
              ))}
            </div>

            {/* Por mês */}
            <div>
              <div style={{ fontWeight: 600, marginBottom: '0.4rem', fontSize: '0.9rem' }}>Por mês</div>
              {summary.byMonth.map(([month, total], i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.3rem 0', borderBottom: '1px solid var(--border)', fontSize: '0.875rem' }}>
                  <span>{formatMonth(month)}</span>
                  <span style={{ fontWeight: 600 }}>{formatCurrency(total)}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </Section>

      {/* Seção: Filtros */}
      <Section
        title="Filtros"
        expanded={showFilters}
        onToggle={() => setShowFilters(s => !s)}
        badge={activeFilters > 0 ? `${activeFilters} ativo${activeFilters > 1 ? 's' : ''}` : undefined}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.25rem' }}>Loja</label>
            <input
              value={storeFilter}
              onChange={e => setStoreFilter(e.target.value)}
              placeholder="Ex: Casa Rena"
              style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.95rem' }}
            />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.25rem' }}>De</label>
              <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={{ width: '100%', padding: '0.5rem 0.5rem', fontSize: '0.9rem' }} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.25rem' }}>Até</label>
              <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} style={{ width: '100%', padding: '0.5rem 0.5rem', fontSize: '0.9rem' }} />
            </div>
          </div>
          {activeFilters > 0 && (
            <button type="button" onClick={() => { setStoreFilter(''); setDateFrom(''); setDateTo('') }} style={{ alignSelf: 'flex-start', background: 'none', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.4rem 0.75rem', cursor: 'pointer', fontSize: '0.85rem' }}>
              Limpar filtros
            </button>
          )}
        </div>
      </Section>

      {/* Lista de cupons */}
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
        {filtered.length} de {receipts.length} {receipts.length === 1 ? 'cupom' : 'cupons'} — clique para ver os itens
      </p>

      {filtered.length === 0 ? (
        <div className="card">
          <p style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>Nenhum cupom corresponde aos filtros.</p>
        </div>
      ) : (
        filtered.map(r => <ReceiptCard key={r.access_key} receipt={r} />)
      )}
    </div>
  )
}
