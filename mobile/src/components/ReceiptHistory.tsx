import { useEffect, useState } from 'react'
import {
  IonAccordion,
  IonAccordionGroup,
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
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
import type { ReceiptData } from './QrReader'

async function fetchReceipts(): Promise<ReceiptData[]> {
  const response = await apiFetch(`${API_URL}/receipts?limit=100`)
  if (!response.ok) return []
  return response.json() as Promise<ReceiptData[]>
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR')
}

function formatCurrency(value: number) {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatMonth(value: string) {
  const [year, month] = value.split('-')
  const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
  return `${months[Number.parseInt(month, 10) - 1]}/${year}`
}

function computeSummary(receipts: ReceiptData[]) {
  if (!receipts.length) return null

  const total = receipts.reduce((sum, receipt) => sum + receipt.totals.paid, 0)
  const storeMap: Record<string, number> = {}
  const monthMap: Record<string, number> = {}

  for (const receipt of receipts) {
    storeMap[receipt.issuer.name] = (storeMap[receipt.issuer.name] || 0) + receipt.totals.paid
    const month = receipt.invoice.issued_at.slice(0, 7)
    monthMap[month] = (monthMap[month] || 0) + receipt.totals.paid
  }

  return {
    total,
    ticketMedio: total / receipts.length,
    byStore: Object.entries(storeMap).sort((a, b) => b[1] - a[1]),
    byMonth: Object.entries(monthMap).sort((a, b) => b[0].localeCompare(a[0])),
  }
}

function ReceiptDetails({ receipt }: { receipt: ReceiptData }) {
  return (
    <div className="accordion-content">
      <IonList inset>
        {receipt.items.map((item, index) => (
          <IonItem key={`${receipt.access_key}-${item.code}-${index}`}>
            <IonLabel>
              <h3>{item.normalized_name || item.description}</h3>
              <p>{item.qty} {item.unit} x {formatCurrency(item.unit_price)}</p>
            </IonLabel>
            <IonBadge slot="end">{formatCurrency(item.total)}</IonBadge>
          </IonItem>
        ))}
      </IonList>
      <p className="muted">{receipt.issuer.address} - CNPJ: {receipt.issuer.cnpj}</p>
      <a href={receipt.url} target="_blank" rel="noreferrer">Ver cupom original</a>
    </div>
  )
}

export function ReceiptHistory() {
  const [receipts, setReceipts] = useState<ReceiptData[]>([])
  const [loading, setLoading] = useState(true)
  const [storeFilter, setStoreFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  useEffect(() => {
    fetchReceipts().then(data => {
      setReceipts(data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const filtered = receipts.filter(receipt => {
    if (storeFilter && !receipt.issuer.name.toLowerCase().includes(storeFilter.toLowerCase())) return false
    if (dateFrom && receipt.invoice.issued_at < dateFrom) return false
    if (dateTo && receipt.invoice.issued_at > `${dateTo}T23:59:59`) return false
    return true
  })
  const summary = computeSummary(filtered)
  const activeFilters = [storeFilter, dateFrom, dateTo].filter(Boolean).length

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>
            <span className="toolbar-brand">
              <img className="toolbar-logo-small" src="/assets/comparador-precos-logo.png" alt="" />
              Histórico
            </span>
          </IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen className="ion-padding">
        {loading && (
          <IonCard className="loading-card">
            <IonSpinner name="crescent" />
            <p className="loading-text">Carregando histórico...</p>
          </IonCard>
        )}

        {!loading && receipts.length === 0 && (
          <IonCard>
            <IonCardContent>
              <p className="muted centered">Nenhum cupom salvo ainda. Escaneie e salve uma nota primeiro.</p>
            </IonCardContent>
          </IonCard>
        )}

        {!loading && receipts.length > 0 && (
          <>
            <IonAccordionGroup multiple value={['summary']}>
              <IonAccordion value="summary">
                <IonItem slot="header">
                  <IonLabel>Resumo de gastos</IonLabel>
                  {summary && <IonBadge slot="end" color="success">{formatCurrency(summary.total)}</IonBadge>}
                </IonItem>
                <div slot="content" className="accordion-content">
                  {summary && (
                    <>
                      <div className="summary-grid">
                        <div><span>Total gasto</span><strong>{formatCurrency(summary.total)}</strong></div>
                        <div><span>Ticket médio</span><strong>{formatCurrency(summary.ticketMedio)}</strong></div>
                        <div><span>Compras</span><strong>{filtered.length}</strong></div>
                      </div>
                      <IonList inset>
                        {summary.byStore.map(([store, total]) => (
                          <IonItem key={store}>
                            <IonLabel>{store}</IonLabel>
                            <IonBadge slot="end">{formatCurrency(total)}</IonBadge>
                          </IonItem>
                        ))}
                      </IonList>
                      <IonList inset>
                        {summary.byMonth.map(([month, total]) => (
                          <IonItem key={month}>
                            <IonLabel>{formatMonth(month)}</IonLabel>
                            <IonBadge slot="end" color="medium">{formatCurrency(total)}</IonBadge>
                          </IonItem>
                        ))}
                      </IonList>
                    </>
                  )}
                </div>
              </IonAccordion>

              <IonAccordion value="filters">
                <IonItem slot="header">
                  <IonLabel>Filtros</IonLabel>
                  {activeFilters > 0 && <IonBadge slot="end">{activeFilters} ativos</IonBadge>}
                </IonItem>
                <div slot="content" className="accordion-content filter-stack">
                  <IonInput
                    label="Loja"
                    labelPlacement="stacked"
                    value={storeFilter}
                    placeholder="Ex: Casa Rena"
                    onIonInput={(event) => setStoreFilter(String(event.detail.value ?? ''))}
                  />
                  <IonInput
                    type="date"
                    label="De"
                    labelPlacement="stacked"
                    value={dateFrom}
                    onIonInput={(event) => setDateFrom(String(event.detail.value ?? ''))}
                  />
                  <IonInput
                    type="date"
                    label="Até"
                    labelPlacement="stacked"
                    value={dateTo}
                    onIonInput={(event) => setDateTo(String(event.detail.value ?? ''))}
                  />
                  {activeFilters > 0 && (
                    <IonButton fill="outline" onClick={() => {
                      setStoreFilter('')
                      setDateFrom('')
                      setDateTo('')
                    }}>
                      Limpar filtros
                    </IonButton>
                  )}
                </div>
              </IonAccordion>
            </IonAccordionGroup>

            <p className="muted count-line">
              {filtered.length} de {receipts.length} {receipts.length === 1 ? 'cupom' : 'cupons'}
            </p>

            {filtered.length === 0 ? (
              <IonCard>
                <IonCardContent>
                  <p className="muted centered">Nenhum cupom corresponde aos filtros.</p>
                </IonCardContent>
              </IonCard>
            ) : (
              <IonAccordionGroup>
                {filtered.map(receipt => (
                  <IonAccordion key={receipt.access_key} value={receipt.access_key}>
                    <IonItem slot="header">
                      <IonLabel>
                        <h3>{receipt.issuer.name}</h3>
                        <p>{formatDate(receipt.invoice.issued_at)}</p>
                      </IonLabel>
                      <IonBadge slot="end" color="success">{formatCurrency(receipt.totals.paid)}</IonBadge>
                    </IonItem>
                    <div slot="content">
                      <ReceiptDetails receipt={receipt} />
                    </div>
                  </IonAccordion>
                ))}
              </IonAccordionGroup>
            )}
          </>
        )}
      </IonContent>
    </IonPage>
  )
}
