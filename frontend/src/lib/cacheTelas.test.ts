import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  inscricao: vi.fn(),
  matricula: vi.fn(),
  documentos: vi.fn(),
  arquivoDocumento: vi.fn(),
  boleto: vi.fn(),
  pix: vi.fn(),
}));
vi.mock("../api/client", () => ({ api }));

import type { Inscricao } from "../api/types";
import { cacheTelas, preCarregar } from "./cacheTelas";

const insc = (acoes: Inscricao["acoes"], ref = "REF123"): Inscricao =>
  ({ codCandidato: "2027100000391", ref, acoes, situacao: "Pré-Matriculado" }) as Inscricao;

const esperar = () => new Promise((r) => setTimeout(r, 0));

describe("cacheTelas", () => {
  beforeEach(() => {
    cacheTelas.limpar();
    Object.values(api).forEach((f) => f.mockReset());
  });

  it("repete a mesma busca enquanto vale e busca de novo depois de limpar", async () => {
    api.matricula.mockResolvedValue({ matricula: "2716520012" });
    await cacheTelas.matricula("A");
    await cacheTelas.matricula("A");
    expect(api.matricula).toHaveBeenCalledTimes(1);
    cacheTelas.limpar(); // sair da conta
    await cacheTelas.matricula("A");
    expect(api.matricula).toHaveBeenCalledTimes(2);
  });

  it("não guarda erro: a tela tenta de novo", async () => {
    api.documentos.mockRejectedValueOnce(new Error("fora do ar")).mockResolvedValueOnce([]);
    await expect(cacheTelas.documentos("A")).rejects.toThrow();
    await expect(cacheTelas.documentos("A")).resolves.toEqual([]);
    expect(api.documentos).toHaveBeenCalledTimes(2);
  });

  it("pré-carrega contrato, documentos e prévias, mas nunca boleto nem PIX (geram cobrança)", async () => {
    api.matricula.mockResolvedValue({});
    api.documentos.mockResolvedValue([
      { codigo: "05", status: "enviado" },
      { codigo: "04", status: "enviado" },
      { codigo: "14", status: "pendente" },
    ]);
    api.arquivoDocumento.mockResolvedValue(new Blob(["x"]));
    preCarregar([insc(["boleto", "pix", "contrato", "documentos"])]);
    await esperar();
    await esperar();
    expect(api.matricula).toHaveBeenCalledWith("REF123");
    expect(api.documentos).toHaveBeenCalledWith("REF123");
    expect(api.arquivoDocumento.mock.calls.map((c) => c[1])).toEqual(["05", "04"]); // só o que foi enviado
    expect(api.boleto).not.toHaveBeenCalled();
    expect(api.pix).not.toHaveBeenCalled();
    // a inscrição vem do próprio histórico: a tela não precisa pedir de novo
    await cacheTelas.inscricao("REF123");
    expect(api.inscricao).not.toHaveBeenCalled();
  });

  it("sem os botões, não busca nada", async () => {
    preCarregar([insc(["matricular"])]);
    await esperar();
    expect(api.matricula).not.toHaveBeenCalled();
    expect(api.documentos).not.toHaveBeenCalled();
  });
});
