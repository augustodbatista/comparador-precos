export interface NfceData {
  url: string
  accessKey: string
}

export function parseNfceQr(raw: string): NfceData | null {
  try {
    const trimmed = raw.trim()
    const url = new URL(trimmed)

    // SP, RS e maioria dos estados: chNFe ou chConsNFCe como param direto
    const directKey = url.searchParams.get('chNFe') ?? url.searchParams.get('chConsNFCe')
    if (directKey && /^\d{44}$/.test(directKey)) {
      return { url: trimmed, accessKey: directKey }
    }

    // MG e outros: param "p" com formato "chave|cDest|..."
    const pParam = url.searchParams.get('p')
    if (pParam) {
      const candidate = pParam.split('|')[0]
      if (/^\d{44}$/.test(candidate)) {
        return { url: trimmed, accessKey: candidate }
      }
    }

    // Fallback: 44 dígitos consecutivos em qualquer parte da URL
    const match = trimmed.match(/(?<!\d)(\d{44})(?!\d)/)
    if (match) {
      return { url: trimmed, accessKey: match[1] }
    }

    return null
  } catch {
    return null
  }
}
