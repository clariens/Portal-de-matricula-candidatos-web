"""Dublê do Lyceum, em memória, com os dados do protótipo. SÓ PARA TESTES AUTOMÁTICOS (pytest e e2e):
o portal não tem modo de demonstração.

Credenciais de demonstração: login `123.456.789-09` ou `ana.rocha@exemplo.com`, senha `demonstracao`.
O estado é por processo (reinicia ao reiniciar o servidor).
"""

import copy
from datetime import date, datetime, timedelta

from app.core.errors import PortalError
from app.core.validators import digits, mask_cep
from app.schemas.auth import Pessoa
from app.schemas.candidato import Candidato, CandidatoUpdate, CepResultado, Endereco, Municipio, Uf
from app.schemas.documento import DocumentoStatus, EnvioDocumentosResultado, OcrResultado
from app.schemas.inscricao import Inscricao
from app.schemas.matricula import ConfirmacaoResultado, Contrato, Disciplina, Matricula, Questionario
from app.schemas.pagamento import (
    Cobranca,
    CupomResultado,
    OpcoesPagamento,
    PagamentoIn,
    PagamentoResultado,
    Plano,
)
from app.services.lyceum.catalogo import TIPOS_DOCUMENTO, UFS

SENHA_DEMO = "demonstracao"
PESSOA = Pessoa(cod_pessoa="767919", login="123.456.789-09", nome="Ana Beatriz Rocha",
                email="ana.rocha@exemplo.com", cpf="123.456.789-09")

CANDIDATO = Candidato(
    cod_candidato="2027100000162", cod_concurso="1364",
    nome_completo="Ana Beatriz Rocha", data_nascimento="14/03/2004", sexo="F", tipo_doc="cpf",
    cpf="123.456.789-09", identidade="5123456", estado_civil="Solteiro",
    email_pessoal="ana.rocha@exemplo.com", celular="34991234567", telefone=None,
    endereco=Endereco(pais="BRASIL", cep="38440-000", uf="MG", municipio="Araguari", municipio_codigo="003105",
                      endereco="Avenida Minas Gerais", numero="1200", complemento="Apto 302", bairro="Centro"),
)

INSCRICOES = [
    Inscricao(cod_candidato="2027100000162", cod_concurso="1364", data_inscricao="01/09/2026",
              processo="2027.1 · Processo Seletivo Tradicional", curso="Medicina",
              unidade="Centro Universitário IMEPAC · Araguari", situacao="Convocado",
              forma_pagamento="PIX", vencimento="01/09/2026", status_pagamento="Aprovado"),
    Inscricao(cod_candidato="2027100000134", cod_concurso="1365", data_inscricao="01/09/2026",
              processo="2027.1 · Processo Seletivo Tradicional", curso="Medicina",
              unidade="Faculdade Zarns · Itumbiara", situacao="Confirmado",
              forma_pagamento="PIX", vencimento="01/09/2026", status_pagamento="Aprovado"),
    Inscricao(cod_candidato="2026200000598", cod_concurso="1290", data_inscricao="08/04/2026",
              processo="2026.2 · Processo Seletivo Tradicional", curso="Medicina",
              unidade="Centro Universitário IMEPAC · Araguari", situacao="Confirmado",
              forma_pagamento="PIX", vencimento="15/04/2026", status_pagamento="Aprovado"),
    Inscricao(cod_candidato="2026200000523", cod_concurso="1291", data_inscricao="06/04/2026",
              processo="2026.2 · Transferência Externa", curso="Medicina",
              unidade="Faculdade Zarns · Itumbiara", situacao="Cancelado",
              forma_pagamento="Boleto", vencimento=None, status_pagamento="Cancelado"),
]

VALOR_PARCELA = 11480.00  # ilustrativo
# Mesmo formato do legado (/r/pagamentoIngresso): codigo = "planoPadrao:codigoPlano:formaPagamento:numParcelas"
PLANOS = [
    Plano(codigo="N:PG_BOLETO:Boleto:6", forma_pagamento="Boleto", nome="Boleto",
          descricao="A modalidade de pagamento com Boleto será aplicado 5% de desconto a partir da 1ª mensalidade",
          num_parcelas=6, valor_parcela=VALOR_PARCELA, valor_total=VALOR_PARCELA * 6),
    Plano(codigo="N:PG_CARTÃO_A:Cartao:6", forma_pagamento="Cartao", nome="Cartão de crédito",
          descricao="Cobrança recorrente no cartão", num_parcelas=6, valor_parcela=VALOR_PARCELA,
          valor_total=VALOR_PARCELA * 6, disponivel=False,
          motivo_indisponivel="Em breve: pagamento por cartão com tokenização segura."),
    Plano(codigo="N:PG_PIX:PIX:6", forma_pagamento="PIX", nome="PIX",
          descricao="A modalidade de pagamento com PIX será aplicado 5% de desconto a partir da 1ª mensalidade",
          num_parcelas=6, valor_parcela=VALOR_PARCELA, valor_total=VALOR_PARCELA * 6, tag="Mais rápido"),
]
CUPONS = {"CLARIENS10": 10.0}

