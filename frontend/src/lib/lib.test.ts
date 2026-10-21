import { describe, expect, it } from "vitest";
import { cnpjValido, cpfValido, dataValida, maskCEP, maskCNPJ, maskCPF, maskDate, maskPhone } from "./format";
import { analisar } from "./ocr/analisar";

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

describe("analisar (OCR)", () => {
  it("ilegível com pouco texto", () => {
    expect(analisar("abc", "cpf", ref).veredito).toBe("ilegivel");
  });
  it("CPF confere", () => {
    const r = analisar("CADASTRO DE PESSOA FISICA NOME ANA BEATRIZ ROCHA CPF 123.456.789-09 NASC 14/03/2004", "cpf", ref);
    expect(r.veredito).toBe("ok");
    expect(r.campos.find((c) => c.k === "CPF")?.ok).toBe(true);
  });
  it("CPF divergente", () => {
    const r = analisar("CADASTRO DE PESSOA FISICA NOME ANA BEATRIZ ROCHA CPF 529.982.247-25", "cpf", ref);
    expect(r.veredito).toBe("divergente");
  });
  it("declaração após 2022 é divergente", () => {
    const r = analisar("DECLARAMOS QUE ANA BEATRIZ ROCHA CONCLUIU O ENSINO MEDIO EM 2023", "declaracao", ref);
    expect(r.veredito).toBe("divergente");
  });
  it("comprovante sem o CEP pede atenção", () => {
    const r = analisar("CONTA DE ENERGIA ANA BEATRIZ ROCHA RUA X 100 CEP 74215-025", "residencia", ref);
    expect(r.veredito).toBe("atencao");
  });
});
