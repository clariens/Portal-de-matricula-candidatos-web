"""Conferência com IA: regras (conferencia.py) e rota de anexo com um leitor falso (sem chamar a API)."""

import pytest

from app.main import app
from app.schemas.candidato import Candidato, Endereco
from app.schemas.documento import TipoDocumento
from app.services.conferencia import conferir
from app.services.ia_documentos import IAIndisponivel, LeituraDocumento, ResultadoIA
from tests.conftest import INSC, PDF, H

CAND = Candidato(
    cod_candidato="1", cod_concurso="1", nome_completo="Ana Beatriz Rocha", data_nascimento="14/03/2004", sexo="F",
    cpf="123.456.789-09", estado_civil="Solteiro", email_pessoal="a@b.com", celular="34991234567",
    endereco=Endereco(cep="38440-000", uf="MG", municipio="Araguari", endereco="Av", numero="1", bairro="Centro"),
)
RG = TipoDocumento(codigo="04", nome="Documento de Identidade", obrigatorio=True, regra="id")
CPF = TipoDocumento(codigo="05", nome="CPF", obrigatorio=True, regra="cpf")
DECL = TipoDocumento(codigo="02", nome="Declaração de Conclusão do Ensino Médio", obrigatorio=True, regra="declaracao")
RESID = TipoDocumento(codigo="11", nome="Comprovante de Residência", obrigatorio=False, regra="residencia")


def leitura(**kw) -> LeituraDocumento:
    base = {"tipo_documento": "04", "tipo_descricao": "Carteira de Identidade (RG)", "lado": "verso", "legivel": True,
            "qualidade_foto": "boa", "problemas_foto": [], "nome": "ANA BEATRIZ ROCHA", "cpf": None, "rg": "MG-1",
            "data_nascimento": "14/3/2004", "ano_conclusao": None, "instituicao": None, "cep": None}
    return LeituraDocumento(**(base | kw))


def test_rg_verso_conferido():
    r = conferir(leitura(), RG, CAND)
    assert r.veredito == "ok" and r.fonte == "ia"
    assert {c.k: c.ok for c in r.campos} == {"Documento": True, "Nome": True, "Data": True}


def test_rg_so_frente_pede_o_verso():
    r = conferir(leitura(lado="frente", nome=None, data_nascimento=None), RG, CAND)
    assert r.veredito == "atencao" and "FRENTE" in r.alertas[0]


def test_cpf_no_lugar_do_rg_e_tipo_errado():
    r = conferir(leitura(tipo_documento="05", tipo_descricao="Cartão do CPF"), RG, CAND)
    assert r.veredito == "tipo_errado" and "Cartão do CPF" in r.alertas[0]


def test_rg_com_cpf_vale_como_cpf():
    assert conferir(leitura(cpf="12345678909"), CPF, CAND).veredito == "ok"
    assert conferir(leitura(cpf="52998224725"), CPF, CAND).veredito == "divergente"


def test_nome_diferente_divergente():
    assert conferir(leitura(nome="FULANO DE TAL"), RG, CAND).veredito == "divergente"


def test_ilegivel_nao_bloqueia():
    r = conferir(leitura(legivel=False, problemas_foto=["desfoque"]), RG, CAND)
    assert r.veredito == "ilegivel" and "desfoque" in r.alertas[0]


def test_declaracao_apos_2022():
    r = conferir(leitura(tipo_documento="02", tipo_descricao="Declaração", lado="pagina_unica", ano_conclusao=2023),
                 DECL, CAND)
    assert r.veredito == "divergente" and "2023" in r.alertas[-1]


def test_certificado_no_lugar_da_declaracao_pede_atencao():
    r = conferir(leitura(tipo_documento="03", tipo_descricao="Certificado", lado="pagina_unica", ano_conclusao=2021),
                 DECL, CAND)
    assert r.veredito == "atencao"


def test_comprovante_cep_e_nome_de_terceiro():
    ok = conferir(leitura(tipo_documento="11", tipo_descricao="Conta de luz", lado="pagina_unica", nome="MARIA",
                          cep="38440-000"), RESID, CAND)
    assert ok.veredito == "ok"  # comprovante pode estar no nome dos pais
    assert conferir(leitura(tipo_documento="11", tipo_descricao="Conta", cep="74215-025"), RESID, CAND).veredito == "atencao"


def test_selfie_nao_e_documento():
    r = conferir(leitura(tipo_documento="nao_e_documento", tipo_descricao="Foto de paisagem"), RG, CAND)
    assert r.veredito == "tipo_errado"


# ---------- rota de anexo com IA ----------
class LeitorFalso:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.chamadas = resposta, erro, 0

    async def ler(self, conteudo, mime, rotulo):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return ResultadoIA(leitura=self.resposta, modelo="claude-opus-5-5", tokens_entrada=3700, tokens_saida=200,
                           custo_usd=0.019, segundos=5)


@pytest.fixture
def com_ia(logged):
    def ligar(leitor):
        app.state.leitor = leitor
        app.state.tentativas_ia = {}
        return leitor
    yield ligar
    app.state.leitor = None


def _upload(c, tipo="04", ocr_navegador=None):
    data = {"ocr": ocr_navegador} if ocr_navegador else {}
    return c.post(f"/api/v1/inscricoes/{INSC}/documentos/{tipo}", files={"arquivo": ("rg.pdf", PDF, "application/pdf")},
                  data=data, headers=H)


def test_recursos_informa_modo(logged, com_ia):
    assert logged.get("/api/v1/recursos").json() == {"conferenciaDocumentos": "navegador"}
    com_ia(LeitorFalso(leitura()))
    assert logged.get("/api/v1/recursos").json() == {"conferenciaDocumentos": "ia"}


def test_anexo_conferido_pela_ia_ignora_o_navegador(logged, com_ia):
    com_ia(LeitorFalso(leitura()))
    # o navegador "diz" tipo_errado, mas quem decide é o servidor
    r = _upload(logged, ocr_navegador='{"veredito":"tipo_errado"}')
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "anexado" and j["analise"]["veredito"] == "ok" and j["analise"]["fonte"] == "ia"


def test_documento_errado_nao_e_anexado(logged, com_ia):
    com_ia(LeitorFalso(leitura(tipo_documento="05", tipo_descricao="Cartão do CPF")))
    j = _upload(logged).json()
    assert j["status"] == "pendente" and j["analise"]["veredito"] == "tipo_errado"
    docs = {d["codigo"]: d["status"] for d in logged.get(f"/api/v1/inscricoes/{INSC}/documentos").json()}
    assert docs["04"] == "pendente"


def test_ia_fora_do_ar_vai_para_conferencia_manual(logged, com_ia):
    com_ia(LeitorFalso(erro=IAIndisponivel("conexão")))
    j = _upload(logged).json()
    assert j["status"] == "anexado" and j["analise"]["veredito"] == "erro"
    assert j["observacao"] == "Será conferido pela secretaria."


def test_limite_de_tentativas_por_documento(logged, com_ia):
    leitor = com_ia(LeitorFalso(leitura()))
    from app.config import get_settings
    limite = get_settings().ia_documentos_tentativas_por_documento
    for _ in range(limite):
        _upload(logged)
    j = _upload(logged).json()
    assert leitor.chamadas == limite  # a última não chamou a IA
    assert j["analise"]["veredito"] == "erro" and "várias vezes" in j["analise"]["alertas"][0]
