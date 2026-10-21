"""Tabelas de referência compartilhadas pelos gateways."""

from app.schemas.candidato import Uf
from app.schemas.documento import TipoDocumento

# Tipos de documento do processo (mapa de /r/documentosPorProcesso, ordem do DOM).
# Em modo techne a lista deve vir do Lyceum; esta tabela é o fallback e a referência de regras de OCR.
TIPOS_DOCUMENTO: list[TipoDocumento] = [
    TipoDocumento(codigo="05", nome="CPF", obrigatorio=True, regra="cpf"),
    TipoDocumento(codigo="04", nome="Documento de Identidade", obrigatorio=True, regra="id"),
    TipoDocumento(codigo="03", nome="Certificado de Conclusão / Histórico Escolar", obrigatorio=True,
                  regra="escolar"),
    TipoDocumento(codigo="02", nome="Declaração de Conclusão do Ensino Médio até 31/12/2022",
                  obrigatorio=True, regra="declaracao"),
    TipoDocumento(codigo="11", nome="Comprovante de Residência", obrigatorio=False, regra="residencia"),
    TipoDocumento(codigo="01", nome="Foto 3x4", obrigatorio=False, regra="foto"),
    TipoDocumento(codigo="09", nome="Certidão de Nascimento", obrigatorio=False),
    TipoDocumento(codigo="10", nome="Certidão de Casamento", obrigatorio=False),
    TipoDocumento(codigo="06", nome="Fotocópia do Título de Eleitor", obrigatorio=False),
    TipoDocumento(codigo="07", nome="Comprovante de Votação – última eleição", obrigatorio=False),
    TipoDocumento(codigo="08", nome="Certificado Militar", obrigatorio=False),
    TipoDocumento(codigo="14", nome="Cartão de Vacina", obrigatorio=False),
    TipoDocumento(codigo="12", nome="Histórico de Graduação – IES de origem", obrigatorio=False),
    TipoDocumento(codigo="13", nome="Financeiro – Termo de confissão de dívida", obrigatorio=False),
]

REGRA_POR_TIPO = {t.codigo: t.regra for t in TIPOS_DOCUMENTO}

UFS: list[Uf] = [
    Uf(sigla=s, nome=n)
    for s, n in [
        ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"), ("AM", "Amazonas"), ("BA", "Bahia"),
        ("CE", "Ceará"), ("DF", "Distrito Federal"), ("ES", "Espírito Santo"), ("GO", "Goiás"),
        ("MA", "Maranhão"), ("MT", "Mato Grosso"), ("MS", "Mato Grosso do Sul"), ("MG", "Minas Gerais"),
        ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"), ("PE", "Pernambuco"), ("PI", "Piauí"),
        ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"), ("RS", "Rio Grande do Sul"),
        ("RO", "Rondônia"), ("RR", "Roraima"), ("SC", "Santa Catarina"), ("SP", "São Paulo"),
        ("SE", "Sergipe"), ("TO", "Tocantins"),
    ]
]

EXTENSOES_ACEITAS = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

# Assinaturas mágicas para validar o conteúdo real do arquivo (não confiar só na extensão)
MAGIC = {
    "application/pdf": [b"%PDF"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}
