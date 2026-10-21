"""Regras de conferência de documentos: decidem ✓/⚠/✗ a partir da LEITURA (feita pela IA).

Sequência (igual à da tela): legível → é o documento pedido? → lado (RG) → os dados conferem?
O modelo nunca decide aprovação: ele só informa o que leu; estas regras comparam com o cadastro.
"""

import unicodedata

from app.core.validators import digits, normalizar_data_br
from app.schemas.candidato import Candidato
from app.schemas.documento import OcrCampo, OcrResultado, TipoDocumento
from app.services.ia_documentos import TIPOS_RECONHECIDOS, LeituraDocumento

ANO_LIMITE_DECLARACAO = 2022

# Tipos lidos aceitos em cada campo do Lyceum, além do próprio código.
#   "ok": vale igual ao pedido | "atencao": a secretaria confere se substitui o pedido
SUBSTITUTOS: dict[str, dict[str, str]] = {
    "05": {"04": "ok", "cnh": "ok"},  # RG/CIN/CNH trazem o CPF (vale se o número conferir)
    "04": {"cnh": "ok"},
    "03": {"02": "atencao"},
    "02": {"03": "atencao"},
}


def _fold(s: str | None) -> str:
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().upper()


def _nome_confere(lido: str | None, cadastro: str) -> bool:
    tokens = [t for t in _fold(cadastro).split() if len(t) > 2]
    alvo = _fold(lido)
    return bool(tokens) and sum(t in alvo for t in tokens) / len(tokens) >= 0.6


def _artigo(nome: str) -> str:
    n = _fold(nome)
    masculinos = ("CPF", "CERTIFICADO", "COMPROVANTE", "DOCUMENTO", "HISTORICO", "CARTAO", "FINANCEIRO", "TERMO")
    return "o" if n.startswith(masculinos) else "a"


def conferir(leitura: LeituraDocumento, tipo: TipoDocumento, cand: Candidato) -> OcrResultado:
    campos: list[OcrCampo] = []
    alertas: list[str] = []
    veredito = "ok"

    def flag(v: str, msg: str) -> None:
        nonlocal veredito
        if not (veredito == "divergente" and v == "atencao"):
            veredito = v
        alertas.append(msg)

    def resultado(v: str | None = None) -> OcrResultado:
        return OcrResultado(veredito=v or veredito, campos=campos, alertas=alertas, fonte="ia")

    problemas = f" ({', '.join(leitura.problemas_foto)})" if leitura.problemas_foto else ""

    # 1. legível?
    if not leitura.legivel:
        alertas.append(f"Não conseguimos ler este arquivo{problemas}. Envie uma foto mais nítida, com boa luz e sem "
                       "reflexo, ou mantenha este arquivo para a secretaria conferir.")
        return resultado("ilegivel")

    # 2. é o documento pedido?
    lido, esperado = leitura.tipo_documento, tipo.codigo
    substituto = SUBSTITUTOS.get(esperado, {}).get(lido)
    if lido != esperado and not substituto:
        descricao = leitura.tipo_descricao or TIPOS_RECONHECIDOS.get(lido, "outro documento")
        campos.append(OcrCampo(k="Documento", v=descricao, ok=False))
        alertas.append(f"Este arquivo parece ser: {descricao}. Esperávamos {_artigo(tipo.nome)} {tipo.nome}. "
                       "Confira e envie o documento certo.")
        return resultado("tipo_errado")
    campos.append(OcrCampo(k="Documento", v=leitura.tipo_descricao or tipo.nome, ok=True))
    if substituto == "atencao":
        flag("atencao", f"Você enviou {TIPOS_RECONHECIDOS.get(lido, lido).lower()} no lugar de "
                        f"{_artigo(tipo.nome)} {tipo.nome}. A secretaria vai conferir se ele substitui o pedido.")

    if tipo.regra == "foto":
        return resultado()

    # 3. lado do documento (frente e verso)
    eh_identidade = lido in ("04",) and esperado in ("04", "05")
    if eh_identidade and leitura.lado == "frente":
        flag("atencao", "Recebemos só a FRENTE da identidade. Envie um arquivo com frente e verso: o verso traz nome "
                        "e data de nascimento.")
    # só o verso: é o lado com nome e data de nascimento, que conferimos abaixo

    # 4. os dados conferem?
    regra = tipo.regra
    tem_nome = bool(leitura.nome)
    nome_ok = _nome_confere(leitura.nome, cand.nome_completo)
    if tem_nome:
        campos.append(OcrCampo(k="Nome", v=leitura.nome or "", ok=nome_ok))
    cpf_lido = digits(leitura.cpf)
    if len(cpf_lido) == 11:
        campos.append(OcrCampo(k="CPF", v=cpf_lido, ok=cpf_lido == digits(cand.cpf)))
    nasc = normalizar_data_br(leitura.data_nascimento) if leitura.data_nascimento else ""
    if nasc:
        campos.append(OcrCampo(k="Data", v=nasc, ok=nasc == cand.data_nascimento))

    if regra == "cpf":
        if len(cpf_lido) != 11:
            flag("atencao", "Não conseguimos ler o número do CPF no arquivo. A secretaria vai conferir.")
        elif cpf_lido != digits(cand.cpf):
            flag("divergente", "O CPF do documento é diferente do informado em Seus dados.")
    if regra == "id" and tem_nome:
        if not nome_ok:
            flag("divergente", "O nome no documento não confere com o nome informado em Seus dados.")
        elif nasc and nasc != cand.data_nascimento:
            flag("atencao", f"A data de nascimento do documento ({nasc}) é diferente da informada "
                            f"({cand.data_nascimento}).")
    if regra in ("escolar", "declaracao"):
        ano = leitura.ano_conclusao
        if ano:
            campos.append(OcrCampo(k="Ano", v=str(ano), ok=regra != "declaracao" or ano <= ANO_LIMITE_DECLARACAO))
        if tem_nome and not nome_ok:
            flag("divergente", "O nome do aluno no documento não confere com o nome informado.")
        elif not tem_nome:
            flag("atencao", "Não encontramos o nome do aluno no documento. A secretaria vai conferir.")
        if regra == "declaracao" and ano and ano > ANO_LIMITE_DECLARACAO:
            flag("divergente", f"Conclusão em {ano}: esta declaração só vale para conclusões até "
                               f"31/12/{ANO_LIMITE_DECLARACAO}.")
    if regra == "residencia":
        cep_lido = digits(leitura.cep)
        if cep_lido:
            campos.append(OcrCampo(k="CEP", v=leitura.cep or "", ok=cep_lido == digits(cand.endereco.cep)))
        if cep_lido != digits(cand.endereco.cep):
            flag("atencao", f"O CEP do seu endereço ({cand.endereco.cep}) não aparece no comprovante. "
                            "A secretaria vai conferir.")
    if regra == "nome" and not nome_ok:
        flag("atencao", "Seu nome não foi encontrado no documento. A secretaria vai conferir.")

    if leitura.qualidade_foto == "ruim" and veredito == "ok":
        flag("atencao", f"A foto está com qualidade baixa{problemas}. A secretaria vai conferir.")
    return resultado()
