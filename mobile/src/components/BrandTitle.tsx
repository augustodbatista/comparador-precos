export function BrandTitle({ label = 'Comparador de Preços NFC-e' }: { label?: string }) {
  return (
    <span className="toolbar-brand">
      <span className="brand-mark" aria-hidden="true">NFC</span>
      <span className="brand-text">{label}</span>
    </span>
  )
}
