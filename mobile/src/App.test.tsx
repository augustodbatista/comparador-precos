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

    expect(screen.getByText('Scanner mock')).toBeInTheDocument()

    const pricesTab = document.querySelector('ion-tab-button[tab="prices"]')
    expect(pricesTab).not.toBeNull()
    await userEvent.click(pricesTab!)

    expect(screen.getByRole('heading', { name: /consulta de preços/i })).toBeInTheDocument()
    expect(screen.queryByText('Scanner mock')).not.toBeInTheDocument()
  })
})
