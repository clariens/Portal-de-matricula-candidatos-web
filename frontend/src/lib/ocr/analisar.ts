// Regras de conferência do OCR. Funções puras: testáveis sem navegador.
//
// Sequência para cada arquivo anexado (ver EtapaDocumentos):
//   1. legível?            → senão "ilegivel"     (outro arquivo OU conferência manual)
//   2. é o documento certo? → se a leitura foi BOA e não é: "tipo_errado" (bloqueia: só aceita outro arquivo)
//                             se a leitura foi FRACA: "erro" (não dá para afirmar; outro arquivo OU manual)
//   3. os dados conferem?   → senão "divergente"   (outro arquivo OU conferência manual)
//                             ou "atencao"         (anexa com aviso)
//   4. tudo certo           → "ok"                 (anexa sozinho)
import { cpfValido, digits, maskCEP, maskCPF, norm } from "../format";

export type Regra = "cpf" | "id" | "escolar" | "declaracao" | "residencia" | "foto" | "nome";
export type Veredito = "ok" | "atencao" | "divergente" | "tipo_errado" | "ilegivel" | "erro";
export interface OcrCampo { k: string; v: string; ok: boolean }
export interface OcrAnalise {
  veredito: Veredito;
  campos: OcrCampo[];
  alertas: string[];
  texto: string;
  confianca?: number;
}
export interface DadosReferencia {
  nomeCompleto: string;
  cpf?: string | null;
  dataNascimento: string;
  cep: string;
}
export interface DocumentoEsperado {
  codigo: string;
  nome: string;
  regra?: Regra | string | null;
}

/**
 * Abaixo desta confiança o texto lido não serve para afirmar que o documento está errado.
 * Medido em 21/10/2026: fotos reais de RG (fundo verde de segurança, plástico, celular) ficaram entre 25% e 47%;
 * documentos nítidos ficam acima de 90%.
 */
export const CONFIANCA_MINIMA = 60;

/** Ano-limite da Declaração de Conclusão do Ensino Médio (documento 02). */
export const ANO_LIMITE_DECLARACAO = 2022;

/** O que o candidato pode fazer com cada resultado. */
export const ACAO_POR_VEREDITO: Record<Veredito, "anexar" | "anexar_com_aviso" | "manual_ou_trocar" | "trocar"> = {
  ok: "anexar",
  atencao: "anexar_com_aviso",
  divergente: "manual_ou_trocar",
  erro: "manual_ou_trocar", // não deu para conferir automaticamente (leitura fraca, PDF protegido…)
  tipo_errado: "trocar", // só com leitura boa: aí há certeza de que é outro documento
  ilegivel: "manual_ou_trocar", // foto ruim de documento verdadeiro não pode travar o candidato
};

/**
 * Marcas que identificam cada documento (pelo código do Lyceum). Basta UMA aparecer no texto lido.
 * Escritas sem acento e em maiúsculas; o texto do OCR é normalizado do mesmo jeito.
 * Documento sem marcas definidas (ex.: Foto 3x4) não passa por esta verificação.
 */
