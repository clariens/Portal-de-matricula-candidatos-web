"""Gateway real: API REST Lyceum Techne v2.

Autenticação de serviço: header Basic base64(usuario:senha) em TODA chamada
(não há token). O navegador nunca vê essa credencial.

Endpoints confirmados (doc "Integração com a API do Lyceum"):
  POST /v2/pessoas/autenticacao               → autenticar
  GET  /v2/alunos/{codAluno}/dados-academicos  → (matrícula / curso, quando houver)

Os demais estão em ENDPOINTS com valor None até serem descobertos no Swagger
(ver docs/integracao-techne.md). Enquanto None, o método responde 501 com a
necessidade correspondente, sem recorrer ao portal legado.
"""

import asyncio
import base64
import logging
import unicodedata
from typing import Any

import httpx

from app.config import Settings
from app.core.errors import (
    GENERIC_LOGIN,
    EndpointNaoMapeado,
    LyceumIndisponivel,
    NaoConfigurado,
    PortalError,
    sanitize_lyceum_error,
)
from app.core.session import sessao_atual
from app.core.validators import digits, mask_cep
from app.schemas.auth import Pessoa
from app.schemas.candidato import CepResultado, Municipio, Uf
from app.services.lyceum.catalogo import UFS
from app.services.lyceum.legado import ClienteLegado, SessoesLegado
from app.services.lyceum.mappers import map_pessoa, map_pessoa_lyceum, pick

log = logging.getLogger("lyceum")

VIACEP = "https://viacep.com.br/ws/{cep}/json/"

# Necessidade → caminho Techne v2 (None = ainda não mapeado).
ENDPOINTS: dict[str, str | None] = {
    "autenticar": "/v2/pessoas/autenticacao",
    "dados_academicos": "/v2/alunos/{cod_aluno}/dados-academicos",
    "listar_inscricoes": None,
    "obter_candidato": None,
    "atualizar_candidato": None,
    "listar_paises": None,
    "listar_municipios": None,
    "listar_documentos": None,
    "enviar_documento": None,
    "opcoes_pagamento": None,
    "validar_cupom": None,
    "efetivar_pagamento": None,
    "obter_matricula": None,
    "confirmar_matricula": None,
    "questionarios_pendentes": None,
}

NECESSIDADE = {
    "listar_inscricoes": "histórico de inscrições do candidato",
    "obter_candidato": "leitura dos dados do candidato",
    "atualizar_candidato": "gravação dos dados do candidato",
    "listar_paises": "lista de países",
    "listar_municipios": "lista de municípios por UF",
    "listar_documentos": "tipos de documento do processo",
    "enviar_documento": "upload de documento do ingresso",
    "opcoes_pagamento": "planos de pagamento do concurso",
    "validar_cupom": "validação de cupom",
    "efetivar_pagamento": "efetivação do pagamento",
    "obter_matricula": "matrícula, disciplinas e contrato",
    "confirmar_matricula": "conclusão do ingresso",
    "questionarios_pendentes": "questionários pendentes",
}

def lyceum_basic_header(s: Settings) -> str:
    raw = f"{s.lyceum_api_basic_user}:{s.lyceum_api_basic_password}".encode()
    return "Basic " + base64.b64encode(raw).decode()


class TechneGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient, sessoes: SessoesLegado | None = None):
        self.s = settings
        self.client = client
        self.legado = ClienteLegado(settings.lyceum_legado_base_url, settings.lyceum_timeout_leitura,
                                    sessoes or SessoesLegado(),
                                    max_kb_arquivo=settings.lyceum_upload_max_kb_por_arquivo,
                                    max_kb_total=settings.lyceum_upload_max_kb_total)

    @property
    def _usa_legado(self) -> bool:
        return self.s.lyceum_auth_modo == "legado"

    # ---------- infraestrutura ----------
    def _check_config(self) -> None:
        if not self.s.lyceum_api_base_url:
            raise NaoConfigurado("LYCEUM_API_BASE_URL")
        if not self.s.lyceum_api_basic_user or not self.s.lyceum_api_basic_password:
            raise NaoConfigurado("LYCEUM_API_BASIC_USER/LYCEUM_API_BASIC_PASSWORD")

    def _headers(self, json_body: bool) -> dict[str, str]:
        h = {"Authorization": lyceum_basic_header(self.s), "Accept": "application/json"}
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    async def _request(self, method: str, path: str, *, json: Any = None, timeout: float | None = None,
                       idempotente: bool = False) -> httpx.Response:
        self._check_config()
        url = self.s.lyceum_api_base_url.rstrip("/") + path
        tentativas = 2 if idempotente else 1  # sem retentativa em gravações
        last: Exception | None = None
        for n in range(tentativas):
            try:
                r = await self.client.request(
                    method, url, json=json, headers=self._headers(json is not None),
                    timeout=timeout or self.s.lyceum_timeout_leitura,
                )
                log.warning("[lyceum] %s %s → HTTP %s", method, path, r.status_code)
                return r
            except httpx.HTTPError as e:
                last = e
                log.warning("[lyceum] %s %s falhou (tentativa %s): %s", method, path, n + 1, type(e).__name__)
        raise LyceumIndisponivel() from last

    def _endpoint(self, chave: str) -> str:
        p = ENDPOINTS.get(chave)
        if not p:
            raise EndpointNaoMapeado(NECESSIDADE.get(chave, chave))
        return p

    @staticmethod
    def _json(r: httpx.Response) -> Any:
        try:
            return r.json()
        except ValueError:
            return None

    # ---------- autenticação ----------
    async def autenticar(self, login: str, senha: str) -> Pessoa:
        if self.s.lyceum_auth_modo == "legado":
            return await self._autenticar_candidato_legado(login, senha)
        return await self._autenticar_aluno(login, senha)

    async def _autenticar_candidato_legado(self, login: str, senha: str) -> Pessoa:
        """Valida no j_security_check (legado), guarda a sessão do candidato e busca a pessoa na API.

        A sessão legada fica no servidor sob o `sid` que a rota de login colocou em `sessao_atual`.
        """
        if not self.s.lyceum_legado_base_url:
            raise NaoConfigurado("LYCEUM_LEGADO_BASE_URL")
        self._check_config()
        sid = sessao_atual.get()
        id_pessoa = await self.legado.login(sid, login, senha)
        r = await self._request("GET", f"/v2/pessoas/idPessoa/{id_pessoa}/obterPessoa", idempotente=True)
        body = self._json(r)
        dados = body.get("data") if isinstance(body, dict) else None
        pessoa = map_pessoa_lyceum(dados, login) if r.status_code == 200 and isinstance(dados, dict) else None
        if not pessoa:
            await self.legado.logout(sid)
            raise LyceumIndisponivel("Não foi possível carregar seus dados no Lyceum")
        return pessoa

    async def sair(self) -> None:
        if self._usa_legado:
            await self.legado.logout(sessao_atual.get())

    async def _autenticar_aluno(self, login: str, senha: str) -> Pessoa:
        """POST /v2/pessoas/autenticacao — aceita só ALUNO (RA); candidato sem RA é recusado."""
        try:
            r = await self._request("POST", self._endpoint("autenticar"),
                                    json={"login": login, "password": senha})
        except LyceumIndisponivel:
            raise LyceumIndisponivel("Não foi possível conectar à API de autenticação") from None
        body = self._json(r)
        interno = body.get("status") if isinstance(body, dict) else None
        if r.status_code in (400, 401, 403) or (r.status_code >= 500 and interno in (401, 403, 412)):
            # Erro Techne: HTTP 500 + {"titulo", "status": 412, "mensagemDetalhada"}
            msg = pick(body, "mensagemDetalhada", "titulo", "message", "mensagem") if isinstance(body, dict) else None
            raise PortalError(401, sanitize_lyceum_error(msg, GENERIC_LOGIN))
        if r.status_code != 200 or not isinstance(body, dict):
            raise LyceumIndisponivel("Resposta inválida da API de autenticação")
        pessoa = map_pessoa(body, login)
        if not pessoa:
            raise LyceumIndisponivel("Resposta inválida da API de autenticação")
        return pessoa

    # ---------- endereço ----------
    async def listar_ufs(self) -> list[Uf]:
        return UFS

    async def listar_paises(self) -> list[str]:
        self._endpoint("listar_paises")
        return []

    async def listar_municipios(self, uf: str) -> list[Municipio]:
        if self._usa_legado:
            return await self.legado.municipios(sessao_atual.get(), uf)
        self._endpoint("listar_municipios")
        return []

    async def buscar_cep(self, cep: str) -> CepResultado | None:
        """Endereço pelo ViaCEP + código de município do Lyceum (exigido ao gravar).

        As duas consultas rodam em paralelo. O texto (logradouro, bairro, cidade, UF) vem do ViaCEP; o código
        do município vem do Lyceum quando ele conhece o CEP e a cidade bate. Sem código, ele é resolvido pelo
        nome da cidade na gravação (/endereco/listarMunicipios). Se o ViaCEP falhar, usa só o Lyceum.
        """
        c = digits(cep)
        lyc_task = asyncio.create_task(self._cep_lyceum(c))
        try:
            via = await self._viacep(c)
        except _CepInexistente:
            lyc_task.cancel()  # ViaCEP respondeu que o CEP não existe: não espera o Lyceum (~3 s em erro)
            return None
        try:
            lyc = await lyc_task
        except PortalError:
            lyc = None
        if not via:
            return lyc
        if lyc and lyc.uf == via.uf and _fold(lyc.municipio) == _fold(via.municipio):
            via.municipio_codigo = lyc.municipio_codigo
        return via

    async def _viacep(self, c: str) -> CepResultado | None:
        try:
            r = await self.client.get(VIACEP.format(cep=c), timeout=8)
            d = r.json() if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            log.warning("[viacep] falha na consulta")
            return None
        if isinstance(d, dict) and d.get("erro"):
            raise _CepInexistente
        if not isinstance(d, dict) or not d.get("localidade"):
            return None
        return CepResultado(cep=mask_cep(c), uf=d.get("uf", ""), municipio=d.get("localidade", ""),
                            bairro=d.get("bairro") or None, endereco=d.get("logradouro") or None)

    async def _cep_lyceum(self, c: str) -> CepResultado | None:
        """GET /v2/comum/cep/{cep}/enderecos — traz o código de município do Lyceum (ex.: 002174)."""
        r = await self._request("GET", f"/v2/comum/cep/{c}/enderecos", idempotente=True)
        body = self._json(r)
        d = body.get("data") if r.status_code == 200 and isinstance(body, dict) else None
        if not isinstance(d, dict) or not d.get("municipio"):
            return None
        return CepResultado(
            cep=mask_cep(c), uf=d.get("ufSigla") or "", municipio=d.get("nomeMunicipio") or "",
            municipio_codigo=d.get("municipio"), bairro=d.get("nomeBairro") or d.get("txbBairro") or None,
            endereco=d.get("txbLogradouro") or d.get("nomeLogradouro") or None,
        )

    async def ping(self) -> bool:
        try:
            self._check_config()
            r = await self.client.get(self.s.lyceum_api_base_url, timeout=5)
            return r.status_code < 500
        except (PortalError, httpx.HTTPError):
            return False

    # ---------- ainda não mapeados (501 até a Fase 0 de descoberta) ----------
    async def listar_inscricoes(self, cod_pessoa):
        # Legado: /r/historico na sessão do candidato (só traz as inscrições dele).
        if self._usa_legado:
            return await self.legado.historico(sessao_atual.get())
        self._endpoint("listar_inscricoes")

    async def obter_candidato(self, cod_pessoa, insc):
        # Legado: form de /r/ingresso + /endereco/obterMunicipioCandidato (sessão do candidato)
        if self._usa_legado:
            if not insc.cod_concurso or insc.situacao != "Convocado":
                raise PortalError(409, "Esta inscrição não está aberta para matrícula.")
            return await self.legado.candidato(sessao_atual.get(), insc.cod_candidato, insc.cod_concurso)
        self._endpoint("obter_candidato")

    async def atualizar_candidato(self, cod_pessoa, insc, dados):
        # Legado: POST /r/ingresso/atualizar.json com os campos da página + os editados
        if self._usa_legado and insc.cod_concurso:
            if insc.situacao != "Convocado":
                raise PortalError(409, "Esta inscrição não está aberta para matrícula.")
            return await self.legado.atualizar_candidato(sessao_atual.get(), insc.cod_candidato, insc.cod_concurso,
                                                         dados)
        self._endpoint("atualizar_candidato")

    async def listar_documentos(self, cod_pessoa, insc):
        # Legado: lista lida da página real /r/documentosPorProcesso + anexos guardados no servidor
        if self._usa_legado:
            self._exigir_convocado(insc)
            return await self.legado.documentos(sessao_atual.get(), insc.cod_candidato, insc.cod_concurso)
        self._endpoint("listar_documentos")

    async def anexar_documento(self, cod_pessoa, insc, tipo, nome_arquivo, conteudo, mime, ocr):
        # Quando mapeado: provável envio em Base64 no JSON (precedente envia_anexo_andamento),
        # com timeout de upload e atenção ao client_max_body_size do nginx (413 com ~3,9 MB em TST).
        if self._usa_legado:
            self._exigir_convocado(insc)
            return await self.legado.anexar(sessao_atual.get(), insc.cod_candidato, insc.cod_concurso, tipo,
                                            nome_arquivo, conteudo, mime, ocr)
        self._endpoint("enviar_documento")

    async def enviar_documentos(self, cod_pessoa, insc, anexos):
        if self._usa_legado:
            self._exigir_convocado(insc)
            return await self.legado.enviar_documentos(sessao_atual.get(), insc.cod_candidato, insc.cod_concurso,
                                                       anexos, simular=self.s.lyceum_documentos_modo != "enviar")
        self._endpoint("enviar_documento")

    @staticmethod
    def _exigir_convocado(insc):
        if insc.situacao != "Convocado":
            raise PortalError(409, "Esta inscrição não está aberta para matrícula.")

    async def opcoes_pagamento(self, cod_pessoa, insc):
        if self._usa_legado:
            self._exigir_convocado(insc)
            return await self.legado.opcoes_pagamento(sessao_atual.get())
        self._endpoint("opcoes_pagamento")

    async def validar_cupom(self, cod_pessoa, insc, codigo):
        if self._usa_legado:
            self._exigir_convocado(insc)
            return await self.legado.validar_cupom(sessao_atual.get(), codigo)
        self._endpoint("validar_cupom")

    async def efetivar_pagamento(self, cod_pessoa, insc, dados):
        # Legado: efetivar.json CRIA A MATRÍCULA; em DEV fica em simulação (LYCEUM_PAGAMENTO_MODO)
        if self._usa_legado:
            self._exigir_convocado(insc)
            return await self.legado.efetivar_pagamento(sessao_atual.get(), insc.cod_candidato, dados,
                                                        simular=self.s.lyceum_pagamento_modo != "enviar")
        self._endpoint("efetivar_pagamento")

    async def obter_matricula(self, cod_pessoa, insc):
        self._endpoint("obter_matricula")

    async def confirmar_matricula(self, cod_pessoa, insc):
        self._endpoint("confirmar_matricula")

    async def questionarios_pendentes(self, cod_pessoa):
        self._endpoint("questionarios_pendentes")


class _CepInexistente(Exception):
    """ViaCEP respondeu {"erro": true}: o CEP não existe (diferente de o ViaCEP estar fora do ar)."""


def _fold(s: str | None) -> str:
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().upper().strip()
