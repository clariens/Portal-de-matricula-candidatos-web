// Regras de conferência do OCR (portadas do protótipo). Funções puras: testáveis sem navegador.
import { cpfValido, digits, maskCEP, maskCPF, norm } from "../format";

export type Regra = "cpf" | "id" | "escolar" | "declaracao" | "residencia" | "foto" | "nome";
export type Veredito = "ok" | "atencao" | "divergente" | "ilegivel" | "erro";
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

/** Ano-limite da Declaração de Conclusão do Ensino Médio (documento 02). */
export const ANO_LIMITE_DECLARACAO = 2022;

export function analisar(texto: string, regra: Regra, c: DadosReferencia): OcrAnalise {
  const T = norm(texto);
  const out: OcrAnalise = { campos: [], alertas: [], veredito: "ok", texto };
  if (texto.replace(/\s/g, "").length < 25) {
    out.veredito = "ilegivel";
    out.alertas.push("Pouco texto legível. Envie uma foto mais nítida, com boa luz e sem cortes.");
    return out;
  }
  const cpfs = [...texto.matchAll(/\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}\b/g)].map((m) => maskCPF(m[0])).filter(cpfValido);
  const datas = [...texto.matchAll(/\b(\d{2})[/.-](\d{2})[/.-](\d{4})\b/g)].map((m) => `${m[1]}/${m[2]}/${m[3]}`);
  const ceps = [...texto.matchAll(/\b\d{5}-?\d{3}\b/g)].map((m) => maskCEP(m[0]));
  const anos = [...texto.matchAll(/\b(19[5-9]\d|20[0-3]\d)\b/g)].map((m) => +m[1]);
  const tokens = norm(c.nomeCompleto).split(/\s+/).filter((t) => t.length > 2);
  const hit = tokens.filter((t) => T.includes(t)).length / Math.max(1, tokens.length);
  const nomeOk = hit >= 0.6;
  const add = (k: string, v: string, ok: boolean) => out.campos.push({ k, v, ok });
  const flag = (v: Veredito, msg: string) => {
    out.veredito = v;
    out.alertas.push(msg);
  };

  add("Nome", nomeOk ? c.nomeCompleto : hit > 0 ? "parcial" : "não encontrado", nomeOk);
  if (cpfs.length) add("CPF", cpfs[0], digits(cpfs[0]) === digits(c.cpf));
  const nasc = datas.find((d) => d === c.dataNascimento);
  if (datas.length) add("Data", nasc || datas[0], !!nasc);

  if (regra === "cpf") {
    if (!cpfs.length) flag("atencao", "Nenhum CPF válido identificado no documento.");
    else if (digits(cpfs[0]) !== digits(c.cpf))
      flag("divergente", `O CPF do documento (${cpfs[0]}) é diferente do informado na etapa Dados (${c.cpf}).`);
  }
  if (regra === "id") {
    if (!nomeOk) flag("divergente", "O nome no documento não confere com o nome informado.");
    else if (datas.length && !nasc)
      flag("atencao", `Data de nascimento informada (${c.dataNascimento}) não aparece no documento.`);
  }
  if (regra === "escolar" || regra === "declaracao") {
    const ano = anos.length ? Math.max(...anos) : null;
    if (ano) add("Ano", String(ano), regra !== "declaracao" || ano <= ANO_LIMITE_DECLARACAO);
    if (!nomeOk) flag("divergente", "O nome do aluno no documento não confere.");
    else if (regra === "declaracao" && ano && ano > ANO_LIMITE_DECLARACAO)
      flag("divergente", `Conclusão em ${ano}: a declaração aceita conclusões até 31/12/${ANO_LIMITE_DECLARACAO}.`);
  }
  if (regra === "residencia") {
    const cep = ceps.find((x) => digits(x) === digits(c.cep));
    if (ceps.length) add("CEP", cep || ceps[0], !!cep);
    if (!cep) flag("atencao", `CEP do endereço informado (${c.cep}) não encontrado no comprovante.`);
  }
  if (regra === "nome" && !nomeOk)
    flag("atencao", "Nome do candidato não encontrado. O documento seguirá para conferência manual.");
  return out;
}