export const MARCAS_DOCUMENTO: Record<string, string[]> = {
  "05": ["CADASTRO DE PESSOAS FISICAS", "CADASTRO DE PESSOA FISICA", "RECEITA FEDERAL", "COMPROVANTE DE INSCRICAO", "CPF"],
  "04": ["REGISTRO GERAL", "CARTEIRA DE IDENTIDADE", "IDENTIDADE", "INSTITUTO DE IDENTIFICACAO", "SECRETARIA DE SEGURANCA",
    "HABILITACAO", "ASSINATURA DO TITULAR", "FILIACAO"],
  "03": ["HISTORICO ESCOLAR", "HISTORICO", "CERTIFICADO DE CONCLUSAO", "CERTIFICADO", "ENSINO MEDIO"],
  "02": ["DECLARACAO", "DECLARAMOS", "DECLARA"],
  "11": ["CONTA", "FATURA", "ENERGIA", "AGUA", "SANEAMENTO", "TELEFONE", "INTERNET", "CONSUMO", "VENCIMENTO",
    "ALUGUEL", "RESIDENCIA", "CONDOMINIO", "BOLETO", "ENDERECO"],
  "09": ["CERTIDAO DE NASCIMENTO", "NASCIMENTO", "REGISTRO CIVIL"],
  "10": ["CERTIDAO DE CASAMENTO", "CASAMENTO", "REGISTRO CIVIL"],
  "06": ["TITULO ELEITORAL", "TITULO DE ELEITOR", "JUSTICA ELEITORAL", "ELEITOR"],
  "07": ["COMPROVANTE DE VOTACAO", "QUITACAO ELEITORAL", "JUSTICA ELEITORAL", "TRIBUNAL SUPERIOR ELEITORAL", "ELEITOR"],
  "08": ["CERTIFICADO DE RESERVISTA", "RESERVISTA", "ALISTAMENTO", "DISPENSA DE INCORPORACAO", "MINISTERIO DA DEFESA",
    "EXERCITO", "MILITAR"],
  "14": ["VACINA", "VACINACAO", "IMUNIZACAO", "DOSE"],
  "12": ["HISTORICO", "GRADUACAO", "ENSINO SUPERIOR", "DISCIPLINA", "CARGA HORARIA"],
  "13": ["CONFISSAO DE DIVIDA", "CONFISSAO", "TERMO"],
};

/** Texto normalizado para busca de marcas: sem acento, maiúsculo, só letras/dígitos separados por 1 espaço. */
const paraBusca = (s: string) => ` ${norm(s).replace(/[^A-Z0-9]+/g, " ").trim()} `;

export function identificarTipo(texto: string, codigo: string): { reconhecido: boolean; marca?: string } {
  const marcas = MARCAS_DOCUMENTO[codigo];
  if (!marcas) return { reconhecido: true };
  const t = paraBusca(texto);
  const marca = marcas.find((m) => t.includes(paraBusca(m)));
  return { reconhecido: !!marca, marca };
}

const leituraFracaMsg = (conf: number) =>
  `Não conseguimos conferir este documento automaticamente: a leitura da foto ficou fraca (${conf}%). ` +
  "Envie uma foto mais nítida (documento inteiro, de frente, com boa luz e sem reflexo) ou mantenha este arquivo para a secretaria conferir.";

