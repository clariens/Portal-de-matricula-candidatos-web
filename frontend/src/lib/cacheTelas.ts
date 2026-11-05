/**
 * Cache em memória (só nesta aba) para as telas abrirem na hora: Minhas inscrições, Meus dados, Contrato e
 * Documentos de ingresso.
 *
 * Quando o histórico carrega, `preCarregar` busca em segundo plano Meus dados, o contrato, a lista de documentos e
 * as prévias das inscrições que têm esses botões. Só leitura: boleto e PIX NÃO entram aqui, porque cada geração
 * registra uma cobrança no banco. Cada item vale por 5 minutos (o Lyceum pode mudar por fora, ex.: pagamento
 * compensado), sai do cache quando o portal grava algo que pode mudá-lo (`invalidarApos`) e tudo é apagado ao sair
 * (documentos pessoais não ficam na memória da aba).
 */
import { api } from "../api/client";
import type { DocumentoStatus, Inscricao, Matricula, MeusDados } from "../api/types";

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

const guardar = (chave: string, valor: unknown) => itens.set(chave, { em: Date.now(), p: Promise.resolve(valor) });

export const cacheTelas = {
  inscricoes: () => memo<Inscricao[]>("inscricoes", () => api.inscricoes()),
  meusDados: () => memo<MeusDados>("meus-dados", () => api.meusDados()),
  /** Depois de salvar, o que o servidor devolveu já é o dado novo: não precisa buscar de novo. */
  guardarMeusDados: (d: MeusDados) => guardar("meus-dados", d),
  inscricao: (ref: string) => memo<Inscricao>(`inscricao:${ref}`, () => api.inscricao(ref)),
  matricula: (ref: string) => memo<Matricula>(`matricula:${ref}`, () => api.matricula(ref)),
  documentos: (ref: string) => memo<DocumentoStatus[]>(`documentos:${ref}`, () => api.documentos(ref)),
  arquivo: (ref: string, tipo: string) => memo<Blob>(`arquivo:${ref}:${tipo}`, () => api.arquivoDocumento(ref, tipo)),
  limpar: () => itens.clear(),
};

/** Tira do cache o que uma gravação em `path` pode ter mudado. */
export function invalidarApos(path: string) {
  if (path.startsWith("/meus-dados")) {
    if (path === "/meus-dados") itens.delete("meus-dados"); // trocar a senha não muda os dados
    return;
  }
  const ref = /^\/inscricoes\/([^/?]+)/.exec(path)?.[1];
  if (!ref) return; // login, logout e recuperar senha: o login e o sair já limpam tudo
  // matrícula muda situação, etapa e pagamento da lista; "Seus dados" grava contato e endereço da pessoa
  itens.delete("inscricoes");
  itens.delete("meus-dados");
  const r = decodeURIComponent(ref);
  for (const k of [...itens.keys()]) if (k.split(":")[1] === r) itens.delete(k);
}

/** Adianta, sem bloquear a tela, o que as outras telas vão pedir. Erros ficam para a tela. */
export function preCarregar(inscricoes: Inscricao[]) {
  const ignorar = () => {};
  cacheTelas.meusDados().catch(ignorar);
  for (const i of inscricoes) {
    if (!i.ref) continue;
    const ref = i.ref;
    guardar(`inscricao:${ref}`, i); // o histórico já trouxe a inscrição
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
