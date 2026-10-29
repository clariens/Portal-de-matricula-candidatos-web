"""Acesso ao portal legado do Processo Seletivo (/processo-seletivo), na sessão do próprio candidato.

Por quê: a API REST só autentica ALUNO por RA, e o usuário técnico não tem acesso às rotas
/processoseletivo/* (grupo v1 → 403). O legado autentica o candidato por CPF/e-mail e só mostra as
inscrições DELE, o que dispensa a checagem de dono que o Basic de serviço exige.

Como: o login (j_security_check) abre uma sessão Java (cookie JSESSIONID). Entre requisições os cookies do
Tomcat viajam num cookie do portal CRIPTOGRAFADO e httpOnly (`portal_legado`, ver `SessoesLegado`), amarrado ao
`sid` da sessão do portal: o navegador não lê o JSESSIONID e o servidor não guarda nada (funciona com várias
instâncias, ex.: Vercel). Se o legado derrubar a sessão (timeout ~30 min) ou o cookie vencer, a chamada
responde 401 e o candidato entra de novo (a senha nunca é guardada).

Contrato observado em DEV (20/10/2026):
  GET  /r/historico        sem sessão → 401 + JSESSIONID (cria o "saved request"; sem ele o login dá 408)
  POST /j_security_check   → 303 Location /processo-seletivo/r/historico (ok)
                           → 401 + <input id="msgErro" value="usuário e/ou senha incorretos."> (falha)
  GET  /r/alterarDados     → 200 com <input id="idPessoa" value="…">
  GET  /r/historico        → tabela com <td class="col-data-…">
  GET  /logout             → 302
  GET  /r/ingresso?codCandidato&codConcurso → <form id="form-candidato"> com os dados (etapa 1)
  GET  /endereco/*         → JSON {"lyceumRetorno": {"item": …, "tipo": "OK"|"ERRO", "mensagem"}}
  POST /r/ingresso/atualizar.json → corpo = todos os campos do form (vazio → null), resposta lyceumRetorno
  GET  /r/documentosPorProcesso → <form id="frm-documentos"> com um <input type=file name="{código}"> por
                           documento; obrigatórios têm `required` e "- Obrigatório" no título. Só abre DEPOIS
                           de um atualizar.json bem-sucedido na mesma sessão (antes: página "Ocorreu um erro").
  POST /r/uploadDocumentosPorProcesso (multipart, todos os campos) → 302 /r/pagamentoIngresso (envio real em
                           DEV em 22/10/2026). ATENÇÃO: depois do envio o legado continua mostrando o formulário;
                           reenviar duplicaria os documentos. O portal consulta os enviados antes (abaixo).
  GET  /r/pagamentoIngresso → <form id="frm-pagamento"> (só abre depois de dados → documentos NA MESMA sessão;
                           antes disso responde 302). Planos em <select id="planoPagamento"> com valor
                           "planoPadrao:codigoPlano:formaPagamento:numParcelas"; a página não informa valores.
  POST /r/pagamentoIngresso/validarvoucher (form "voucher=…") → lyceumRetorno.item[0] {descPercValor, desconto}
  POST /r/pagamentoIngresso/efetivar.json → corpo = form serializado (só os campos do tipo de responsável ativo;
                           os demais ficam desabilitados no legado) → CRIA A MATRÍCULA; depois /r/terminoIngresso.
  GET  /r/documentosPorProcessoCandidato?q=base64("{concurso}separadorb64{candidato}") → documentos já entregues:
                           <td class="col-data-documento|aceito|motivo-recusa|data-entrega">, código no
                           openModalWindown('id','código',…); Aceito: title Pendente | Sim | Não.

"""

import base64
import hashlib
import html
import json
import logging
import re
import secrets
import time
import unicodedata
from contextvars import ContextVar
from dataclasses import dataclass, field

import httpx
from cryptography.fernet import Fernet, InvalidToken
from PIL import Image

from app.core.errors import GENERIC_LOGIN, LyceumIndisponivel, PortalError
from app.core.http import TLS_CONTEXT
from app.core.validators import digits, mask_cep, mask_cnpj, mask_cpf, normalizar_data_br
from app.schemas.candidato import Candidato, CandidatoUpdate, Endereco, Municipio
from app.schemas.documento import (
    Anexo,
    DocumentoStatus,
    EnvioDocumentosResultado,
    OcrResultado,
    TipoDocumento,
)
from app.schemas.inscricao import Inscricao
from app.schemas.pagamento import (
    Cobranca,
    CupomResultado,
    OpcoesPagamento,
    PagamentoIn,
    PagamentoResultado,
    Plano,
)
from app.services.imagens import preparar_imagem
from app.services.lyceum.catalogo import REGRA_POR_TIPO, TIPOS_DOCUMENTO
from app.services.lyceum.mappers import normalizar_situacao

log = logging.getLogger("lyceum")

SESSAO_TTL = 25 * 60  # abaixo dos 30 min padrão do Tomcat
CACHE_HISTORICO = 30  # s; o histórico é consultado em toda rota de inscrição (checagem de dono)
CACHE_TIPOS_DOCUMENTO = 300  # s
UPLOAD_TIMEOUT = 120.0
FOTO_MAX_PX, FOTO_QUALIDADE = 2000, 85  # foto enviada ao Lyceum: legível para a secretaria, ~300-600 KB
_TAMANHO_JAVA_RE = re.compile(r"(FileSizeLimitExceeded|SizeLimitExceeded|MaxUploadSizeExceeded)", re.IGNORECASE)
_TITULO_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)

ID_PESSOA_RE = re.compile(r'id="idPessoa"[^>]*?value="(\d+)"', re.DOTALL)
MSG_ERRO_RE = re.compile(r'id="msgErro"[^>]*?value="([^"]*)"', re.DOTALL)


class SessaoLegadoExpirada(PortalError):
    def __init__(self):
        super().__init__(401, "Sua sessão expirou. Entre novamente.")


@dataclass
class _Sessao:
    cookies: httpx.Cookies
    expira: float
    historico: tuple[float, list[Inscricao]] | None = field(default=None)
    # Progresso do wizard por inscrição: o legado não expõe em que etapa o candidato está.
    etapas: dict[str, str] = field(default_factory=dict)
    tipos_documento: tuple[float, list[TipoDocumento]] | None = None


class _Requisicao:
    """O que uma requisição tocou nas sessões (para gravar o cookie) e o que ela carregou (para liberar)."""

    def __init__(self) -> None:
        self.tocados: set[str] = set()
        self.carregados: list[str] = []


_requisicao: ContextVar[_Requisicao | None] = ContextVar("requisicao_legado", default=None)
COOKIE_LEGADO = "portal_legado"


