import { describe, it, expect } from 'vitest'
import { parseNfceQr } from './parseNfceQr'

const KEY = '12345678901234567890123456789012345678901234' // 44 dígitos

describe('parseNfceQr', () => {
  describe('param chNFe (SP, RS e outros)', () => {
    it('extrai URL e chave via chNFe', () => {
      const url = `https://www.nfce.fazenda.sp.gov.br/consulta?chNFe=${KEY}&p=1`
      expect(parseNfceQr(url)).toEqual({ url, accessKey: KEY })
    })

    it('ignora espaços em branco ao redor', () => {
      const url = `https://www.nfce.fazenda.sp.gov.br/consulta?chNFe=${KEY}`
      expect(parseNfceQr(`  ${url}  `)?.accessKey).toBe(KEY)
    })
  })

  describe('param chConsNFCe (RS antigo)', () => {
    it('extrai chave via chConsNFCe', () => {
      const url = `https://www.sefaz.rs.gov.br/NFCE/consulta?chConsNFCe=${KEY}`
      expect(parseNfceQr(url)?.accessKey).toBe(KEY)
    })
  })

  describe('param p (MG e outros)', () => {
    it('extrai chave do primeiro segmento do param p', () => {
      const url = `https://nfce.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=${KEY}|1|1|abc`
      expect(parseNfceQr(url)?.accessKey).toBe(KEY)
    })

    it('retorna null se segmento p não tem 44 dígitos', () => {
      const url = 'https://nfce.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=12345|1|1'
      expect(parseNfceQr(url)).toBeNull()
    })
  })

  describe('fallback — 44 dígitos na URL', () => {
    it('encontra chave embutida em path não-padrão', () => {
      const url = `https://nfce.sefaz.ba.gov.br/nfce/${KEY}/consulta`
      expect(parseNfceQr(url)?.accessKey).toBe(KEY)
    })
  })

  describe('casos inválidos', () => {
    it('retorna null para URL sem chave', () => {
      expect(parseNfceQr('https://google.com')).toBeNull()
    })

    it('retorna null para chave com menos de 44 dígitos', () => {
      const url = 'https://nfce.fazenda.sp.gov.br/consulta?chNFe=12345'
      expect(parseNfceQr(url)).toBeNull()
    })

    it('retorna null para chave com mais de 44 dígitos', () => {
      const url = `https://nfce.fazenda.sp.gov.br/consulta?chNFe=${KEY}5`
      expect(parseNfceQr(url)).toBeNull()
    })

    it('retorna null para texto simples', () => {
      expect(parseNfceQr('apenas um texto qualquer')).toBeNull()
    })

    it('retorna null para string vazia', () => {
      expect(parseNfceQr('')).toBeNull()
    })
  })
})
