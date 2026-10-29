import type {
  Cabecalho,
  Candidato,
  CandidatoUpdate,
  CepResultado,
  ConfirmacaoResultado,
  CupomResultado,
  DocumentoStatus,
  EnvioDocumentosResultado,
  Inscricao,
  Matricula,
  OpcoesPagamento,
  PagamentoIn,
  PagamentoResultado,
  Pessoa,
  Questionario,
  Uf,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public campos: Record<string, string> = {},
  ) {
    super(message);
  }
}

// ---- inspetor de chamadas (somente em desenvolvimento) ----
export interface ApiLog { t: string; method: string; path: string; status: number; ms: number; body?: unknown }
const logs: ApiLog[] = [];
const subs = new Set<() => void>();
export const apiLog = {
  list: () => logs,
  subscribe(fn: () => void) {
    subs.add(fn);
    return () => void subs.delete(fn);
  },
};
function pushLog(l: ApiLog) {
  if (!import.meta.env.DEV) return;
  logs.unshift(l);
  logs.length = Math.min(logs.length, 100);
  subs.forEach((f) => f());
}

let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (fn: () => void) => (onUnauthorized = fn);

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  const t0 = performance.now();
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method,
      credentials: "include",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "fetch",
        ...(body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}),
      },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Sem conexão com o servidor. Verifique sua internet e tente de novo.");
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  pushLog({
    t: new Date().toLocaleTimeString("pt-BR"),
    method,
    path,
    status: res.status,
    ms: Math.round(performance.now() - t0),
    body: isForm ? "[multipart]" : body,
  });
  if (!res.ok) {
    const erro = data?.erro;
    if (res.status === 401 && path !== "/auth/login") onUnauthorized?.();
    throw new ApiError(res.status, erro?.mensagem || "Não foi possível concluir a operação.", erro?.campos || {});
  }
  return data as T;
}

const ins = (id: string) => `/inscricoes/${encodeURIComponent(id)}`;

export const api = {
  login: (login: string, senha: string) => request<Pessoa>("POST", "/auth/login", { login, senha }),
  logout: () => request<null>("POST", "/auth/logout"),
  /** Esqueci minha senha: o Processo Seletivo envia as instruções ao e-mail cadastrado. */
  recuperarSenha: (login: string) => request<{ mensagem: string }>("POST", "/auth/recuperar-senha", { login }),
  /** Áreas de interesse e link de cadastro do Processo Seletivo (público). */
  cabecalho: () => request<Cabecalho>("GET", "/publico/cabecalho"),
  /** Quem está logado; null quando ninguém entrou (não é erro). */
  me: () => request<Pessoa | null>("GET", "/me"),
  /** Recursos ligados no ambiente: conferência de documentos pela IA (servidor) ou pelo navegador. */
  recursos: () => request<{ conferenciaDocumentos: "ia" | "navegador" }>("GET", "/recursos"),

  inscricoes: () => request<Inscricao[]>("GET", "/inscricoes"),
  inscricao: (id: string) => request<Inscricao>("GET", ins(id)),

  candidato: (id: string) => request<Candidato>("GET", `${ins(id)}/candidato`),
  salvarCandidato: (id: string, c: CandidatoUpdate) => request<Candidato>("PUT", `${ins(id)}/candidato`, c),

  ufs: () => request<Uf[]>("GET", "/enderecos/ufs"),
  cep: (cep: string) => request<CepResultado>("GET", `/enderecos/cep/${cep.replace(/\D/g, "")}`),

  documentos: (id: string) => request<DocumentoStatus[]>("GET", `${ins(id)}/documentos`),
  enviarDocumento: (id: string, tipo: string, arquivo: File, ocr?: unknown) => {
    const fd = new FormData();
    fd.append("arquivo", arquivo);
    if (ocr) fd.append("ocr", JSON.stringify(ocr));
    return request<DocumentoStatus>("POST", `${ins(id)}/documentos/${tipo}`, fd);
  },
  /** Envia ao Lyceum, de uma vez, os documentos guardados no navegador, cada um com o selo da conferência
   *  (no legado o primeiro envio finaliza a inscrição). */
  enviarDocumentos: (id: string, itens: { tipo: string; nome: string; arquivo: Blob; selo: string }[]) => {
    const fd = new FormData();
    for (const i of itens) {
      fd.append(`arquivo_${i.tipo}`, i.arquivo, i.nome);
      fd.append(`selo_${i.tipo}`, i.selo);
    }
    return request<EnvioDocumentosResultado>("POST", `${ins(id)}/envio-documentos`, fd);
  },

  opcoesPagamento: (id: string) => request<OpcoesPagamento>("GET", `${ins(id)}/pagamento/opcoes`),
  validarCupom: (id: string, codigo: string) => request<CupomResultado>("POST", `${ins(id)}/cupons/validar`, { codigo }),
  efetivarPagamento: (id: string, p: PagamentoIn) => request<PagamentoResultado>("POST", `${ins(id)}/pagamento`, p),

  matricula: (id: string) => request<Matricula>("GET", `${ins(id)}/matricula`),
  confirmarMatricula: (id: string) => request<ConfirmacaoResultado>("POST", `${ins(id)}/matricula/confirmar`),
  questionarios: () => request<Questionario[]>("GET", "/questionarios/pendentes"),
};