/** @param confianca confiança média do OCR (0–100); abaixo de CONFIANCA_MINIMA o resultado nunca bloqueia. */
export function analisar(texto: string, doc: DocumentoEsperado, c: DadosReferencia, confianca?: number): OcrAnalise {
  const regra = (doc.regra ?? "nome") as Regra;
  const T = norm(texto);
  const out: OcrAnalise = { campos: [], alertas: [], veredito: "ok", texto, confianca };
  const leituraFraca = confianca !== undefined && confianca < CONFIANCA_MINIMA;

  // 1. legível?
  if (texto.replace(/\s/g, "").length < 25) {
    out.veredito = "ilegivel";
    out.alertas.push("Não conseguimos ler este arquivo. Envie uma foto mais nítida, com boa luz, sem cortes e sem reflexo, ou mantenha este arquivo para a secretaria conferir.");
    return out;
  }

  // 2. é o documento esperado?
  const tipo = identificarTipo(texto, doc.codigo);
  if (!tipo.reconhecido && leituraFraca) {
    out.veredito = "erro";
    out.alertas.push(leituraFracaMsg(confianca!));
    return out;
  }
  if (!tipo.reconhecido) {
    out.veredito = "tipo_errado";
    out.campos.push({ k: "Documento", v: "não reconhecido", ok: false });
    out.alertas.push(`Este arquivo não parece ser ${artigo(doc.nome)} ${doc.nome}. Confira se anexou o documento certo e envie outro arquivo.`);
    return out;
  }
  if (tipo.marca) out.campos.push({ k: "Documento", v: doc.nome, ok: true });

  // 3. os dados conferem?
  const cpfs = [...texto.matchAll(/\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}\b/g)].map((m) => maskCPF(m[0])).filter(cpfValido);
  // aceita dia/mês com 1 dígito (o RG antigo traz "26/9/2004")
  const datas = [...texto.matchAll(/\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b/g)].map(
    (m) => `${m[1].padStart(2, "0")}/${m[2].padStart(2, "0")}/${m[3]}`,
  );
  const ceps = [...texto.matchAll(/\b\d{5}-?\d{3}\b/g)].map((m) => maskCEP(m[0]));
  const anos = [...texto.matchAll(/\b(19[5-9]\d|20[0-3]\d)\b/g)].map((m) => +m[1]);
  const tokens = norm(c.nomeCompleto).split(/\s+/).filter((t) => t.length > 2);
  const hit = tokens.filter((t) => T.includes(t)).length / Math.max(1, tokens.length);
  const nomeOk = hit >= 0.6;
  const add = (k: string, v: string, ok: boolean) => out.campos.push({ k, v, ok });
  const flag = (v: Veredito, msg: string) => {
    // divergente prevalece sobre atencao
    if (!(out.veredito === "divergente" && v === "atencao")) out.veredito = v;
    out.alertas.push(msg);
  };

  add("Nome", nomeOk ? c.nomeCompleto : hit > 0 ? "parcial" : "não encontrado", nomeOk);
  if (cpfs.length) add("CPF", cpfs[0], digits(cpfs[0]) === digits(c.cpf));
  const nasc = datas.find((d) => d === c.dataNascimento);
  if (datas.length) add("Data", nasc || datas[0], !!nasc);

  if (regra === "cpf") {
    if (!cpfs.length) flag("atencao", "Não encontramos o número do CPF no arquivo. A secretaria vai conferir.");
    else if (digits(cpfs[0]) !== digits(c.cpf))
      flag("divergente", `O CPF do documento (${cpfs[0]}) é diferente do informado em Seus dados (${c.cpf}).`);
  }
  if (regra === "id") {
    if (!nomeOk) flag("divergente", "O nome no documento não confere com o nome informado em Seus dados.");
    else if (datas.length && !nasc)
      flag("atencao", `A data de nascimento informada (${c.dataNascimento}) não aparece no documento.`);
  }
  if (regra === "escolar" || regra === "declaracao") {
    const ano = anos.length ? Math.max(...anos) : null;
    if (ano) add("Ano", String(ano), regra !== "declaracao" || ano <= ANO_LIMITE_DECLARACAO);
    if (!nomeOk) flag("divergente", "O nome do aluno no documento não confere com o nome informado.");
    else if (regra === "declaracao" && ano && ano > ANO_LIMITE_DECLARACAO)
      flag("divergente", `Conclusão em ${ano}: esta declaração só vale para conclusões até 31/12/${ANO_LIMITE_DECLARACAO}.`);
  }
  if (regra === "residencia") {
    const cep = ceps.find((x) => digits(x) === digits(c.cep));
    if (ceps.length) add("CEP", cep || ceps[0], !!cep);
    if (!cep) flag("atencao", `O CEP do seu endereço (${c.cep}) não aparece no comprovante. A secretaria vai conferir.`);
  }
  if (regra === "nome" && !nomeOk)
    flag("atencao", "Seu nome não foi encontrado no documento. A secretaria vai conferir.");
  // leitura fraca: uma "divergência" pode ser só erro de leitura; não acusar o candidato
  if (leituraFraca && out.veredito === "divergente") {
    out.veredito = "erro";
    out.alertas = [leituraFracaMsg(confianca!)];
  }
  return out;
}

/** "o CPF", "a Declaração…" — para mensagens naturais. */
function artigo(nome: string): string {
  const n = norm(nome);
  return /^(CPF|CERTIFICADO|COMPROVANTE|DOCUMENTO|HISTORICO|CARTAO|FINANCEIRO|TERMO)/.test(n) ? "o" : "a";
}
