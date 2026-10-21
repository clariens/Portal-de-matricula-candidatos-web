import { describe, expect, it } from "vitest";
import { cnpjValido, cpfValido, dataValida, maskCEP, maskCNPJ, maskCPF, maskDate, maskPhone } from "./format";
import { ACAO_POR_VEREDITO, analisar, identificarTipo } from "./ocr/analisar";

const ref = { nomeCompleto: "Ana Beatriz Rocha", cpf: "123.456.789-09", dataNascimento: "14/03/2004", cep: "38440-000" };

describe("máscaras", () => {
  it("formata", () => {
    expect(maskCPF("12345678909")).toBe("123.456.789-09");
    expect(maskCNPJ("11222333000181")).toBe("11.222.333/0001-81");
    expect(maskDate("14032004")).toBe("14/03/2004");
    expect(maskCEP("38440000")).toBe("38440-000");
    expect(maskPhone("34991234567")).toBe("(34) 99123-4567");
    expect(maskPhone("6432221111")).toBe("(64) 3222-1111");
  });
  it("valida CPF, CNPJ e data", () => {
    expect(cpfValido("123.456.789-09")).toBe(true);
    expect(cpfValido("111.111.111-11")).toBe(false);
    expect(cnpjValido("11.222.333/0001-81")).toBe(true);
    expect(cnpjValido("11.222.333/0001-82")).toBe(false);
    expect(dataValida("31/02/2004")).toBe(false);
    expect(dataValida("29/02/2004")).toBe(true);
  });
});

const CPF = { codigo: "05", nome: "CPF", regra: "cpf" };
const RG = { codigo: "04", nome: "Documento de Identidade", regra: "id" };
const HIST = { codigo: "03", nome: "Certificado de Conclusão / Histórico Escolar", regra: "escolar" };
const DECL = { codigo: "02", nome: "Declaração de Conclusão do Ensino Médio até 31/12/2022", regra: "declaracao" };
const RESID = { codigo: "11", nome: "Comprovante de Residência", regra: "residencia" };
const FOTO = { codigo: "01", nome: "Foto 3X4", regra: "foto" };

const textoCPF = "REPUBLICA FEDERATIVA DO BRASIL CADASTRO DE PESSOAS FÍSICAS NOME ANA BEATRIZ ROCHA CPF 123.456.789-09 NASC 14/03/2004";
const textoRG = "REPÚBLICA FEDERATIVA DO BRASIL CARTEIRA DE IDENTIDADE REGISTRO GERAL 5123456 NOME ANA BEATRIZ ROCHA FILIAÇÃO 14/03/2004";
const textoConta = "COMPANHIA ENERGETICA FATURA DE ENERGIA ELETRICA CONSUMO KWH ANA BEATRIZ ROCHA CEP 38440-000 VENCIMENTO";

describe("analisar: sequência legível → tipo → dados", () => {
  it("ilegível com pouco texto: outro arquivo ou conferência manual (não trava)", () => {
    const r = analisar("abc", CPF, ref);
    expect(r.veredito).toBe("ilegivel");
    expect(ACAO_POR_VEREDITO[r.veredito]).toBe("manual_ou_trocar");
  });
  it("leitura fraca de documento verdadeiro NÃO vira 'não reconhecido' (foto real de RG ~35%)", () => {
    const lixo = "a. pair es EA .. Es O os AAA a EDOS o O E a aaa ND JA 9 e sh peso o ni o MEC sm REA no FR mm";
    const r = analisar(lixo, RG, ref, 37);
    expect(r.veredito).toBe("erro");
    expect(ACAO_POR_VEREDITO[r.veredito]).toBe("manual_ou_trocar");
    expect(r.alertas[0]).toContain("leitura da foto ficou fraca (37%)");
  });
  it("leitura boa sem nenhuma marca continua bloqueando (certeza de documento errado)", () => {
    expect(analisar(textoRG, CPF, ref, 92).veredito).toBe("tipo_errado");
  });
  it("leitura fraca não acusa divergência de dados", () => {
    const r = analisar(textoCPF.replace("123.456.789-09", "529.982.247-25"), CPF, ref, 40);
    expect(r.veredito).toBe("erro");
  });
  it("data com dia/mês de 1 dígito (RG antigo: 26/9/2004)", () => {
    const r = analisar("CARTEIRA DE IDENTIDADE REGISTRO GERAL NOME ANA BEATRIZ ROCHA NASCIMENTO 14/3/2004", RG, ref, 90);
    expect(r.veredito).toBe("ok");
    expect(r.campos.find((c) => c.k === "Data")).toEqual({ k: "Data", v: "14/03/2004", ok: true });
  });
  it("CPF correto é conferido", () => {
    const r = analisar(textoCPF, CPF, ref);
    expect(r.veredito).toBe("ok");
    expect(r.campos.find((c) => c.k === "Documento")?.ok).toBe(true);
    expect(r.campos.find((c) => c.k === "CPF")?.ok).toBe(true);
  });
  it("RG anexado no lugar do CPF não é reconhecido", () => {
    const r = analisar(textoRG, CPF, ref);
    expect(r.veredito).toBe("tipo_errado");
    expect(r.alertas[0]).toContain("não parece ser o CPF");
    expect(ACAO_POR_VEREDITO[r.veredito]).toBe("trocar");
  });
  it("CPF anexado no lugar da identidade não é reconhecido", () => {
    expect(analisar(textoCPF, RG, ref).veredito).toBe("tipo_errado");
  });
  it("conta de luz no lugar da declaração não é reconhecida", () => {
    const r = analisar(textoConta, DECL, ref);
    expect(r.veredito).toBe("tipo_errado");
    expect(r.alertas[0]).toContain("não parece ser a Declaração");
  });
  it("CPF certo com número diferente: divergente (outro arquivo ou conferência manual)", () => {
    const r = analisar(textoCPF.replace("123.456.789-09", "529.982.247-25"), CPF, ref);
    expect(r.veredito).toBe("divergente");
    expect(ACAO_POR_VEREDITO[r.veredito]).toBe("manual_ou_trocar");
  });
  it("declaração após 2022 é divergente", () => {
    const r = analisar("DECLARAMOS QUE ANA BEATRIZ ROCHA CONCLUIU O ENSINO MEDIO EM 2023", DECL, ref);
    expect(r.veredito).toBe("divergente");
  });
  it("histórico com nome e ano é conferido", () => {
    expect(analisar("HISTORICO ESCOLAR ENSINO MEDIO ALUNO ANA BEATRIZ ROCHA CONCLUSAO 2021", HIST, ref).veredito).toBe("ok");
  });
  it("comprovante com outro CEP pede atenção (anexa com aviso)", () => {
    const r = analisar(textoConta.replace("38440-000", "74215-025"), RESID, ref);
    expect(r.veredito).toBe("atencao");
    expect(ACAO_POR_VEREDITO[r.veredito]).toBe("anexar_com_aviso");
  });
  it("foto 3x4 não passa pela identificação de tipo", () => {
    expect(identificarTipo("qualquer coisa", FOTO.codigo).reconhecido).toBe(true);
  });
  it("marcas toleram acento, caixa e pontuação", () => {
    expect(identificarTipo("cadastro de pessoas físicas", "05").reconhecido).toBe(true);
    expect(identificarTipo("Título  Eleitoral", "06").reconhecido).toBe(true);
  });
});
