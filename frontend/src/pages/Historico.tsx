import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Inscricao } from "../api/types";
import { useAuth } from "../components/auth";
import { Alert, Chip } from "../components/ui";

export const SITUACAO_TOM: Record<string, string> = {
  Convocado: "info",
  Confirmado: "ok",
  Cancelado: "neutral",
  "Pré-Matriculado": "warn",
  Matriculado: "ok",
  Inscrito: "neutral",
};

export function Historico() {
  const { pessoa } = useAuth();
  const nav = useNavigate();
  const [itens, setItens] = useState<Inscricao[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.inscricoes().then(setItens).catch((e) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar."));
  }, []);

  const primeiroNome = pessoa?.nome.split(" ")[0] ?? "";
  const conv = itens?.find((i) => i.acoes.includes("matricular") || i.acoes.includes("continuar_matricula"));

  return (
    <>
      <div className="page-head">
        <div>
          <span className="eyebrow">Olá, {primeiroNome}</span>
          <h1>Minhas inscrições</h1>
        </div>
        {itens && <span className="muted">{itens.length} inscrições</span>}
      </div>
      {erro && <Alert>{erro}</Alert>}
      {conv && (
        <div className="banner-call">
          <Chip tone="info">Ação pendente</Chip>
          <p>
            Você foi convocado(a) para <b>{conv.curso}</b> no {conv.unidade}. Faça sua matrícula para garantir a vaga.
          </p>
          <button className="btn btn-primary" onClick={() => nav(`/matricula/${conv.ref ?? ""}`)}>
            {conv.acoes.includes("continuar_matricula") ? "Continuar matrícula" : "Fazer matrícula"}
          </button>
        </div>
      )}
      <div className="hist" aria-busy={!itens}>
        {!itens && !erro && [0, 1, 2].map((k) => <div key={k} className="skel" />)}
        {itens?.map((i) => (
          <article key={i.codCandidato} className={`card ins ${i.situacao === "Convocado" ? "callout" : ""}`}>
            <div>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <Chip tone={SITUACAO_TOM[i.situacao]}>{i.situacao}</Chip>
                <span className="mono muted" style={{ fontSize: 12 }}>
                  #{i.codCandidato}
                </span>
              </div>
              <h3 style={{ marginTop: 8 }}>
                {i.curso} · {i.unidade}
              </h3>
              <p className="muted" style={{ fontSize: 14 }}>
                {i.processo}
              </p>
              <div className="meta">
                <span>
                  Inscrição <b>{i.dataInscricao}</b>
                </span>
                {i.formaPagamento && (
                  <span>
                    Pagamento <b>{i.formaPagamento}</b>
                    {i.statusPagamento ? ` · ${i.statusPagamento}` : ""}
                  </span>
                )}
                {i.vencimento && (
                  <span>
                    Vencimento <b>{i.vencimento}</b>
                  </span>
                )}
                {i.situacao === "Pré-Matriculado" && (
                  <span>
                    Contrato <b>{i.contratoAceito ? "assinado" : "aguardando assinatura"}</b>
                  </span>
                )}
              </div>
            </div>
            <div className="actions">
              {(i.acoes.includes("matricular") || i.acoes.includes("continuar_matricula")) && (
                <button className="btn btn-primary" onClick={() => nav(`/matricula/${i.ref ?? ""}`)}>
                  {i.acoes.includes("continuar_matricula") ? "Continuar matrícula" : "Fazer matrícula"}
                </button>
              )}
              {i.acoes.includes("contrato") && (
                <button className="btn btn-ghost" onClick={() => nav(`/matricula/${i.ref ?? ""}/conclusao`)}>
                  Ver contrato
                </button>
              )}
              {i.acoes.includes("documentos") && (
                <button className="btn btn-ghost" onClick={() => nav(`/matricula/${i.ref ?? ""}/documentos`)}>
                  Documentos
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
