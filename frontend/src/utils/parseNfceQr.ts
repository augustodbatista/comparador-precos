// Tipo retornado pelo parser de QR Code NFC-e
export interface NfceData {
  url: string        // URL original do QR Code (enviada ao backend para buscar os dados na SEFAZ)
  accessKey: string  // chave de acesso de 44 dígitos (ID único do cupom)
}

/**
 * Extrai URL e chave de acesso do conteúdo bruto de um QR Code NFC-e.
 *
 * Tenta três estratégias em ordem de confiabilidade:
 * 1. Query params chNFe / chConsNFCe — maioria dos estados (SP, RS)
 * 2. Query param "p" no formato "<chave>|<cDest>|<hash>" — MG e outros
 * 3. Fallback: regex de 44 dígitos na URL — BA, PE e formatos não-padrão
 *
 * Retorna null se a string não for uma NFC-e válida.
 * Espelho do qr_parser.py do backend — mantidos em sincronia propositalmente.
 */
export function parseNfceQr(raw: string): NfceData | null {
  try {
    const trimmed = raw.trim()
    const url = new URL(trimmed)  // lança TypeError se não for uma URL válida

    // Estratégia 1: SP/RS usam chNFe; RS legado usa chConsNFCe — chave exposta diretamente
    const directKey = url.searchParams.get('chNFe') ?? url.searchParams.get('chConsNFCe')
    if (directKey && /^\d{44}$/.test(directKey)) {
      return { url: trimmed, accessKey: directKey }
    }

    // Estratégia 2: MG e outros usam param "p" com formato "<chave>|<cDest>|<hash>"
    // A chave de acesso é sempre o segmento 0 (antes do primeiro "|")
    const pParam = url.searchParams.get('p')
    if (pParam) {
      const candidate = pParam.split('|')[0]
      if (/^\d{44}$/.test(candidate)) {
        return { url: trimmed, accessKey: candidate }
      }
    }

    // Estratégia 3: fallback para estados com formato não-padrão
    // Lookbehind/lookahead negativos evitam capturar sequências maiores que 44 dígitos
    const match = trimmed.match(/(?<!\d)(\d{44})(?!\d)/)
    if (match) {
      return { url: trimmed, accessKey: match[1] }
    }

    return null
  } catch {
    // new URL() lança TypeError para qualquer string não-URL — tratamos como inválida
    return null
  }
}
