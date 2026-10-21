import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import type { Candidato, Etapa, Inscricao } from "../../api/types";
import { Alert, Hexa, ICON_ESTETOSCOPIO, Spin, useToast } from "../../components/ui";
import { EtapaConclusao } from "./EtapaConclusao";
import { EtapaDados } from "./EtapaDados";
import { EtapaDocumentos } from "./EtapaDocumentos";
import { EtapaPagamento } from "./EtapaPagamento";

export const ETAPAS: { id: Etapa; nome: string; sub: string; titulo: string }[] = [
  { id: "dados", nome: "Dados", sub: "Confira e atualize", titulo: "Seus dados" },
  { id: "documentos", nome: "Documentos", sub: "Leitura automática", titulo: "Seus documentos" },
  { id: "pagamento", nome: "Pagamento", sub: "Plano e responsável", titulo: "Pagamento" },
  { id: "conclusao", nome: "Conclusão", sub: "Contrato e disciplinas", titulo: "Matrícula concluída" },
];
const idx = (e: Etapa) => ETAPAS.findIndex((x) => x.id === e);

interface WizardCtx {
  insc: Inscricao;
  candidato: Candidato;
  setCandidato: (c: Candidato) => void;
  recarregar: () => Promise<void>;
  ir: (e: Etapa) => void;
  somenteLeitura: boolean;
}
const Ctx = createContext<WizardCtx>(null!);
export const useWizard = () => useContext(Ctx);

/** Etapas que a inscrição permite abrir. Pré-matriculado: só documentos (consulta) e conclusão. */
function etapasPermitidas(i: Inscricao): Etapa[] {
  if (i.situacao === "Pré-Matriculado" || i.situacao === "Matriculado") return ["documentos", "conclusao"];
  if (i.situacao !== "Convocado") return [];
  const ate = idx(i.etapaAtual ?? "dados");
  return ETAPAS.slice(0, Math.min(ate, 2) + 1).map((e) => e.id);
}

export function Wizard() {
  const { id = "", etapa } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [insc, setInsc] = useState<Inscricao | null>(null);
  const [candidato, setCandidato] = useState<Candidato | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const recarregar = useCallback(async () => {
    try {
      const [i, c] = await Promise.all([api.inscricao(id), api.candidato(id)]);
      setInsc(i);
      setCandidato(c);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Erro ao carregar a matrícula.");
    }
  }, [id]);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  if (erro)
    return (
      <div className="center">
        <Alert>{erro}</Alert>
        <button className="btn btn-ghost" onClick={() => nav("/inscricoes")}>
          Voltar para minhas inscrições
        </button>
      </div>
    );
  if (!insc || !candidato)
    return (
      <div className="center">
        <Spin />
        <span className="muted">Abrindo sua matrícula…</span>
      </div>
    );

  const permitidas = etapasPermitidas(insc);
  if (!permitidas.length) return <Navigate to="/inscricoes" replace />;
  const atual = ETAPAS.find((e) => e.id === etapa)?.id;
  if (!atual || !permitidas.includes(atual)) return <Navigate to={`/matricula/${id}/${permitidas[permitidas.length - 1]}`} replace />;

  const somenteLeitura = insc.situacao !== "Convocado";
  const n = idx(atual);
  const ir = (e: Etapa) => nav(`/matricula/${id}/${e}`);
  const EtapaView = { dados: EtapaDados, documentos: EtapaDocumentos, pagamento: EtapaPagamento, conclusao: EtapaConclusao }[atual];

  return (
    <Ctx.Provider value={{ insc, candidato, setCandidato, recarregar, ir, somenteLeitura }}>
      <div className="page-head">
        <div>
          <span className="eyebrow">Matrícula · Inscrição #{insc.codCandidato}</span>
          <h1>{ETAPAS[n].titulo}</h1>
        </div>
        {!somenteLeitura && atual !== "conclusao" && (
          <button
            className="btn btn-ghost"
            onClick={() => {
              toast("Progresso salvo. Você pode continuar quando quiser.");
              nav("/inscricoes");
            }}
          >
            Continuar depois
          </button>
        )}
      </div>
      <div className="wiz">
        <aside className="rail">
          <ol className="card steps" aria-label="Etapas da matrícula">
            {ETAPAS.map((e, i) => {
              const ok = permitidas.includes(e.id);
              const done = i < idx(insc.etapaAtual ?? "dados");
              const cls = e.id === atual ? "active" : done ? "done" : ok ? "" : "locked";
              const conteudo = (
                <>
                  <span className="n">{done && e.id !== atual ? "✓" : i + 1}</span>
                  <span>
                    {e.nome}
                    <small>{e.sub}</small>
                  </span>
                </>
              );
              return (
                <li key={e.id} className={cls} aria-current={e.id === atual ? "step" : undefined}>
                  {ok && e.id !== atual ? (
                    <button type="button" onClick={() => ir(e.id)}>
                      {conteudo}
                    </button>
                  ) : (
                    conteudo
                  )}
                </li>
              );
            })}
          </ol>
          <div className="card sum">
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <Hexa path={ICON_ESTETOSCOPIO} size={34} />
              <span className="eyebrow">Sua vaga em {insc.curso}</span>
            </div>
            <dl>
              <dt>Curso</dt>
              <dd>{insc.curso}</dd>
              <dt>Unidade</dt>
              <dd>{insc.unidade}</dd>
              <dt>Processo</dt>
              <dd>{insc.processo}</dd>
              <dt>Concurso</dt>
              <dd className="mono">{insc.codConcurso}</dd>
            </dl>
          </div>
        </aside>
        <div>
          <EtapaView key={atual} />
        </div>
      </div>
    </Ctx.Provider>
  );
}
