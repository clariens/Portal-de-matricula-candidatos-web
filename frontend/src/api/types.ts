// Tipos derivados do contrato OpenAPI do BFF (src/api/schema.d.ts é gerado por `npm run gen:api`).
import type { components } from "./schema";

type S = components["schemas"];
export type Pessoa = S["Pessoa"];
export type Inscricao = S["Inscricao"];
export type Etapa = NonNullable<Inscricao["etapaAtual"]>;
export type Candidato = S["Candidato"];
export type CandidatoUpdate = S["CandidatoUpdate"];
export type Endereco = S["Endereco"];
export type Uf = S["Uf"];
export type CepResultado = S["CepResultado"];
export type DocumentoStatus = S["DocumentoStatus"];
export type EnvioDocumentosResultado = S["EnvioDocumentosResultado"];
export type OpcoesPagamento = S["OpcoesPagamento"];
export type Plano = S["Plano"];
export type CupomResultado = S["CupomResultado"];
export type PagamentoIn = S["PagamentoIn"];
export type PagamentoResultado = S["PagamentoResultado"];
export type Responsavel = S["Responsavel"];
export type Matricula = S["Matricula"];
export type ConfirmacaoResultado = S["ConfirmacaoResultado"];
export type Questionario = S["Questionario"];
