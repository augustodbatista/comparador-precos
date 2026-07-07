import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PriceConsultation, type PriceData } from './PriceConsultation'

const mockProductList = [
  { normalized_name: 'Leite Moça 395g' },
  { normalized_name: 'Arroz Tilio 5kg' },
]

const latestPrice: PriceData = {
  product_id: 'Leite Moça 395g',
  description: 'LEITE MOCA CX 395G',
  normalized_name: 'Leite Moça 395g',
  unit_price: 5.5,
  quantity: 1,
  unit: 'UN',
  total_value: 5.5,
  purchase_date: '2026-06-07T15:00:00',
  invoice_number: '123456',
  invoice_series: '1',
  invoice_model: '65',
  issuer_name: 'Supermercado D',
  issuer_cnpj: '44444444000144',
  issuer_address: 'Rua X, 100',
  receipt_access_key: '44444444444444444444444444444444444444444444',
  receipt_url: 'https://sefaz.mg.gov.br/nfce?p=123',
}

const lowestPrice: PriceData = {
  ...latestPrice,
  unit_price: 4.9,
  total_value: 4.9,
  purchase_date: '2026-06-07T12:00:00',
  issuer_name: 'Supermercado B',
  issuer_cnpj: '22222222000122',
  issuer_address: 'Rua Y, 200',
  receipt_access_key: '22222222222222222222222222222222222222222222',
  receipt_url: 'https://sefaz.mg.gov.br/nfce?p=456',
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
  // Default: sem produtos — evita UnhandledRejection nos testes que não precisam da lista
  fetchMock.mockReturnValue(jsonResponse([]))
})

describe('PriceConsultation', () => {
  it('renderiza o campo de busca de produto', () => {
    render(<PriceConsultation />)

    expect(screen.getByRole('heading', { name: /consulta de preços/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/buscar produto/i)).toBeInTheDocument()
  })

  it('carrega e exibe lista de produtos ao montar', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse(mockProductList))

    render(<PriceConsultation />)
    await userEvent.type(screen.getByLabelText(/buscar produto/i), 'a')

    await waitFor(() => {
      expect(screen.getByText('Leite Moça 395g')).toBeInTheDocument()
      expect(screen.getByText('Arroz Tilio 5kg')).toBeInTheDocument()
    })
  })

  it('consulta último e menor preço ao clicar num produto', async () => {
    fetchMock
      .mockReturnValueOnce(jsonResponse(mockProductList)) // GET /products
      .mockReturnValueOnce(jsonResponse(latestPrice))     // GET /prices/latest
      .mockReturnValueOnce(jsonResponse(lowestPrice))     // GET /prices/lowest

    render(<PriceConsultation />)
    await userEvent.type(screen.getByLabelText(/buscar produto/i), 'Leite')

    await waitFor(() => screen.getByText('Leite Moça 395g'))
    await userEvent.click(screen.getByText('Leite Moça 395g'))

    await waitFor(() => {
      expect(screen.getByTestId('latest-price-card')).toBeInTheDocument()
      expect(screen.getByTestId('lowest-price-card')).toBeInTheDocument()
    })

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/prices/latest?product_id='))
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/prices/lowest?product_id='))
    expect(screen.getByTestId('latest-price-card')).toHaveTextContent('Supermercado D')
    expect(screen.getByTestId('latest-price-card')).toHaveTextContent('R$ 5,50')
    expect(screen.getByTestId('lowest-price-card')).toHaveTextContent('Supermercado B')
    expect(screen.getByTestId('lowest-price-card')).toHaveTextContent('R$ 4,90')
  })

  it('exibe estado vazio quando o produto não tem preços cadastrados', async () => {
    fetchMock
      .mockReturnValueOnce(jsonResponse(mockProductList))
      .mockReturnValueOnce(jsonResponse({ detail: 'Produto não encontrado' }, 404))
      .mockReturnValueOnce(jsonResponse({ detail: 'Produto não encontrado' }, 404))

    render(<PriceConsultation />)
    await userEvent.type(screen.getByLabelText(/buscar produto/i), 'Leite')

    await waitFor(() => screen.getByText('Leite Moça 395g'))
    await userEvent.click(screen.getByText('Leite Moça 395g'))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/nenhum preço encontrado/i)
    })
  })

  it('exibe erro retornado pela API', async () => {
    fetchMock
      .mockReturnValueOnce(jsonResponse(mockProductList))
      .mockReturnValueOnce(jsonResponse({ detail: 'Falha no banco' }, 500))
      .mockReturnValueOnce(jsonResponse({ detail: 'Falha no banco' }, 500))

    render(<PriceConsultation />)
    await userEvent.type(screen.getByLabelText(/buscar produto/i), 'Leite')

    await waitFor(() => screen.getByText('Leite Moça 395g'))
    await userEvent.click(screen.getByText('Leite Moça 395g'))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/falha no banco/i)
    })
  })
})
