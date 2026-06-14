import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QrReader } from './QrReader'

const KEY = '12345678901234567890123456789012345678901234'
const VALID_URL = `https://www.nfce.fazenda.sp.gov.br/consulta?chNFe=${KEY}&p=1`

const mockReceiptData = {
  access_key: KEY,
  url: VALID_URL,
  issuer: {
    name: 'Supermercado Preço Bom',
    cnpj: '12.345.678/0001-99',
    address: 'Rua Principal, 123, Centro'
  },
  items: [
    {
      code: '001',
      description: 'ARROZ TIPO 1 5KG',
      qty: 1,
      unit: 'UN',
      unit_price: 25.5,
      total: 25.5
    },
    {
      code: '002',
      description: 'FEIJAO PRETO 1KG',
      qty: 2,
      unit: 'UN',
      unit_price: 8.25,
      total: 16.5
    }
  ],
  totals: {
    total: 42.0,
    paid: 42.0,
    items_count: 2
  },
  invoice: {
    model: '65',
    series: '1',
    number: '12345',
    issued_at: '2026-06-12T15:59:33-03:00'
  }
}

let capturedOnScan: ((text: string) => void) | null = null

vi.mock('html5-qrcode', () => ({
  Html5QrcodeScanner: vi.fn().mockImplementation(() => ({
    render: vi.fn((onSuccess: (text: string) => void) => {
      capturedOnScan = onSuccess
    }),
    clear: vi.fn().mockResolvedValue(undefined),
  })),
}))

const fetchMock = vi.fn().mockImplementation((_url, init) => {
  const signal = init?.signal;
  return new Promise((resolve, reject) => {
    if (signal) {
      if (signal.aborted) {
        return reject(new DOMException('The user aborted a request.', 'AbortError'));
      }
      signal.addEventListener('abort', () => {
        reject(new DOMException('The user aborted a request.', 'AbortError'));
      });
    }
    resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockReceiptData)
    });
  });
})

vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  capturedOnScan = null
  fetchMock.mockClear()
  fetchMock.mockImplementation((_url, init) => {
    const signal = init?.signal;
    return new Promise((resolve, reject) => {
      if (signal) {
        if (signal.aborted) {
          return reject(new DOMException('The user aborted a request.', 'AbortError'));
        }
        signal.addEventListener('abort', () => {
          reject(new DOMException('The user aborted a request.', 'AbortError'));
        });
      }
      resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockReceiptData)
      });
    });
  })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('QrReader', () => {
  it('exibe instrução de câmera no estado inicial', () => {
    render(<QrReader />)
    expect(screen.getByText(/aponte a câmera/i)).toBeInTheDocument()
  })

  it('exibe loading enquanto busca os dados da nota', async () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}))

    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    expect(screen.getByTestId('loader')).toBeInTheDocument()
    expect(screen.getByText(/Buscando nota na SEFAZ/i)).toBeInTheDocument()
  })

  it('exibe os dados retornados pela API após scan válido', async () => {
    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    await waitFor(() => {
      expect(screen.getByTestId('store-name')).toHaveTextContent('Supermercado Preço Bom')
    })

    const items = screen.getAllByTestId('receipt-item')
    expect(items).toHaveLength(2)
    expect(screen.getByText('ARROZ TIPO 1 5KG')).toBeInTheDocument()
    expect(screen.getByText('FEIJAO PRETO 1KG')).toBeInTheDocument()
    expect(screen.getByTestId('total-paid')).toHaveTextContent('R$ 42,00')
  })

  it('exibe erro de timeout se o servidor demorar mais de 60s (client-side)', async () => {
    vi.useFakeTimers()
    
    fetchMock.mockImplementationOnce((_url, init) => {
      const signal = init?.signal;
      return new Promise((_resolve, reject) => {
        if (signal) {
          signal.addEventListener('abort', () => {
            reject(new DOMException('The user aborted a request.', 'AbortError'));
          });
        }
      });
    })

    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    expect(screen.getByTestId('loader')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000)
    })

    // Assert synchronously to avoid waitFor hanging on fake timers
    expect(screen.getByRole('alert')).toHaveTextContent(/demorou muito para responder/i)
  })

  it('exibe erro se o servidor retornar 504 Gateway Timeout', async () => {
    fetchMock.mockImplementationOnce(() => Promise.resolve({
      ok: false,
      status: 504,
      json: () => Promise.resolve({ detail: 'Timeout ao acessar a SEFAZ.' })
    }))

    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Timeout ao acessar a SEFAZ/i)
    })
  })

  it('permite salvar a nota com sucesso e exibe feedback de sucesso', async () => {
    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    await waitFor(() => {
      expect(screen.getByTestId('store-name')).toBeInTheDocument()
    })

    fetchMock.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      status: 201,
      json: () => Promise.resolve(mockReceiptData)
    }))

    const saveBtn = screen.getByTestId('save-btn')
    await userEvent.click(saveBtn)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/salva com sucesso/i)
    })

    expect(screen.queryByTestId('save-btn')).not.toBeInTheDocument()
  })

  it('exibe feedback de erro ao falhar no salvamento', async () => {
    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    await waitFor(() => {
      expect(screen.getByTestId('store-name')).toBeInTheDocument()
    })

    fetchMock.mockImplementationOnce(() => Promise.resolve({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'Erro interno no banco de dados.' })
    }))

    const saveBtn = screen.getByTestId('save-btn')
    await userEvent.click(saveBtn)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Erro interno no banco de dados/i)
    })

    expect(screen.getByTestId('save-btn')).toBeInTheDocument()
  })
})