class SessoesLegado:
    """Sessões do legado por `sid`.

    Sem `segredo`: só em memória (testes de unidade). Com `segredo` (o app sempre passa): a sessão vive no
    navegador, num cookie httpOnly criptografado (Fernet, chave derivada do PORTAL_SESSION_SECRET) com os cookies
    do Tomcat e a etapa do wizard. Nenhuma instância guarda estado (Vercel) e não há banco: o middleware em
    app/main.py carrega o cookie no início da requisição e grava a versão nova na resposta. Cookie ausente,
    adulterado ou vencido = sessão expirada, e o candidato entra de novo.
    """

    def __init__(self, segredo: str | None = None, cookie_seguro: bool = False) -> None:
        self._fernet = Fernet(_chave_fernet(segredo)) if segredo else None
        self.cookie_seguro = cookie_seguro
        self._s: dict[str, _Sessao] = {}
        self._em_uso: dict[str, int] = {}  # requisições em andamento por sid nesta instância
        self._removidos: set[str] = set()

    @property
    def no_cookie(self) -> bool:
        return self._fernet is not None

    def _tocar(self, sid: str | None) -> None:
        req = _requisicao.get()
        if req is not None and sid:
            req.tocados.add(sid)

    def criar(self, sid: str, cookies: httpx.Cookies) -> None:
        self._limpar()
        self._s[sid] = _Sessao(cookies=cookies, expira=time.time() + SESSAO_TTL)
        self._removidos.discard(sid)
        self._tocar(sid)

    def obter(self, sid: str | None) -> _Sessao:
        s = self._s.get(sid or "")
        if not s or s.expira < time.time():
            self._s.pop(sid or "", None)
            raise SessaoLegadoExpirada()
        s.expira = time.time() + SESSAO_TTL
        self._tocar(sid)
        return s

    def remover(self, sid: str | None) -> _Sessao | None:
        if sid and self.no_cookie:
            self._removidos.add(sid)
            self._tocar(sid)
        return self._s.pop(sid or "", None)

    def _limpar(self) -> None:
        agora = time.time()
        for k in [k for k, v in self._s.items() if v.expira < agora]:
            self._s.pop(k, None)

    # ---------- sessão no cookie (chamado pelo middleware) ----------
    def iniciar(self) -> _Requisicao:
        req = _Requisicao()
        _requisicao.set(req)
        return req

    def carregar(self, req: _Requisicao, sid: str, valor_cookie: str | None) -> None:
        if not self.no_cookie:
            return
        req.carregados.append(sid)
        self._em_uso[sid] = self._em_uso.get(sid, 0) + 1
        if self._em_uso[sid] > 1 and sid in self._s:
            return  # outra requisição desta instância já carregou e está usando
        self._s.pop(sid, None)
        if not valor_cookie:
            return
        try:
            d = json.loads(self._fernet.decrypt(valor_cookie.encode(), ttl=SESSAO_TTL))
        except (InvalidToken, ValueError):
            return
        if d.get("s") != sid:  # cookie de outra sessão do portal: ignora
            return
        cookies = httpx.Cookies()
        for nome, valor, dominio, caminho in d.get("c", []):
            cookies.set(nome, valor, domain=dominio, path=caminho)
        self._s[sid] = _Sessao(cookies=cookies, expira=float(d.get("x", 0)), etapas=d.get("e") or {})

    def concluir(self, req: _Requisicao) -> list[str]:
        """Cabeçalhos Set-Cookie com a sessão atualizada (ou apagada) das sessões que a requisição tocou."""
        if not self.no_cookie:
            return []
        cabecalhos = []
        try:
            for sid in req.tocados:
                s = self._s.get(sid)
                if sid in self._removidos or not s:
                    cabecalhos.append(self._set_cookie("", 0))
                    continue
                corpo = {"s": sid, "x": s.expira, "e": s.etapas,
                         "c": [[c.name, c.value, c.domain, c.path] for c in s.cookies.jar]}
                cabecalhos.append(self._set_cookie(self._fernet.encrypt(json.dumps(corpo).encode()).decode(),
                                                   SESSAO_TTL))
        finally:
            for sid in req.carregados:
                self._em_uso[sid] = self._em_uso.get(sid, 1) - 1
            for sid in set(req.carregados) | req.tocados:
                if self._em_uso.get(sid, 0) <= 0:  # ninguém mais usando: nada fica na memória da instância
                    self._em_uso.pop(sid, None)
                    self._s.pop(sid, None)
                    self._removidos.discard(sid)
        return cabecalhos

    def _set_cookie(self, valor: str, max_age: int) -> str:
        return (f"{COOKIE_LEGADO}={valor}; Path=/api; Max-Age={max_age}; HttpOnly; SameSite=Lax"
                + ("; Secure" if self.cookie_seguro else ""))


def _chave_fernet(segredo: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(b"portal-legado:" + segredo.encode()).digest())