DISCIPLINAS = [
    Disciplina(codigo=c, nome=n) for c, n in [
        ("MED10001", "Sessão Tutorial e Integração do Conhecimento I"), ("MED10002", "Estrutura e Função I"),
        ("MED10003", "Biologia Celular"), ("MED10004", "Bioquímica"), ("MED10005", "Propedêutica Médica I"),
        ("MED10006", "Saúde Coletiva"),
    ]
]

CEPS = {
    "38440000": ("MG", "Araguari", "003105", "Centro", "Avenida Minas Gerais"),
    "74215025": ("GO", "Goiânia", "002174", "Setor Bueno", "Rua T-9"),
    "75503970": ("GO", "Itumbiara", "002238", "Centro", "Rua Paranaíba"),
    "41720200": ("BA", "Salvador", "003849", "Imbuí", "Avenida Luís Viana Filho"),
    "37551086": ("MG", "Pouso Alegre", "005191", "Santa Luzia", "Rua Dr. José Pinto de Carvalho"),
}

MUNICIPIOS = {
    "MG": [("003105", "Araguari"), ("005191", "Pouso Alegre"), ("006207", "Uberlândia")],
    "GO": [("002174", "Goiânia"), ("002238", "Itumbiara")],
    "BA": [("003849", "Salvador")],
}


