import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import type { Inscricao, Matricula } from "../api/types";
import { AssinaturaContrato } from "../components/AssinaturaContrato";
import { Alert } from "../components/ui";
import { cacheTelas } from "../lib/cacheTelas";

/** Contrato da inscrição depois do pagamento (botão "Contrato" do histórico): matrícula e como assinar. */
export function ContratoInscricao() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [insc, setInsc] = useState<Inscricao | null>(null);
  const [m, setM] = useState<Matricula | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([cacheTelas.inscricao(id), cacheTelas.matricula(id)])
      .then(([i, mat]) => {
        setInsc(i);
        setM(mat);
      })
      .catch((e) => setErro(e instanceof ApiError ? e.message : "Não foi possível abrir o contrato."));
  }, [id]);

  const voltar = (
    <div className="foot">
      <button className="btn btn-ghost" type="button" onClick={() => nav("/inscricoes")}>
        Voltar para minhas inscrições
      </button>
    </div>
  );

  return (
    <>
      <div className="page-head">
        <div>
          <span className="eyebrow">{insc ? `Inscrição #${insc.codCandidato}` : "Inscrição"}</span>
          <h1>Contrato</h1>
        </div>
      </div>
      {erro && <Alert>{erro}</Alert>}
      {!erro && (!insc || !m) && <div className="skel" style={{ minHeight: 240 }} />}
      {insc && m && (
        <>
          <section className="card panel">
            <div className="resumo-inscricao">
              <h2>{insc.curso} · {insc.unidade}</h2>
              <p className="muted">{insc.processo}</p>
              <dl>
                <div><dt>Matrícula</dt><dd className="mono">{m.matricula}</dd></div>
                {m.periodo && <div><dt>Turma</dt><dd>{m.periodo}</dd></div>}
                {insc.formaPagamento && (
                  <div><dt>Pagamento</dt><dd>{insc.formaPagamento}{insc.statusPagamento ? ` · ${insc.statusPagamento}` : ""}</dd></div>
                )}
                {insc.vencimento && <div><dt>Vencimento</dt><dd>{insc.vencimento}</dd></div>}
              </dl>
            </div>
          </section>
          <AssinaturaContrato contrato={m.contrato} />
        </>
      )}
      {voltar}
    </>
  );
}
