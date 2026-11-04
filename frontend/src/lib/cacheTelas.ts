/**
 * Cache em memória (só nesta aba) para as telas de Contrato e Documentos de ingresso abrirem na hora.
 *
 * Quando o histórico carrega, `preCarregar` busca em segundo plano o contrato, a lista de documentos e as prévias
 * das inscrições que têm esses botões. Só leitura: boleto e PIX NÃO entram aqui, porque cada geração registra uma
 * cobrança no banco. Vale por 5 minutos e é apagado ao sair (documentos pessoais não ficam na memória da aba).
 */
import { api } from "../api/client";
import type { DocumentoStatus, Inscricao, Matricula } from "../api/types";

const VALIDADE_MS = 5 * 60_000;
const itens = new Map<string, { em: number; p: Promise<unknown> }>();

function memo<T>(chave: string, carregar: () => Promise<T>): Promise<T> {
  const x = itens.get(chave);
  if (x && Date.now() - x.em < VALIDADE_MS) return x.p as Promise<T>;
  const p = carregar();
  itens.set(chave, { em: Date.now(), p });
  p.catch(() => {
    if (itens.get(chave)?.p === p) itens.delete(chave); // erro não fica guardado: a tela tenta de novo
  });
  return p;
}

export const cacheTelas = {
  inscricao: (ref: string) => memo<Inscricao>(`inscricao:${ref}`, () => api.inscricao(ref)),
  matricula: (ref: string) => memo<Matricula>(`matricula:${ref}`, () => api.matricula(ref)),
  documentos: (ref: string) => memo<DocumentoStatus[]>(`documentos:${ref}`, () => api.documentos(ref)),
  arquivo: (ref: string, tipo: string) => memo<Blob>(`arquivo:${ref}:${tipo}`, () => api.arquivoDocumento(ref, tipo)),
  limpar: () => itens.clear(),
};

/** Adianta, sem bloquear a tela, o que as telas de Contrato e Documentos vão pedir. Erros ficam para a tela. */
export function preCarregar(inscricoes: Inscricao[]) {
  const ignorar = () => {};
  for (const i of inscricoes) {
    if (!i.ref) continue;
    const ref = i.ref;
    itens.set(`inscricao:${ref}`, { em: Date.now(), p: Promise.resolve(i) }); // o histórico já trouxe a inscrição
    if (i.acoes.includes("contrato")) cacheTelas.matricula(ref).catch(ignorar);
    if (i.acoes.includes("documentos")) {
      cacheTelas.documentos(ref).then(async (docs) => {
        // prévias uma de cada vez, para não disputar a rede com o que a pessoa estiver fazendo
        for (const d of docs.filter((x) => x.status !== "pendente" && x.status !== "anexado")) {
          await cacheTelas.arquivo(ref, d.codigo).catch(ignorar);
        }
      }).catch(ignorar);
    }
  }
}
