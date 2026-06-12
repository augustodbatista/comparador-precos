import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QrReader } from './QrReader'

const KEY = '12345678901234567890123456789012345678901234'
const VALID_URL = `https://www.nfce.fazenda.sp.gov.br/consulta?chNFe=${KEY}&p=1`

// Captura o callback de sucesso registrado pelo scanner
let capturedOnScan: ((text: string) => void) | null = null

vi.mock('html5-qrcode', () => ({
  Html5QrcodeScanner: vi.fn().mockImplementation(() => ({
    render: vi.fn((onSuccess: (text: string) => void) => {
      capturedOnScan = onSuccess
    }),
    clear: vi.fn().mockResolvedValue(undefined),
  })),
}))

beforeEach(() => {
  capturedOnScan = null
})

describe('QrReader', () => {
  it('exibe instrução de câmera no estado inicial', () => {
    render(<QrReader />)
    expect(screen.getByText(/aponte a câmera/i)).toBeInTheDocument()
  })

  it('exibe chave e URL após scan válido', async () => {
    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    expect(screen.getByTestId('access-key')).toHaveTextContent(KEY)
    expect(screen.getByTestId('nfce-url')).toHaveTextContent(VALID_URL)
    expect(screen.getByText(/QR Code lido com sucesso/i)).toBeInTheDocument()
  })

  it('exibe mensagem de erro para QR Code não NFC-e', async () => {
    render(<QrReader />)

    await act(async () => {
      capturedOnScan!('https://google.com')
    })

    expect(screen.getByRole('alert')).toHaveTextContent(/não reconhecido/i)
    expect(screen.getByText(/aponte a câmera/i)).toBeInTheDocument()
  })

  it('volta ao scanner ao clicar em "Escanear novamente"', async () => {
    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    await waitFor(() => screen.getByText(/escanear novamente/i))
    await userEvent.click(screen.getByText(/escanear novamente/i))

    expect(screen.getByText(/aponte a câmera/i)).toBeInTheDocument()
  })

  it('botão "Copiar URL" chama clipboard com a URL correta', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    render(<QrReader />)

    await act(async () => {
      capturedOnScan!(VALID_URL)
    })

    await userEvent.click(screen.getByText(/copiar url/i))

    expect(writeText).toHaveBeenCalledWith(VALID_URL)
    await waitFor(() => expect(screen.getByText(/copiado!/i)).toBeInTheDocument())
  })
})