class FakeLyceum:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.inscricoes = {i.cod_candidato: i.model_copy(deep=True) for i in INSCRICOES}
        self.candidatos: dict[str, Candidato] = {}
        self.documentos: dict[str, dict[str, DocumentoStatus]] = {}
        self.pagamentos: dict[str, PagamentoIn] = {}
        self.confirmados: set[str] = set()
        self.cupom: dict[str, str] = {}
        self._atualizar_acoes()

    # ---------- helpers ----------
    def _atualizar_acoes(self) -> None:
        for i in self.inscricoes.values():
            if i.situacao == "Convocado":
                i.acoes = ["continuar_matricula" if i.etapa_atual else "matricular"]
            elif i.situacao == "Pré-Matriculado":
                i.acoes = ["contrato", "documentos"]
            else:
                i.acoes = []

    def _avancar(self, cod: str, etapa: str) -> None:
        ordem = ["dados", "documentos", "pagamento", "conclusao"]
        i = self.inscricoes[cod]
        if i.etapa_atual is None or ordem.index(etapa) > ordem.index(i.etapa_atual):
            i.etapa_atual = etapa  # type: ignore[assignment]
        self._atualizar_acoes()

    def _exigir_convocado(self, insc: Inscricao) -> None:
        if self.inscricoes[insc.cod_candidato].situacao != "Convocado":
            raise PortalError(409, "Esta inscrição não está aberta para matrícula.")

    # ---------- auth ----------
    async def autenticar(self, login: str, senha: str) -> Pessoa:
        ok_login = digits(login) == digits(PESSOA.cpf) or login.strip().lower() == PESSOA.email
        if not ok_login or senha != SENHA_DEMO:
            raise PortalError(401, "Usuário ou senha inválidos.")
        return PESSOA

    async def listar_inscricoes(self, cod_pessoa: str) -> list[Inscricao]:
        if cod_pessoa != PESSOA.cod_pessoa:
            return []
        return [i.model_copy(deep=True) for i in self.inscricoes.values()]

    # ---------- candidato ----------
    async def obter_candidato(self, cod_pessoa: str, insc: Inscricao) -> Candidato:
        c = self.candidatos.get(insc.cod_candidato)
        if c:
            return c.model_copy(deep=True)
        base = CANDIDATO.model_copy(deep=True)
        base.cod_candidato, base.cod_concurso = insc.cod_candidato, insc.cod_concurso
        return base

    async def atualizar_candidato(self, cod_pessoa: str, insc: Inscricao, dados: CandidatoUpdate) -> Candidato:
        self._exigir_convocado(insc)
        c = Candidato(cod_candidato=insc.cod_candidato, cod_concurso=insc.cod_concurso, **dados.model_dump())
        self.candidatos[insc.cod_candidato] = c
        self._avancar(insc.cod_candidato, "documentos")
        return c

    # ---------- endereço ----------
    async def listar_ufs(self) -> list[Uf]:
        return UFS

    async def listar_paises(self) -> list[str]:
        return ["BRASIL", "ARGENTINA", "BOLÍVIA", "PARAGUAI", "PORTUGAL", "URUGUAI"]

    async def listar_municipios(self, uf: str) -> list[Municipio]:
        return [Municipio(codigo=c, nome=n) for c, n in MUNICIPIOS.get(uf.upper(), [])]

    async def buscar_cep(self, cep: str) -> CepResultado | None:
        d = CEPS.get(digits(cep))
        if not d:
            return None
        uf, mun, cod, bairro, end = d
        return CepResultado(cep=mask_cep(cep), uf=uf, municipio=mun, municipio_codigo=cod, bairro=bairro, endereco=end)

    # ---------- documentos ----------
    async def listar_documentos(self, cod_pessoa: str, insc: Inscricao) -> list[DocumentoStatus]:
        enviados = self.documentos.get(insc.cod_candidato, {})
        out = []
        for t in TIPOS_DOCUMENTO:
            out.append(enviados.get(t.codigo) or DocumentoStatus(**t.model_dump()))
        return [d.model_copy(deep=True) for d in out]

    async def enviar_documento(self, cod_pessoa, insc, tipo, nome_arquivo, conteudo, mime, ocr: OcrResultado | None):
        self._exigir_convocado(insc)
        t = next((x for x in TIPOS_DOCUMENTO if x.codigo == tipo), None)
        if not t:
            raise PortalError(404, "Tipo de documento não encontrado neste processo.")
        manual = ocr is None or ocr.veredito != "ok"
        st = DocumentoStatus(
            **t.model_dump(), status="anexado", arquivo=nome_arquivo,
            enviado_em=datetime.now().strftime("%d/%m/%Y %H:%M"), ocr_veredito=ocr.veredito if ocr else None,
            observacao="Será conferido pela secretaria." if manual else None,
        )
        self.documentos.setdefault(insc.cod_candidato, {})[tipo] = st
        return st.model_copy(deep=True)

    async def remover_documento(self, cod_pessoa, insc, tipo) -> DocumentoStatus:
        self._exigir_convocado(insc)
        t = next((x for x in TIPOS_DOCUMENTO if x.codigo == tipo), None)
        if not t:
            raise PortalError(404, "Tipo de documento não encontrado neste processo.")
        self.documentos.get(insc.cod_candidato, {}).pop(tipo, None)
        return DocumentoStatus(**t.model_dump())

    async def enviar_documentos(self, cod_pessoa, insc) -> EnvioDocumentosResultado:
        self._exigir_convocado(insc)
        docs = self.documentos.get(insc.cod_candidato, {})
        faltando = [t.nome for t in TIPOS_DOCUMENTO if t.obrigatorio and t.codigo not in docs]
        if faltando:
            raise PortalError(409, "Anexe os documentos obrigatórios: " + ", ".join(faltando) + ".")
        for d in docs.values():
            if d.status == "anexado":  # para o candidato, só "enviado" (aceite é da secretaria)
                d.status, d.observacao = "enviado", None
        self._avancar(insc.cod_candidato, "pagamento")
        return EnvioDocumentosResultado(simulado=False, mensagem="Documentos enviados.",
                                        documentos=await self.listar_documentos(cod_pessoa, insc))

    # ---------- pagamento ----------
    def _planos(self, desconto: float | None) -> list[Plano]:
        planos = copy.deepcopy(PLANOS)
        if desconto:
            for p in planos:
                p.valor_parcela = round(p.valor_parcela * (1 - desconto / 100), 2)
                p.valor_total = round(p.valor_parcela * p.num_parcelas, 2)
        return planos

    async def opcoes_pagamento(self, cod_pessoa, insc) -> OpcoesPagamento:
        cupom = self.cupom.get(insc.cod_candidato)
        return OpcoesPagamento(tipos_responsavel=["Pessoa", "OutraPessoa", "Empresa"],
                               planos=self._planos(CUPONS.get(cupom or "")), cupom_aplicado=cupom)

    async def validar_cupom(self, cod_pessoa, insc, codigo) -> CupomResultado:
        cod = codigo.strip().upper()
        d = CUPONS.get(cod)
        if not d:
            return CupomResultado(valido=False, mensagem="Cupom não encontrado para este curso.")
        self.cupom[insc.cod_candidato] = cod
        return CupomResultado(valido=True, mensagem=f"Cupom aplicado: {d:.0f}% de desconto.",
                              desconto_percentual=d, planos=self._planos(d))

    async def efetivar_pagamento(self, cod_pessoa, insc, dados: PagamentoIn) -> PagamentoResultado:
        self._exigir_convocado(insc)
        docs = self.documentos.get(insc.cod_candidato, {})
        faltando = [t.nome for t in TIPOS_DOCUMENTO if t.obrigatorio and docs.get(t.codigo, None) is None]
        if faltando or any(d.status == "anexado" for d in docs.values()):
            raise PortalError(409, "Envie os documentos obrigatórios antes do pagamento.")
        cupom = (dados.voucher or self.cupom.get(insc.cod_candidato) or "").upper()
        if dados.voucher and cupom not in CUPONS:
            raise PortalError(422, "Cupom inválido.", {"voucher": "Cupom não encontrado para este curso."})
        plano = next((p for p in self._planos(CUPONS.get(cupom)) if p.codigo == dados.codigo_plano), None)
        if not plano:
            raise PortalError(422, "Plano de pagamento inválido.", {"codigoPlano": "Escolha um plano."})
        if not plano.disponivel:
            raise PortalError(422, plano.motivo_indisponivel or "Plano indisponível.", {"codigoPlano": "Indisponível."})
        self.pagamentos[insc.cod_candidato] = dados
        i = self.inscricoes[insc.cod_candidato]
        venc = (date.today() + timedelta(days=3)).strftime("%d/%m/%Y")
        i.situacao, i.forma_pagamento, i.status_pagamento, i.vencimento = "Pré-Matriculado", plano.nome, "Pendente", venc
        i.contrato_aceito = False
        i.etapa_atual = "conclusao"
        self._atualizar_acoes()
        instr = ("O QR Code PIX da 1ª parcela foi enviado para o seu e-mail." if plano.forma_pagamento == "PIX"
                 else "O boleto da 1ª parcela foi enviado para o seu e-mail.")
        return PagamentoResultado(situacao=i.situacao, cobranca=Cobranca(
            forma_pagamento=plano.forma_pagamento, num_parcelas=plano.num_parcelas,
            valor_parcela=plano.valor_parcela, vencimento=venc, instrucoes=instr))

    # ---------- conclusão ----------
    async def obter_matricula(self, cod_pessoa, insc) -> Matricula:
        i = self.inscricoes[insc.cod_candidato]
        if i.situacao not in ("Pré-Matriculado", "Matriculado"):
            raise PortalError(409, "A matrícula ainda não foi gerada. Conclua o pagamento.")
        pg = self.pagamentos.get(insc.cod_candidato)
        cand = await self.obter_candidato(cod_pessoa, insc)
        cel = (pg.responsavel.celular if pg and pg.responsavel else None) or cand.celular
        return Matricula(
            matricula="2716520002", curso="09-Medicina", turma="MED-2027.1-A", periodo="2027.1",
            unidade=i.unidade, disciplinas=DISCIPLINAS,
            contrato=Contrato(status="aguardando_assinatura", destinatario=f"({cel[:2]}) •••••-{cel[-4:]}"),
            forma_pagamento=i.forma_pagamento, num_parcelas=6,
        )

    async def confirmar_matricula(self, cod_pessoa, insc) -> ConfirmacaoResultado:
        i = self.inscricoes[insc.cod_candidato]
        if i.situacao != "Pré-Matriculado":
            raise PortalError(409, "A matrícula ainda não pode ser confirmada.")
        self.confirmados.add(insc.cod_candidato)
        return ConfirmacaoResultado(situacao=i.situacao, questionarios_pendentes=await self.questionarios_pendentes(cod_pessoa))

    async def questionarios_pendentes(self, cod_pessoa) -> list[Questionario]:
        if self.confirmados:
            return [Questionario(codigo="SOCIO2027", titulo="Questionário socioeconômico do ingressante")]
        return []

    async def ping(self) -> bool:
        return True

    async def sair(self) -> None:
        return None
