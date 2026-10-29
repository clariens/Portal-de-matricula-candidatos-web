"""Contrato entre o BFF e o Lyceum.

Os routers só conhecem esta interface. Implementação: TechneGateway (API REST Techne v2 com Basic de
serviço + portal legado na sessão do candidato). Os testes automáticos usam um dublê em tests/fake_lyceum.py.

Todos os métodos que operam sobre uma inscrição recebem a `Inscricao` já autorizada
(ela pertence à pessoa da sessão; ver app/api/deps.py).
"""

from typing import Protocol

from app.schemas.auth import Pessoa
from app.schemas.candidato import Candidato, CandidatoUpdate, CepResultado, Municipio, Uf
from app.schemas.documento import Anexo, DocumentoStatus, EnvioDocumentosResultado, OcrResultado
from app.schemas.inscricao import Inscricao
from app.schemas.matricula import ConfirmacaoResultado, Matricula, Questionario
from app.schemas.pagamento import CupomResultado, OpcoesPagamento, PagamentoIn, PagamentoResultado


class LyceumGateway(Protocol):
    # autenticação
    async def autenticar(self, login: str, senha: str) -> Pessoa: ...

    # histórico
    async def listar_inscricoes(self, cod_pessoa: str) -> list[Inscricao]: ...

    # etapa 1 — dados
    async def obter_candidato(self, cod_pessoa: str, insc: Inscricao) -> Candidato: ...
    async def atualizar_candidato(self, cod_pessoa: str, insc: Inscricao, dados: CandidatoUpdate) -> Candidato: ...

    # endereço
    async def listar_ufs(self) -> list[Uf]: ...
    async def listar_paises(self) -> list[str]: ...
    async def listar_municipios(self, uf: str) -> list[Municipio]: ...
    async def buscar_cep(self, cep: str) -> CepResultado | None: ...

    # etapa 1b — documentos
    async def listar_documentos(self, cod_pessoa: str, insc: Inscricao) -> list[DocumentoStatus]: ...
    # Valida e prepara um documento (sem guardar: o arquivo fica no navegador até o envio final)
    async def anexar_documento(
        self,
        cod_pessoa: str,
        insc: Inscricao,
        tipo: str,
        nome_arquivo: str,
        conteudo: bytes,
        mime: str,
        ocr: OcrResultado | None,
    ) -> tuple[DocumentoStatus, Anexo]: ...
    # Envia os documentos que o navegador devolveu (o legado recebe tudo num único POST e FINALIZA a inscrição)
    async def enviar_documentos(self, cod_pessoa: str, insc: Inscricao,
                                anexos: dict[str, Anexo]) -> EnvioDocumentosResultado: ...

    # etapa 2 — pagamento
    async def opcoes_pagamento(self, cod_pessoa: str, insc: Inscricao) -> OpcoesPagamento: ...
    async def validar_cupom(self, cod_pessoa: str, insc: Inscricao, codigo: str) -> CupomResultado: ...
    async def efetivar_pagamento(self, cod_pessoa: str, insc: Inscricao, dados: PagamentoIn) -> PagamentoResultado: ...

    # etapa 3 — conclusão
    async def obter_matricula(self, cod_pessoa: str, insc: Inscricao) -> Matricula: ...
    async def confirmar_matricula(self, cod_pessoa: str, insc: Inscricao) -> ConfirmacaoResultado: ...
    async def questionarios_pendentes(self, cod_pessoa: str) -> list[Questionario]: ...

    async def ping(self) -> bool: ...

    # encerra recursos da sessão atual (ex.: sessão do candidato no portal legado)
    async def sair(self) -> None: ...
