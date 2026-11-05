import { afterEach, describe, expect, it, vi } from "vitest";
import { definirDono, guardarAnexo, limparAnexos, listarAnexos } from "./anexosLocais";

// Sem IndexedDB (ambiente de teste), os anexos ficam na memória da aba: as mesmas regras valem.
const anexo = (tipo: string) => ({ cand: "2027100000162", tipo, nome: `${tipo}.png`, arquivo: new Blob(["x"]), selo: "s" });

describe("anexos guardados no navegador", () => {
  afterEach(async () => {
    vi.useRealTimers();
    await limparAnexos();
  });

  it("quando entra outra pessoa, os documentos da anterior são apagados", async () => {
    await definirDono("111");
    await guardarAnexo(anexo("05"));
    await definirDono("111"); // a mesma pessoa voltando: continuam
    expect(await listarAnexos("2027100000162")).toHaveLength(1);
    await definirDono("222");
    expect(await listarAnexos("2027100000162")).toHaveLength(0);
  });

  it("abrir o portal sem sessão apaga tudo", async () => {
    await definirDono("111");
    await guardarAnexo(anexo("04"));
    await definirDono(null);
    await definirDono("111");
    expect(await listarAnexos("2027100000162")).toHaveLength(0);
  });

  it("vencidos (24 h) saem ao abrir o portal, mesmo sem passar pela etapa de documentos", async () => {
    vi.useFakeTimers();
    await definirDono("111");
    await guardarAnexo(anexo("03"));
    vi.setSystemTime(Date.now() + 25 * 3600 * 1000);
    await definirDono("111");
    vi.useRealTimers();
    expect(await listarAnexos("2027100000162")).toHaveLength(0);
  });
});