class ClienteLegado:
    def __init__(self, base_url: str, timeout: float, sessoes: SessoesLegado,
                 max_kb_arquivo: int = 2048, max_kb_total: int = 8192):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.sessoes = sessoes
        self.max_arquivo = max_kb_arquivo * 1024
        self.max_total = max_kb_total * 1024

    def _client(self, cookies: httpx.Cookies | None = None) -> httpx.AsyncClient:
        # Um cliente por chamada: os cookies de um candidato nunca se misturam com os de outro.
        return httpx.AsyncClient(base_url=self.base, cookies=cookies, follow_redirects=False, timeout=self.timeout,
                                 verify=TLS_CONTEXT)

    # ---------- login / logout ----------
    async def login(self, sid: str, login: str, senha: str) -> int:
        """Valida CPF/e-mail + senha, guarda a sessão Java sob `sid` e devolve o idPessoa."""
        async with self._client() as c:
            try:
                await c.get("/r/historico")
                r = await c.post("/j_security_check", data={"j_username": login, "j_password": senha})
                log.warning("[lyceum-legado] POST /j_security_check → HTTP %s", r.status_code)
                if r.status_code == 401:
                    m = MSG_ERRO_RE.search(r.text)
                    msg = html.unescape(m[1]).strip() if m else ""
                    raise PortalError(401, (msg[:1].upper() + msg[1:]) if msg else GENERIC_LOGIN)
                if r.status_code not in (302, 303) or "/r/historico" not in r.headers.get("location", ""):
                    raise LyceumIndisponivel("Resposta inválida do login do Processo Seletivo")
                dados = await c.get("/r/alterarDados")
            except httpx.HTTPError:
                raise LyceumIndisponivel("Não foi possível conectar ao Processo Seletivo") from None
            m = ID_PESSOA_RE.search(dados.text) if dados.status_code == 200 else None
            if not m:
                await c.get("/logout")
                raise LyceumIndisponivel("Resposta inválida do login do Processo Seletivo")
            self.sessoes.criar(sid, httpx.Cookies(c.cookies))
            return int(m[1])

    async def logout(self, sid: str | None) -> None:
        s = self.sessoes.remover(sid)
        if not s:
            return
        try:
            async with self._client(s.cookies) as c:
                await c.get("/logout")
        except httpx.HTTPError:
            pass  # sessão Java expira sozinha

    # ---------- leitura de páginas ----------
    async def get(self, sid: str | None, path: str, params: dict | None = None) -> httpx.Response:
        return await self._req(sid, "GET", path, params=params)

    async def _req(self, sid: str | None, method: str, path: str, *, params: dict | None = None,
                   json: object = None, ajax: bool = False, files: list | None = None,
                   timeout: float | None = None, data: dict | None = None) -> httpx.Response:
        s = self.sessoes.obter(sid)
        headers = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"} if ajax else {}
        content = None
        if files is not None:
            content, headers["Content-Type"] = multipart_como_navegador(files)
        try:
            async with self._client(s.cookies) as c:
                r = await c.request(method, path, params=params, json=json, headers=headers, content=content,
                                    data=data, timeout=timeout or self.timeout)
                s.cookies = httpx.Cookies(c.cookies)
        except httpx.HTTPError:
            raise LyceumIndisponivel("Não foi possível conectar ao Processo Seletivo") from None
        log.warning("[lyceum-legado] %s %s → HTTP %s", method, path, r.status_code)
        # Sessão Java expirada: o Tomcat devolve a página de login (401) ou redireciona para /home
        if r.status_code == 401 or (r.is_redirect and "/home" in r.headers.get("location", "")):
            self.sessoes.remover(sid)
            raise SessaoLegadoExpirada()
        return r

    async def historico(self, sid: str | None) -> list[Inscricao]:
        s = self.sessoes.obter(sid)
        if s.historico and time.time() - s.historico[0] < CACHE_HISTORICO:
            return [self._com_etapa(s, i) for i in s.historico[1]]
        r = await self.get(sid, "/r/historico")
        if r.status_code != 200:
            raise LyceumIndisponivel("Não foi possível carregar suas inscrições")
        itens = parse_historico(r.text)
        s.historico = (time.time(), itens)
        return [self._com_etapa(s, i) for i in itens]

    @staticmethod
    def _com_etapa(s: _Sessao, i: Inscricao) -> Inscricao:
        i = i.model_copy(deep=True)
        etapa = s.etapas.get(i.cod_candidato)
        if etapa and i.situacao == "Convocado":
            i.etapa_atual = etapa  # type: ignore[assignment]
            i.acoes = ["continuar_matricula" if a == "matricular" else a for a in i.acoes]
        return i

    def avancar_etapa(self, sid: str | None, cod_candidato: str, etapa: str) -> None:
        ordem = ["dados", "documentos", "pagamento", "conclusao"]
        s = self.sessoes.obter(sid)
        atual = s.etapas.get(cod_candidato)
        if atual is None or ordem.index(etapa) > ordem.index(atual):
            s.etapas[cod_candidato] = etapa

    # ---------- JSON (lyceumRetorno) ----------
    @staticmethod
    def _retorno(r: httpx.Response, acao: str) -> object:
        try:
            ret = r.json().get("lyceumRetorno") or {}
        except (ValueError, AttributeError):
            raise LyceumIndisponivel(f"Resposta inválida do Processo Seletivo ({acao})") from None
        if ret.get("tipo") != "OK":
            raise PortalError(422, ret.get("mensagem") or f"O Processo Seletivo recusou a operação ({acao}).")
        return ret.get("item")

    async def get_json(self, sid: str | None, path: str, params: dict | None = None) -> object:
        return self._retorno(await self._req(sid, "GET", path, params=params, ajax=True), path)

    async def post_json(self, sid: str | None, path: str, corpo: dict) -> object:
        return self._retorno(await self._req(sid, "POST", path, json=corpo, ajax=True), path)

    # ---------- etapa 1: dados do candidato ----------
    async def form_ingresso(self, sid: str | None, cod_candidato: str, cod_concurso: str) -> dict[str, str]:
        """Abre /r/ingresso (como o botão Matricule-se) e devolve os campos do form-candidato."""
        r = await self.get(sid, "/r/ingresso", params={"codCandidato": cod_candidato, "codConcurso": cod_concurso})
        campos = parse_form(r.text, "form-candidato") if r.status_code == 200 else {}
        if campos.get("codCandidato") != cod_candidato:
            raise PortalError(409, "Esta inscrição não está aberta para matrícula no momento.")
        return campos

    async def candidato(self, sid: str | None, cod_candidato: str, cod_concurso: str) -> Candidato:
        campos = await self.form_ingresso(sid, cod_candidato, cod_concurso)
        itens = await self.get_json(sid, "/endereco/obterMunicipioCandidato",
                                    {"codCandidato": cod_candidato, "codConcurso": cod_concurso})
        municipio = itens[0] if isinstance(itens, list) and itens else {}
        return candidato_de_form(campos, municipio)

    async def municipios(self, sid: str | None, uf: str, nome: str = "") -> list[Municipio]:
        itens = await self.get_json(sid, "/endereco/listarMunicipios", {"nome": nome, "uf": uf})
        return [Municipio(codigo=str(m["codigo"]), nome=str(m["nome"])) for m in itens or [] if m.get("codigo")]

    async def atualizar_candidato(self, sid: str | None, cod_candidato: str, cod_concurso: str,
                                  dados: CandidatoUpdate) -> Candidato:
        campos = await self.form_ingresso(sid, cod_candidato, cod_concurso)  # estado fresco + campos ocultos
        codigo = await self._codigo_municipio(sid, dados.endereco, "endereco.municipio")
        await self.post_json(sid, "/r/ingresso/atualizar.json", payload_atualizar(campos, dados, codigo))
        self.invalidar_historico(sid)
        self.avancar_etapa(sid, cod_candidato, "documentos")
        return await self.candidato(sid, cod_candidato, cod_concurso)

    async def _codigo_municipio(self, sid: str | None, end: Endereco, campo: str) -> str:
        """Código Lyceum do município (vem do CEP; se a cidade foi digitada, procura pelo nome na UF)."""
        if end.municipio_codigo:
            return end.municipio_codigo
        alvo = _fold(end.municipio)
        achados = [m for m in await self.municipios(sid, end.uf, end.municipio) if _fold(m.nome) == alvo]
        if not achados:
            raise PortalError(422, "Revise os campos destacados.",
                              {campo: "Cidade não encontrada nesta UF. Use o CEP para preencher."})
        return achados[0].codigo

    # ---------- etapa 2: pagamento ----------
    async def _pagina_pagamento(self, sid: str | None) -> str:
        """Abre /r/pagamentoIngresso. O legado só libera a página depois de passar por dados → documentos
        na mesma sessão; tenta reabrir os documentos uma vez antes de pedir para o candidato confirmar os dados."""
        for tentativa in range(2):
            r = await self.get(sid, "/r/pagamentoIngresso")
            if r.status_code == 200 and 'id="frm-pagamento"' in r.text:
                return r.text
            if tentativa == 0:
                await self.get(sid, "/r/documentosPorProcesso")
        raise PortalError(409, "Confirme seus dados e documentos para seguir ao pagamento.")

    async def opcoes_pagamento(self, sid: str | None) -> OpcoesPagamento:
        pagina = parse_pagamento(await self._pagina_pagamento(sid))
        return OpcoesPagamento(tipos_responsavel=pagina.tipos_responsavel or ["Pessoa"], planos=pagina.planos)

    async def validar_cupom(self, sid: str | None, codigo: str) -> CupomResultado:
        await self._pagina_pagamento(sid)
        r = await self._req(sid, "POST", "/r/pagamentoIngresso/validarvoucher", data={"voucher": codigo}, ajax=True)
        try:
            ret = r.json().get("lyceumRetorno") or {}
        except (ValueError, AttributeError):
            ret = {}
        itens = ret.get("item") if ret.get("tipo") == "OK" else None
        if not itens:
            return CupomResultado(valido=False, mensagem=ret.get("mensagem") or "Cupom não encontrado para este curso.")
        v = itens[0] or {}
        desconto = float(v.get("desconto") or 0)
        if str(v.get("descPercValor", "")).lower().startswith("valor"):
            return CupomResultado(valido=True, mensagem=f"Cupom aplicado: desconto de {_brl(desconto)}.",
                                  desconto_valor=desconto)
        return CupomResultado(valido=True, mensagem=f"Cupom aplicado: {desconto:g}% de desconto.",
                              desconto_percentual=desconto)

    async def efetivar_pagamento(self, sid: str | None, cod_candidato: str, dados: PagamentoIn,
                                 simular: bool) -> PagamentoResultado:
        pagina = parse_pagamento(await self._pagina_pagamento(sid))
        plano = next((p for p in pagina.planos if p.codigo == dados.codigo_plano), None)
        if not plano:
            raise PortalError(422, "Escolha uma forma de pagamento.", {"codigoPlano": "Escolha um plano."})
        if not plano.disponivel:
            raise PortalError(422, plano.motivo_indisponivel or "Forma de pagamento indisponível.",
                              {"codigoPlano": "Indisponível."})
        if dados.tipo_resp not in pagina.tipos_responsavel:
            raise PortalError(422, "Tipo de responsável financeiro não disponível.", {"tipoResp": "Indisponível."})
        corpo = await self._payload_pagamento(sid, dados, plano)
        cobranca = Cobranca(forma_pagamento=plano.forma_pagamento, num_parcelas=plano.num_parcelas,
                            instrucoes=INSTRUCOES_PAGAMENTO.get(plano.forma_pagamento, INSTRUCOES_PAGAMENTO["Boleto"]))
        resumo = f"tipoResp={dados.tipo_resp} plano={plano.codigo} voucher={'sim' if dados.voucher else 'não'}"
        if simular:
            log.warning("[lyceum-legado] SIMULAÇÃO POST /r/pagamentoIngresso/efetivar.json (não enviado): %s | campos=%s",
                        resumo, sorted(k for k, v in corpo.items() if v is not None))
            return PagamentoResultado(situacao="Convocado", cobranca=cobranca, simulado=True,
                                      mensagem="Pagamento simulado (ambiente de desenvolvimento): nada foi enviado "
                                               "ao Lyceum e a matrícula não foi criada.")
        log.warning("[lyceum-legado] ENVIO REAL POST /r/pagamentoIngresso/efetivar.json: %s", resumo)
        await self.post_json(sid, "/r/pagamentoIngresso/efetivar.json", corpo)
        self.invalidar_historico(sid)
        self.avancar_etapa(sid, cod_candidato, "conclusao")
        return PagamentoResultado(situacao="Pré-Matriculado", cobranca=cobranca, mensagem="Pagamento registrado.")

    async def _payload_pagamento(self, sid: str | None, d: PagamentoIn, plano: Plano) -> dict[str, str | None]:
        """Corpo igual ao frm-pagamento serializado: só os campos do tipo de responsável escolhido
        (o legado desabilita os outros). Cartão sempre vazio na fase 1. verificafraudeInput/requerTelefoneInput
        ficam fora do <form> no legado e por isso não vão no corpo."""
        padrao, codigo, forma, parcelas = plano.codigo.split(":", 3)
        p: dict[str, str | None] = {
            "tipoResp": d.tipo_resp, "voucher": d.voucher,
            "planoPadrao": padrao, "codigoPlano": codigo, "formaPagamento": forma, "numParcelas": parcelas,
            "numeroCartao": None, "titularCartao": None, "mesValidadeCartao": None, "anoValidadeCartao": None,
            "codSegurancaCartao": None, "docPortadorCartao": None,
        }
        r = d.responsavel
        if r:
            end = r.endereco
            p.update({
                "titular": r.nome, "cep": mask_cep(end.cep), "enderecoUf": end.uf,
                "enderecoMunicipio": await self._codigo_municipio(sid, end, "responsavel.endereco.municipio"),
                "endereco": end.endereco, "enderecoNum": end.numero, "enderecoCompl": end.complemento,
                "enderecoBairro": end.bairro,
            })
            if d.tipo_resp == "OutraPessoa":
                cel, tel = digits(r.celular), digits(r.telefone)
                p.update({
                    "dataNascimento": normalizar_data_br(r.data_nascimento), "sexo": r.sexo, "cpf": mask_cpf(r.documento),
                    "rg": r.rg, "passaporte": None, "estadoCivil": r.estado_civil, "email": r.email,
                    "dddFone": tel[:2], "fone": tel[2:], "dddCelular": cel[:2], "celular": cel[2:],
                })
            else:
                p.update({"cnpj": mask_cnpj(r.documento), "inscrEstadual": r.inscricao_estadual,
                          "inscrMunicipal": r.inscricao_municipal})
        return {k: (None if v in (None, "") else re.sub(r"</?[^>]+(>|$)", "", str(v))) for k, v in p.items()}

    # ---------- etapa 1b: documentos ----------
    async def documentos_exigidos(self, sid: str | None) -> list[TipoDocumento]:
        """Lista de documentos do processo, lida da página real (muda por concurso). Cache curto por sessão."""
        s = self.sessoes.obter(sid)
        if s.tipos_documento and time.time() - s.tipos_documento[0] < CACHE_TIPOS_DOCUMENTO:
            return [t.model_copy(deep=True) for t in s.tipos_documento[1]]
        r = await self.get(sid, "/r/documentosPorProcesso")
        tipos = parse_documentos(r.text) if r.status_code == 200 else []
        if not tipos:
            # a página só abre depois de salvar os dados nesta sessão
            raise PortalError(409, "Confirme seus dados pessoais antes de enviar os documentos.")
        s.tipos_documento = (time.time(), tipos)
        return [t.model_copy(deep=True) for t in tipos]

    async def documentos_entregues(self, sid: str | None, cod_candidato: str,
                                   cod_concurso: str) -> dict[str, "Entregue"]:
        """Documentos que o Lyceum já registrou para a inscrição (tela "Documentos Ingresso" do legado)."""
        q = base64.b64encode(f"{cod_concurso}separadorb64{cod_candidato}".encode()).decode()
        r = await self.get(sid, "/r/documentosPorProcessoCandidato", params={"q": q})
        return parse_documentos_entregues(r.text) if r.status_code == 200 else {}

    async def documentos(self, sid: str | None, cod_candidato: str, cod_concurso: str) -> list[DocumentoStatus]:
        entregues = await self.documentos_entregues(sid, cod_candidato, cod_concurso)
        try:
            tipos = await self.documentos_exigidos(sid)
        except PortalError:
            if not entregues:
                raise
            tipos = [t.model_copy(deep=True) for t in TIPOS_DOCUMENTO]  # página fechada: usa o catálogo
        # anexos ainda não enviados ficam no navegador do candidato; aqui só o que o Lyceum já registrou
        lista = [_status_entregue(t, entregues[t.codigo]) if t.codigo in entregues else _status(t, None)
                 for t in tipos]
        if entregues and all(t.codigo in entregues for t in tipos if t.obrigatorio):
            self.avancar_etapa(sid, cod_candidato, "pagamento")
        return lista

    async def anexar(self, sid: str | None, cod_candidato: str, cod_concurso: str, tipo: str, nome: str,
                     conteudo: bytes, mime: str, ocr: OcrResultado | None) -> tuple[DocumentoStatus, Anexo]:
        """Valida e prepara (comprime fotos) um documento. Não guarda nada: o navegador guarda o arquivo e o
        reenvia no envio final, quando este método roda de novo para montar o que vai ao Lyceum."""
        t = next((x for x in await self.documentos_exigidos(sid) if x.codigo == tipo), None)
        if not t:
            raise PortalError(404, "Documento não solicitado neste processo.")
        if tipo in await self.documentos_entregues(sid, cod_candidato, cod_concurso):
            raise PortalError(409, "Este documento já foi enviado ao Lyceum. A secretaria vai conferir.")
        ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
        if ext not in t.extensoes:
            raise PortalError(422, f"Formato não aceito. Envie: {', '.join(e.upper() for e in t.extensoes)}.",
                              {"arquivo": "Formato não aceito."})
        if mime in ("image/jpeg", "image/png"):
            # Foto de celular (2-5 MB) é comprimida antes de ir ao Lyceum, que tem limite de tamanho
            try:
                menor, mime_menor = preparar_imagem(conteudo, FOTO_MAX_PX, FOTO_QUALIDADE)
            except (OSError, ValueError, Image.DecompressionBombError):
                menor = b""
            if menor and len(menor) < len(conteudo):
                log.warning("[lyceum-legado] foto %s comprimida: %s KB → %s KB", tipo, len(conteudo) // 1024,
                            len(menor) // 1024)
                conteudo, mime = menor, mime_menor
                nome = nome.rsplit(".", 1)[0] + ".jpg"
        if len(conteudo) > self.max_arquivo:
            raise PortalError(422, f"Este arquivo tem {_mb(len(conteudo))}; o limite do Lyceum é "
                                   f"{_mb(self.max_arquivo)} por arquivo. Reduza o arquivo ou envie uma foto.",
                              {"arquivo": "Arquivo grande demais."})
        anexo = Anexo(nome=nome, conteudo=conteudo, mime=mime, ocr=ocr, em=time.strftime("%d/%m/%Y %H:%M"))
        return _status(t, anexo), anexo

    async def enviar_documentos(self, sid: str | None, cod_candidato: str, cod_concurso: str,
                                anexos: dict[str, Anexo], simular: bool) -> EnvioDocumentosResultado:
        """Monta o multipart igual ao form frm-documentos (um campo por documento; vazio quando não anexado).

        simular=True: valida e registra, sem chamar o Lyceum (o POST real FINALIZA a inscrição).
        """
        tipos = await self.documentos_exigidos(sid)
        anexos = dict(anexos)
        entregues = await self.documentos_entregues(sid, cod_candidato, cod_concurso)
        for codigo in list(anexos):
            if codigo in entregues:  # nunca reenviar o que o Lyceum já tem
                anexos.pop(codigo)
        if not anexos and entregues and all(t.codigo in entregues for t in tipos if t.obrigatorio):
            self.avancar_etapa(sid, cod_candidato, "pagamento")
            return EnvioDocumentosResultado(
                simulado=False, mensagem="Seus documentos já foram enviados. Siga para o pagamento.",
                documentos=await self.documentos(sid, cod_candidato, cod_concurso))
        if entregues:
            # Depois do primeiro envio o legado ignora /r/uploadDocumentosPorProcesso (responde 200 sem gravar):
            # documentos novos vão um a um pela rota da tela "Documentos Ingresso".
            return await self._enviar_avulsos(sid, cod_candidato, cod_concurso, tipos, anexos, simular)
        faltando = [t.nome for t in tipos if t.obrigatorio and t.codigo not in anexos and t.codigo not in entregues]
        if faltando:
            raise PortalError(409, "Anexe os documentos obrigatórios: " + ", ".join(faltando) + ".")
        files = [(t.codigo, (anexos[t.codigo].nome, anexos[t.codigo].conteudo, anexos[t.codigo].mime)
                  if t.codigo in anexos else ("", b"", "application/octet-stream")) for t in tipos]
        resumo = ", ".join(f"{t.codigo}={len(anexos[t.codigo].conteudo)}B" for t in tipos if t.codigo in anexos)
        if simular:
            log.warning("[lyceum-legado] SIMULAÇÃO POST /r/uploadDocumentosPorProcesso (não enviado): %s", resumo)
            self.avancar_etapa(sid, cod_candidato, "pagamento")
            return EnvioDocumentosResultado(
                simulado=True,
                mensagem="Envio simulado (ambiente de desenvolvimento): nada foi enviado ao Lyceum.",
                documentos=[_status(t, anexos.get(t.codigo)) for t in tipos])

        total = sum(len(a.conteudo) for a in anexos.values())
        if total > self.max_total:
            maiores = sorted(((len(anexos[t.codigo].conteudo), t.nome) for t in tipos if t.codigo in anexos), reverse=True)
            lista = ", ".join(f"{n} ({_mb(b)})" for b, n in maiores[:2])
            raise PortalError(422, f"Os documentos somam {_mb(total)}; o limite por envio do Lyceum é "
                                   f"{_mb(self.max_total)}. Troque os maiores por arquivos menores: {lista}.")
        log.warning("[lyceum-legado] ENVIO REAL POST /r/uploadDocumentosPorProcesso: %s | total %s KB", resumo,
                    total // 1024)
        r = await self._req(sid, "POST", "/r/uploadDocumentosPorProcesso", files=files, timeout=UPLOAD_TIMEOUT)
        destino = r.headers.get("location", "")
        erro_legado = r.headers.get("mensagem") or (MSG_ERRO_RE.search(r.text)[1] if MSG_ERRO_RE.search(r.text) else "")
        titulo = _TITULO_RE.search(r.text)
        log.warning("[lyceum-legado] resposta do envio: HTTP %s location=%s erro=%s título=%s", r.status_code,
                    destino or "-", "sim" if erro_legado else "não",
                    " ".join(html.unescape(titulo[1]).split())[:80] if titulo else "-")
        if r.status_code == 413:
            raise PortalError(422, f"O envio passou do limite de tamanho do Lyceum ({_mb(total)} no total). "
                                   "Troque os maiores arquivos por versões menores.")
        if r.status_code >= 500 and _TAMANHO_JAVA_RE.search(r.text):
            raise PortalError(422, "Um dos arquivos passou do limite por arquivo do Lyceum. "
                                   "Troque o maior arquivo por uma versão menor e tente de novo.")
        if erro_legado or r.status_code not in (200, 302, 303):
            raise PortalError(422, html.unescape(erro_legado) or "O Processo Seletivo não aceitou os documentos.")
        # A resposta HTTP não basta (o legado responde 200 mesmo sem gravar): só conta o que aparece em
        # "Documentos Ingresso". Dizer "enviado" sem estar lá faria o candidato achar que entregou.
        return await self._confirmar_envio(sid, cod_candidato, cod_concurso, tipos, anexos, list(anexos))

    async def _enviar_avulsos(self, sid: str | None, cod_candidato: str, cod_concurso: str,
                              tipos: list[TipoDocumento], anexos: dict[str, "Anexo"],
                              simular: bool) -> EnvioDocumentosResultado:
        """Documento novo depois do primeiro envio: POST /r/documentosCandidato/upload, um por vez, com o campo
        de arquivo "<código>,Ingresso" (igual ao modal de upload da tela Documentos Ingresso)."""
        if not anexos:
            raise PortalError(409, "Anexe um documento para enviar.")
        resumo = ", ".join(f"{c}={len(a.conteudo)}B" for c, a in anexos.items())
        if simular:
            log.warning("[lyceum-legado] SIMULAÇÃO POST /r/documentosCandidato/upload (não enviado): %s", resumo)
            return EnvioDocumentosResultado(
                simulado=True, mensagem="Envio simulado (ambiente de desenvolvimento): nada foi enviado ao Lyceum.",
                documentos=await self.documentos(sid, cod_candidato, cod_concurso))
        log.warning("[lyceum-legado] ENVIO REAL POST /r/documentosCandidato/upload: %s", resumo)
        tentados, recusas = [], []
        for codigo, a in list(anexos.items()):
            r = await self._req(sid, "POST", "/r/documentosCandidato/upload", ajax=True, timeout=UPLOAD_TIMEOUT,
                                files=[(f"{codigo},Ingresso", (a.nome, a.conteudo, a.mime))])
            log.warning("[lyceum-legado] resposta do upload %s: HTTP %s", codigo, r.status_code)
            nome = next((t.nome for t in tipos if t.codigo == codigo), codigo)
            if r.status_code == 413:
                recusas.append(f"{nome}: arquivo maior que o limite do Lyceum")
            elif not 200 <= r.status_code < 300:
                recusas.append(f"{nome}: {html.unescape(r.headers.get('mensagem') or 'não aceito pelo Lyceum')}")
            else:
                tentados.append(codigo)
        if recusas and not tentados:
            raise PortalError(422, "O Processo Seletivo não aceitou: " + "; ".join(recusas) + ".")
        resultado = await self._confirmar_envio(sid, cod_candidato, cod_concurso, tipos, anexos, tentados)
        if recusas:
            resultado.mensagem += " Não foram aceitos: " + "; ".join(recusas) + "."
        return resultado

    async def _confirmar_envio(self, sid: str | None, cod_candidato: str, cod_concurso: str,
                               tipos: list[TipoDocumento], anexos: dict[str, "Anexo"],
                               enviados: list[str]) -> EnvioDocumentosResultado:
        """Confere em "Documentos Ingresso" o que o Lyceum gravou; tira dos anexos só o que foi confirmado."""
        entregues = await self.documentos_entregues(sid, cod_candidato, cod_concurso)
        confirmados = [c for c in enviados if c in entregues]
        faltam = [next((t.nome for t in tipos if t.codigo == c), c) for c in enviados if c not in entregues]
        for c in confirmados:
            anexos.pop(c, None)
        log.warning("[lyceum-legado] conferência do envio: gravados=%s não gravados=%s", confirmados or "-",
                    [c for c in enviados if c not in entregues] or "-")
        if not confirmados:
            raise PortalError(422, "O Processo Seletivo não registrou os documentos. Tente novamente; "
                                   "se continuar, procure a secretaria.")
        self.invalidar_historico(sid)
        if all(t.codigo in entregues for t in tipos if t.obrigatorio):
            self.avancar_etapa(sid, cod_candidato, "pagamento")
        mensagem = "Documentos enviados."
        if faltam:
            mensagem = f"Documentos enviados, exceto: {', '.join(faltam)}. Tente enviar esses de novo."
        return EnvioDocumentosResultado(simulado=False, mensagem=mensagem,
                                        documentos=await self.documentos(sid, cod_candidato, cod_concurso))

    def invalidar_historico(self, sid: str | None) -> None:
        try:
            self.sessoes.obter(sid).historico = None
        except SessaoLegadoExpirada:
            pass


# ---------- parsing de /r/historico ----------
_TBODY_RE = re.compile(r"<tbody>(.*?)</tbody>", re.DOTALL | re.IGNORECASE)
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_COL_RE = re.compile(r'<td[^>]*class="[^"]*col-data-([a-z-]+)[^"]*"[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
_INGRESSO_RE = re.compile(r"/r/ingresso\?codCandidato=(\d+)&(?:amp;)?codConcurso=([\w-]+)")
_DOCS_RE = re.compile(r"documentosPorProcessoCandidato\?q=([A-Za-z0-9+/=%]+)")
_CONTRATO_RE = re.compile(r"chamaContrato\(")


def _texto(fragmento: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragmento)).split())


def _vazio(v: str) -> str | None:
    return None if v in ("", "-") else v


def _concurso_de_docs(q: str) -> str | None:
    """`q` = base64("{codConcurso}separadorb64{codCandidato}") (link Documentos Ingresso)."""
    try:
        bruto = base64.b64decode(q.replace("%3D", "=") + "===").decode("utf-8", "ignore")
    except ValueError:
        return None
    return bruto.split("separadorb64", 1)[0] or None


def parse_historico(pagina: str) -> list[Inscricao]:
    corpo = _TBODY_RE.search(pagina)
    itens: list[Inscricao] = []
    for tr in _TR_RE.findall(corpo[1] if corpo else ""):
        col = {k.lower(): _texto(v) for k, v in _COL_RE.findall(tr)}
        cod = col.get("cod-inscricao")
        if not cod:
            continue
        ingresso = _INGRESSO_RE.search(tr)
        docs = _DOCS_RE.search(tr)
        concurso = ingresso[2] if ingresso else (_concurso_de_docs(docs[1]) if docs else None)
        opcao = col.get("opcoes-escolhidas", "")
        processo, _, curso = opcao.rpartition(" - ")
        situacao = normalizar_situacao(col.get("situacao"))
        contrato = _vazio(col.get("contrato-aceito", ""))
        acoes: list[str] = []
        if ingresso and situacao == "Convocado":
            acoes.append("matricular")
        if _CONTRATO_RE.search(tr):
            acoes.append("contrato")
        if docs:
            acoes.append("documentos")
        itens.append(Inscricao(
            cod_candidato=cod,
            cod_concurso=concurso,
            data_inscricao=col.get("inscricao", "").split(" ")[0],
            processo=processo or opcao,
            curso=curso or opcao,
            unidade=col.get("unidade", ""),
            situacao=situacao,
            forma_pagamento=_vazio(col.get("forma-pagamento", "")),
            vencimento=_vazio(col.get("vencimento-pagamento", "")),
            status_pagamento=_vazio(col.get("status-pagamento", "")),
            contrato_aceito=None if contrato is None else contrato.strip().lower() in ("sim", "s"),
            agendamento=_vazio(col.get("agendamento", "")),
            sala=_vazio(col.get("sala", "")),
            acoes=acoes,
        ))
    return itens


# ---------- etapa 1: /r/ingresso ----------
_CAMPO_RE = re.compile(r"<(input|select|textarea)\b([^>]*)>", re.IGNORECASE | re.DOTALL)


def _attr(attrs: str, nome: str) -> str | None:
    m = re.search(rf'\b{nome}\s*=\s*"([^"]*)"', attrs, re.IGNORECASE)
    return html.unescape(m[1]) if m else None


def _fold(s: str) -> str:
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().upper().strip()


def parse_form(pagina: str, form_id: str) -> dict[str, str]:
    """name → value dos campos do form. No JSP legado o <select> traz o valor no próprio atributo `value`."""
    m = re.search(rf'<form[^>]*id=["\']{re.escape(form_id)}["\'][^>]*>(.*?)</form>', pagina,
                  re.IGNORECASE | re.DOTALL)
    corpo = m[1] if m else ""
    campos: dict[str, str] = {}
    for tag, attrs in _CAMPO_RE.findall(corpo):
        nome = _attr(attrs, "name")
        if not nome or nome in campos:
            continue
        valor = _attr(attrs, "value") or ""
        if tag.lower() == "select":
            sel = re.search(rf'name="{re.escape(nome)}"[^>]*>(.*?)</select>', corpo, re.IGNORECASE | re.DOTALL)
            opt = re.search(r'<option[^>]*value="([^"]*)"[^>]*\bselected\b', sel[1]) if sel else None
            valor = html.unescape(opt[1]) if opt else valor
        campos[nome] = valor.strip()
    return campos


def candidato_de_form(c: dict[str, str], municipio: dict) -> Candidato:
    """Campos do form-candidato (+ /endereco/obterMunicipioCandidato) → modelo do portal."""
    cpf = c.get("cpf") or None
    tipo = c.get("tipoDoc") or ("passaporte" if c.get("passaporte") and not cpf else "cpf")
    sexo = c.get("sexo") if c.get("sexo") in ("M", "F", "O") else None
    cep = c.get("cep") or c.get("cepEs") or ""
    return Candidato(
        cod_candidato=c["codCandidato"], cod_concurso=c.get("codConcurso", ""),
        nome_completo=c.get("nomeCompleto", ""), data_nascimento=normalizar_data_br(c.get("dataNascimento")),
        sexo=sexo, tipo_doc=tipo, cpf=cpf, identidade=c.get("identidade") or None,
        passaporte=c.get("passaporte") or None, estado_civil=c.get("estadoCivil") or None,
        email_pessoal=c.get("emailPessoal", ""),
        celular=digits(c.get("dddFoneCelular")) + digits(c.get("celular")),
        telefone=(digits(c.get("dddFone")) + digits(c.get("telefone"))) or None,
        pais_nascimento=c.get("paisNascimento") or None, municipio_nascimento=c.get("municipioNascimento") or None,
        endereco=Endereco.model_construct(
            pais=c.get("pais") or "BRASIL", cep=mask_cep(cep) if cep else "",
            uf=str(municipio.get("uf") or ""), municipio=str(municipio.get("nome") or ""),
            municipio_codigo=c.get("enderecoMunicipioCode") or str(municipio.get("codigo") or "") or None,
            endereco=c.get("endereco", ""), numero=c.get("numero", ""),
            complemento=c.get("complemento") or None, bairro=c.get("bairro", ""),
        ),
    )


def payload_atualizar(campos: dict[str, str], d: CandidatoUpdate, cod_municipio: str) -> dict[str, str | None]:
    """Corpo de /r/ingresso/atualizar.json. Parte dos campos que a página trouxe (preserva os ocultos:
    `pessoa`, `obrigatorio*`, formação) e sobrescreve os editados. Como o sanitizeJson do legado:
    vazio vira null e tags HTML são removidas."""
    cel, tel, end = digits(d.celular), digits(d.telefone), d.endereco
    p: dict[str, str | None] = dict(campos)
    p.update({
        "nomeCompleto": d.nome_completo, "dataNascimento": d.data_nascimento, "sexo": d.sexo,
        "tipoDoc": d.tipo_doc, "cpf": d.cpf if d.tipo_doc == "cpf" else "",
        "passaporte": d.passaporte if d.tipo_doc == "passaporte" else "",
        "identidade": d.identidade or "", "estadoCivil": d.estado_civil, "emailPessoal": d.email_pessoal,
        "dddFoneCelular": cel[:2], "celular": cel[2:], "dddFone": tel[:2], "telefone": tel[2:],
        "pais": end.pais or "BRASIL", "paisSelect": end.pais or "BRASIL",
        "cep": end.cep, "cepEs": digits(end.cep), "enderecoUf": end.uf,
        "enderecoMunicipioCode": cod_municipio, "municipio": cod_municipio,
        "endereco": end.endereco, "numero": end.numero, "complemento": end.complemento or "", "bairro": end.bairro,
    })
    return {k: (None if v in (None, "") else re.sub(r"</?[^>]+(>|$)", "", str(v))) for k, v in p.items()}


# ---------- etapa 1b: /r/documentosPorProcesso ----------
_DOC_RE = re.compile(r'<h4[^>]*>(.*?)</h4>.*?<input([^>]*type="file"[^>]*)>', re.DOTALL | re.IGNORECASE)
_TITULO_RE = re.compile(r"^(?:Upload de\s+)?(.*?)(\s*-\s*obrigat[óo]rio)?\s*(?:\(Extens[õo]es permitidas:\s*(.*?)\))?$",
                        re.IGNORECASE)


def parse_documentos(pagina: str) -> list[TipoDocumento]:
    m = re.search(r'<form[^>]*id="frm-documentos"[^>]*>(.*?)</form>', pagina, re.IGNORECASE | re.DOTALL)
    tipos: list[TipoDocumento] = []
    for h4, attrs in _DOC_RE.findall(m[1] if m else ""):
        codigo = _attr(attrs, "name")
        if not codigo:
            continue
        titulo = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", h4)).split())
        t = _TITULO_RE.match(titulo)
        nome = t[1].strip() if t else titulo
        exts = re.search(r"validarExtensao\(this,\s*'\[?([^'\]]*)\]?'\)", attrs)
        extensoes = [e.strip().lower() for e in (exts[1] if exts else (t[3] if t and t[3] else "")).split(",") if e.strip()]
        obrigatorio = bool(re.search(r"\brequired\b", attrs, re.IGNORECASE)) or bool(t and t[2])
        tipos.append(TipoDocumento(codigo=codigo, nome=nome, obrigatorio=obrigatorio,
                                   regra=REGRA_POR_TIPO.get(codigo, "nome"),
                                   extensoes=extensoes or ["pdf", "jpg", "jpeg", "png"]))
    return tipos


def _status(t: TipoDocumento, a: "Anexo | None") -> DocumentoStatus:
    if not a:
        return DocumentoStatus(**t.model_dump())
    manual = a.ocr is None or a.ocr.veredito != "ok"
    return DocumentoStatus(**t.model_dump(), status="anexado", arquivo=a.nome, enviado_em=a.em,
                           ocr_veredito=a.ocr.veredito if a.ocr else None,
                           observacao="Será conferido pela secretaria." if manual else None)


CRLF = "\r\n"


def multipart_como_navegador(campos: list[tuple[str, tuple[str, bytes, str]]]) -> tuple[bytes, str]:
    """multipart/form-data igual ao de um <form> de upload no navegador.

    Diferença para o httpx: campo de arquivo vazio vai como `filename=""` (o httpx omite o filename),
    que é como o servidor Java do legado recebe "documento não anexado".
    """
    boundary = "----PortalMatricula" + secrets.token_hex(12)
    partes: list[bytes] = []
    for nome, (arquivo, conteudo, mime) in campos:
        arq = re.sub(r"[\r\n]", "", arquivo).replace('"', "%22")
        cabecalho = (f"--{boundary}{CRLF}"
                     f'Content-Disposition: form-data; name="{nome}"; filename="{arq}"{CRLF}'
                     f"Content-Type: {mime}{CRLF}{CRLF}")
        partes.append(cabecalho.encode() + conteudo + CRLF.encode())
    corpo = b"".join(partes) + f"--{boundary}--{CRLF}".encode()
    return corpo, f"multipart/form-data; boundary={boundary}"


# ---------- documentos já entregues: /r/documentosPorProcessoCandidato ----------
@dataclass
class Entregue:
    aceito: str  # "Pendente" | "Sim" | "Não"
    motivo: str | None
    data: str | None


_ENTREGUE_COD_RE = re.compile(r"openModalWindown\('[^']*',\s*'([^']+)'")
_ENTREGUE_COL_RE = re.compile(r'<td[^>]*class="[^"]*col-data-([a-z-]+)[^"]*"[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)


def parse_documentos_entregues(pagina: str) -> dict[str, Entregue]:
    itens: dict[str, Entregue] = {}
    for tr in _TR_RE.findall(pagina):
        cod = _ENTREGUE_COD_RE.search(tr)
        if not cod:
            continue
        col = {k.lower(): v for k, v in _ENTREGUE_COL_RE.findall(tr)}
        aceito = re.search(r'title="([^"]*)"', col.get("aceito", ""))
        itens[cod[1]] = Entregue(aceito=html.unescape(aceito[1]).strip() if aceito else "Pendente",
                                 motivo=_vazio(_texto(col.get("motivo-recusa", ""))) or None,
                                 data=_vazio(_texto(col.get("data-entrega", ""))) or None)
    return itens


def _status_entregue(t: TipoDocumento, e: Entregue) -> DocumentoStatus:
    # Para o candidato, documento entregue é "enviado". Aceite ou recusa é processo interno da secretaria
    # (tela de aceite de documentos do Lyceum) e não aparece no portal.
    return DocumentoStatus(**t.model_dump(), status="enviado", enviado_em=e.data)


def _mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB".replace(".", ",")


# ---------- etapa 2: /r/pagamentoIngresso ----------
FORMAS = {"BOLETO": "Boleto", "PIX": "PIX", "CARTAO": "Cartao", "CARTÃO": "Cartao"}
NOMES_FORMA = {"Boleto": "Boleto", "PIX": "PIX", "Cartao": "Cartão de crédito"}
INSTRUCOES_PAGAMENTO = {
    "Boleto": "O boleto da 1ª parcela fica disponível em Minhas inscrições.",
    "PIX": "O PIX da 1ª parcela fica disponível em Minhas inscrições.",
    "Cartao": "A cobrança é feita no cartão informado.",
}


@dataclass
class PaginaPagamento:
    planos: list[Plano]
    tipos_responsavel: list[str]


def parse_pagamento(pagina: str) -> PaginaPagamento:
    m = re.search(r'<select[^>]*id="planoPagamento"[^>]*>(.*?)</select>', pagina, re.DOTALL | re.IGNORECASE)
    planos: list[Plano] = []
    for valor, rotulo in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', m[1] if m else "", re.DOTALL):
        valor = html.unescape(valor)
        partes = valor.split(":")
        if len(partes) != 4 or not partes[1]:
            continue
        forma = FORMAS.get(_fold(partes[2]).upper(), FORMAS.get(partes[2].upper(), "Boleto"))
        texto = _texto(rotulo)
        descricao = texto.split(":", 1)[1].strip() if ":" in texto else texto
        cartao = forma == "Cartao"
        planos.append(Plano(
            codigo=valor, forma_pagamento=forma, nome=NOMES_FORMA[forma], descricao=descricao,
            plano_padrao=partes[0], num_parcelas=int(partes[3]) if partes[3].isdigit() else 1,
            disponivel=not cartao,
            motivo_indisponivel="Em breve: pagamento por cartão com tokenização segura." if cartao else None,
            tag="Mais rápido" if forma == "PIX" else None,
        ))
    tipos = [t for t in ("Pessoa", "OutraPessoa", "Empresa")
             if re.search(rf'name="tipoResp"[^>]*value="{t}"', pagina)]
    return PaginaPagamento(planos=planos, tipos_responsavel=tipos)


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
