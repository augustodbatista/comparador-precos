import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./components/QrReader', () => ({
  QrReader: () => <div>Scanner mock</div>,
}))

describe('App', () => {
  it('alterna entre scanner e consulta de preços', async () => {
    render(<App />)

    expect(await screen.findByText('Scanner mock')).toBeInTheDocument()

    const pricesTab = document.querySelector('ion-tab-button[tab="prices"]')
    expect(pricesTab).not.toBeNull()
    await userEvent.click(pricesTab!)

    expect(await screen.findByRole('heading', { name: /consulta de pre/i })).toBeInTheDocument()
    expect(screen.queryByText('Scanner mock')).not.toBeInTheDocument()
  })
})
