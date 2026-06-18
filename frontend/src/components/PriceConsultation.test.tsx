import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PriceConsultation, type PriceData } from './PriceConsultation'

const latestPrice: PriceData = {
  product_id: 'P1',
  description: 'Leite Moça Promoção',
  unit_price: 5.5,
  quantity: 1,
  unit: 'UN',
  total_value: 5.5,
  purchase_date: '2026-06-07T15:00:00',
  issuer_name: 'Supermercado D',
  issuer_cnpj: '44444444000144',
  receipt_access_key: '44444444444444444444444444444444444444444444',
}

const lowestPrice: PriceData = {
  product_id: 'P1',
  description: 'Leite Moça',
  unit_price: 4.9,
  quantity: 1,
  unit: 'UN',
  total_value: 4.9,
  purchase_date: '2026-06-07T12:00:00',
  issuer_name: 'Supermercado B',
  issuer_cnpj: '22222222000122',
  receipt_access_key: '22222222222222222222222222222222222222222222',
}

const fetchMock = vi.fn()

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  })
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

describe('PriceConsultation', () => {
  it('renderiza o formulário de consulta', () => {
    render(<PriceConsultation />)

    expect(screen.getByRole('heading', { name: /consulta de preços/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/código do produto/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /consultar/i })).toBeInTheDocument()
  })

  it('consulta último e menor preço para o produto informado', async () => {
    fetchMock
      .mockReturnValueOnce(jsonResponse(latestPrice))
      .mockReturnValueOnce(jsonResponse(lowestPrice))

    render(<PriceConsultation />)

    await userEvent.type(screen.getByLabelText(/código do produto/i), ' P1 ')
    await userEvent.click(screen.getByRole('button', { name: /consultar/i }))

    await waitFor(() => {
      expect(screen.getByTestId('latest-price-card')).toBeInTheDocument()
      expect(screen.getByTestId('lowest-price-card')).toBeInTheDocument()
    })

    expect(fetchMock).toHaveBeenNthCalledWith(1, expect.stringContaining('/prices/latest?product_id=P1'))
    expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining('/prices/lowest?product_id=P1'))
    expect(screen.getByTestId('latest-price-card')).toHaveTextContent('Supermercado D')
    expect(screen.getByTestId('latest-price-card')).toHaveTextContent('R$ 5,50')
    expect(screen.getByTestId('lowest-price-card')).toHaveTextContent('Supermercado B')
    expect(screen.getByTestId('lowest-price-card')).toHaveTextContent('R$ 4,90')
  })

  it('exibe estado vazio quando o produto não existe', async () => {
    fetchMock
      .mockReturnValueOnce(jsonResponse({ detail: 'Produto não encontrado' }, 404))
      .mockReturnValueOnce(jsonResponse({ detail: 'Produto não encontrado' }, 404))

    render(<PriceConsultation />)

    await userEvent.type(screen.getByLabelText(/código do produto/i), 'P404')
    await userEvent.click(screen.getByRole('button', { name: /consultar/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/nenhum preço encontrado/i)
    })
  })

  it('exibe erro retornado pela API', async () => {
    fetchMock
      .mockReturnValueOnce(jsonResponse({ detail: 'Falha no banco' }, 500))
      .mockReturnValueOnce(jsonResponse(lowestPrice))

    render(<PriceConsultation />)

    await userEvent.type(screen.getByLabelText(/código do produto/i), 'P1')
    await userEvent.click(screen.getByRole('button', { name: /consultar/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/falha no banco/i)
    })
  })

  it('valida produto em branco sem chamar a API', async () => {
    render(<PriceConsultation />)

    await userEvent.click(screen.getByRole('button', { name: /consultar/i }))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/informe o código/i)
  })
})
