export interface NfceData {
  url: string
  accessKey: string
}

export function parseNfceQr(raw: string): NfceData | null {
  try {
    const trimmed = raw.trim()
    const url = new URL(trimmed)

    // SP/RS usam chNFe; RS legado usa chConsNFCe — ambos expõem a chave diretamente
    const directKey = url.searchParams.get('chNFe') ?? url.searchParams.get('chConsNFCe')
    if (directKey && /^\d{44}$/.test(directKey)) {
      return { url: trimmed, accessKey: directKey }
    }

    // MG e outros: param "p" com formato "<chave>|<cDest>|<hash>" — a chave é sempre o segmento 0
    const pParam = url.searchParams.get('p')
    if (pParam) {
      const candidate = pParam.split('|')[0]
      if (/^\d{44}$/.test(candidate)) {
        return { url: trimmed, accessKey: candidate }
      }
    }

    // Fallback para estados com formato não-padrão — lookbehind/lookahead negativos
    // evitam capturar sequências maiores que 44 dígitos
    const match = trimmed.match(/(?<!\d)(\d{44})(?!\d)/)
    if (match) {
      return { url: trimmed, accessKey: match[1] }
    }

    return null
  } catch {
    // new URL() lança TypeError para qualquer string não-URL; tratamos como inválida
    return null
  }
}
