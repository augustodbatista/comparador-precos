import pytest
from app.services.qr_parser import parse_qr_nfce, NfceData

KEY = "12345678901234567890123456789012345678901234"  # 44 dígitos


class TestChNFe:
    def test_extrai_chave_via_chNFe(self):
        url = f"https://www.nfce.fazenda.sp.gov.br/consulta?chNFe={KEY}&p=1"
        result = parse_qr_nfce(url)
        assert result == NfceData(url=url, access_key=KEY)

    def test_ignora_espacos_ao_redor(self):
        url = f"https://www.nfce.fazenda.sp.gov.br/consulta?chNFe={KEY}"
        result = parse_qr_nfce(f"  {url}  ")
        assert result is not None
        assert result.access_key == KEY

    def test_url_armazenada_sem_espacos(self):
        url = f"https://www.nfce.fazenda.sp.gov.br/consulta?chNFe={KEY}"
        result = parse_qr_nfce(f"  {url}  ")
        assert result is not None
        assert result.url == url


class TestChConsNFCe:
    def test_extrai_chave_via_chConsNFCe(self):
        url = f"https://www.sefaz.rs.gov.br/NFCE/consulta?chConsNFCe={KEY}"
        result = parse_qr_nfce(url)
        assert result is not None
        assert result.access_key == KEY


class TestParamP:
    def test_extrai_chave_do_primeiro_segmento_de_p(self):
        url = f"https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p={KEY}|3|1"
        result = parse_qr_nfce(url)
        assert result is not None
        assert result.access_key == KEY

    def test_retorna_none_se_segmento_p_invalido(self):
        url = "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=12345|3|1"
        assert parse_qr_nfce(url) is None

    def test_url_real_mg(self):
        url = "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=31260661585865266267650040002426521200179790|3|1"
        result = parse_qr_nfce(url)
        assert result is not None
        assert result.access_key == "31260661585865266267650040002426521200179790"


class TestFallback:
    def test_encontra_chave_embutida_em_path(self):
        url = f"https://nfce.sefaz.ba.gov.br/nfce/{KEY}/consulta"
        result = parse_qr_nfce(url)
        assert result is not None
        assert result.access_key == KEY


class TestCasosInvalidos:
    def test_url_sem_chave(self):
        assert parse_qr_nfce("https://google.com") is None

    def test_chave_curta(self):
        assert parse_qr_nfce("https://nfce.fazenda.sp.gov.br/consulta?chNFe=12345") is None

    def test_chave_longa(self):
        assert parse_qr_nfce(f"https://nfce.fazenda.sp.gov.br/consulta?chNFe={KEY}5") is None

    def test_texto_simples(self):
        assert parse_qr_nfce("apenas um texto qualquer") is None

    def test_string_vazia(self):
        assert parse_qr_nfce("") is None

    def test_scheme_invalido(self):
        assert parse_qr_nfce(f"ftp://nfce.fazenda.sp.gov.br/consulta?chNFe={KEY}") is None
