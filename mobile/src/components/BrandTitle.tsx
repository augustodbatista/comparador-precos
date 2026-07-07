export function BrandTitle({ label = 'Comparador 360' }: { label?: string }) {
  return (
    <span className="toolbar-brand">
      <span className="brand-mark" aria-hidden="true">360</span>
      <span className="brand-text">{label}</span>
    </span>
  )
}
