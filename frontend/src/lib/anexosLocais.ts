/**
 * Anexos guardados no navegador até o envio final (o servidor não guarda nada entre requisições).
 *
 * Cada documento conferido fica no IndexedDB com o arquivo e o selo que o servidor devolveu na conferência;
 * no "Enviar documentos" os dois voltam ao servidor, que confere o selo antes de mandar ao Lyceum.
 * Sobrevive a recarregar a página. É apagado ao enviar, ao remover, ao sair e depois de 24 h (validade do selo).
 * Sem IndexedDB (navegação privada em alguns navegadores), fica só na memória da aba.
 */
import type { OcrResultado } from "../api/types";

export interface AnexoLocal {
  cand: string;
  tipo: string;
  nome: string;
  arquivo: Blob;
  selo: string;
  analise?: OcrResultado | null;
  convertidoDe?: string;
  salvoEm: number;
}

const BANCO = "portal-matricula";
const LOJA = "anexos";
const VALIDADE_MS = 24 * 3600 * 1000;
const memoria = new Map<string, AnexoLocal>();
const chave = (cand: string, tipo: string) => `${cand}:${tipo}`;

let banco: Promise<IDBDatabase | null> | null = null;
function abrir(): Promise<IDBDatabase | null> {
  if (banco) return banco;
  banco = new Promise((resolve) => {
    try {
      if (typeof indexedDB === "undefined") return resolve(null);
      const req = indexedDB.open(BANCO, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(LOJA);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
      req.onblocked = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
  return banco;
}

async function operar<T>(modo: IDBTransactionMode, f: (loja: IDBObjectStore) => IDBRequest<T>): Promise<T | undefined> {
  const db = await abrir();
  if (!db) return undefined;
  return new Promise((resolve) => {
    try {
      const req = f(db.transaction(LOJA, modo).objectStore(LOJA));
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(undefined);
    } catch {
      resolve(undefined);
    }
  });
}

export async function guardarAnexo(a: Omit<AnexoLocal, "salvoEm">): Promise<void> {
  const reg: AnexoLocal = { ...a, salvoEm: Date.now() };
  memoria.set(chave(a.cand, a.tipo), reg);
  await operar("readwrite", (l) => l.put(reg, chave(a.cand, a.tipo)));
}

export async function removerAnexo(cand: string, tipo: string): Promise<void> {
  memoria.delete(chave(cand, tipo));
  await operar("readwrite", (l) => l.delete(chave(cand, tipo)));
}

/** Anexos ainda válidos desta inscrição (os vencidos são apagados). */
export async function listarAnexos(cand: string): Promise<AnexoLocal[]> {
  const todos = ((await operar("readonly", (l) => l.getAll() as IDBRequest<AnexoLocal[]>)) ?? [...memoria.values()]);
  const agora = Date.now();
  const validos: AnexoLocal[] = [];
  for (const a of todos) {
    if (agora - a.salvoEm > VALIDADE_MS) await removerAnexo(a.cand, a.tipo);
    else if (a.cand === cand) validos.push(a);
  }
  return validos;
}

/** Apaga todos os anexos guardados (ao sair: documentos pessoais não ficam no computador). */
export async function limparAnexos(): Promise<void> {
  memoria.clear();
  await operar("readwrite", (l) => l.clear());
}
