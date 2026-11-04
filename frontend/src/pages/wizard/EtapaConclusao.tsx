import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import type { Matricula, PagamentoResultado, Questionario } from "../../api/types";
import { Alert, Chip, Spin } from "../../components/ui";
import { COBRANCA_KEY } from "./EtapaPagamento";
import { PrimeiraParcela } from "./PrimeiraParcela";
import { useWizard } from "./Wizard";

const CONTRATO: Record<string, [string, string]> = {
  nao_enviado: ["neutral", "Contrato em preparação"],
  aguardando_assinatura: ["warn", "Aguardando assinatura"],
  assinado: ["ok", "Contrato assinado"],
};

function lerCobranca(id: string): PagamentoResultado["cobranca"] | null {
  try {
    const raw = sessionStorage.getItem(COBRANCA_KEY(id));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function EtapaConclusao() {
  const { insc, ref, candidato } = useWizard();
  const nav = useNavigate();
  const [m, setM] = useState<Matricula | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [questionarios, setQuestionarios] = useState<Questionario[] | null>(null);
  const cobranca = lerCobranca(insc.codCandidato);

  useEffect(() => {
    api.matricula(ref).then(setM).catch((e) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar a matrícula."));
  }, [insc.codCandidato]);

  async function concluir() {
    setEnviando(true);
    try {
      const r = await api.confirmarMatricula(ref);
      if (r.questionariosPendentes?.length) setQuestionarios(r.questionariosPendentes);
      else nav("/inscricoes");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível concluir.");
    } finally {
      setEnviando(false);
    }
  }

  if (erro && !m)
    // os dados da matrícula ainda não vêm do Lyceum real, mas o pagamento da 1ª parcela já pode ser gerado
    return (
      <>
        <Alert tone="info">
          Pagamento confirmado. Os detalhes da matrícula (contrato e disciplinas) ainda não aparecem neste portal.
        </Alert>
        <PrimeiraParcela inscRef={ref} cobranca={cobranca} insc={insc} />
        <div className="foot">
          <button className="btn btn-ghost" type="button" onClick={() => nav(`/matricula/${ref}/documentos`)}>
            Ver documentos
          </button>
          <button className="btn btn-primary" type="button" onClick={() => nav("/inscricoes")}>
            Ir para minhas inscrições
          </button>
        </div>
      </>
    );
  if (erro) return <Alert>{erro}</Alert>;
  if (!m) return <div className="skel" style={{ minHeight: 320 }} />;
  const [tom, rotulo] = CONTRATO[m.contrato.status];

  return (
    <>
      <div className="done-hero">
        <div>
          <span className="eyebrow" style={{ color: "var(--on-deep-muted)" }}>
            Pré-matrícula confirmada{m.periodo ? ` · Turma ${m.periodo}` : ""}
          </span>
          <h2>
            Bem-vindo(a) à {insc.curso}, {candidato.nomeCompleto.split(" ")[0]}.
          </h2>
          <p style={{ marginTop: 6 }}>
            {m.contrato.status === "assinado" ? "Tudo certo! Sua matrícula está completa." : "Falta só assinar o contrato para concluir."}
          </p>
        </div>
        <div className="mat">
          Matrícula<b>{m.matricula}</b>
          {m.formaPagamento}
          {m.numParcelas ? ` · ${m.numParcelas} mensalidades` : ""}
        </div>
      </div>

      <PrimeiraParcela inscRef={ref} cobranca={cobranca} insc={insc} />

      <section className="card panel" style={{ marginTop: 16 }}>
        <div className="panel-head">
          <h2>Assine o contrato</h2>
          <Chip tone={tom}>{rotulo}</Chip>
        </div>
        {m.contrato.instrucoes?.length ? (
          <InstrucoesContrato linhas={m.contrato.instrucoes} />
        ) : (
        <ol className="timeline">
          <li>
            <div>
              <b>Abra a mensagem da Clicksign no WhatsApp</b>
              <p className="muted">Enviada para {m.contrato.destinatario ?? "o celular do responsável financeiro"}.</p>
            </div>
          </li>
          <li>
            <div>
              <b>Confirme CPF e data de nascimento</b>
              <p className="muted">São os dados do responsável financeiro.</p>
            </div>
          </li>
          <li>
            <div>
              <b>Digite o token recebido</b>
              <p className="muted">Uma cópia assinada chega no seu e-mail.</p>
            </div>
          </li>
        </ol>
        )}
      </section>

      {m.disciplinas.length > 0 && (
      <section className="card panel">
        <div className="panel-head">
          <h2>Disciplinas do 1º período</h2>
          <span className="muted">{m.disciplinas.length} disciplinas</span>
        </div>
        <ul className="disc">
          {m.disciplinas.map((d) => (
            <li key={d.codigo}>
              <code>{d.codigo}</code>
              <span>{d.nome}</span>
            </li>
          ))}
        </ul>
      </section>
      )}

      {questionarios && (
        <section className="card panel">
          <h2>Questionário pendente</h2>
          <p className="muted">Antes de seguir, responda:</p>
          <ul>
            {questionarios.map((q) => (
              <li key={q.codigo}>
                {q.url ? (
                  <a href={q.url} target="_blank" rel="noreferrer">
                    {q.titulo}
                  </a>
                ) : (
                  q.titulo
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="foot">
        <button className="btn btn-ghost" type="button" onClick={() => nav(`/matricula/${ref}/documentos`)}>
          Ver documentos
        </button>
        {questionarios ? (
          <button className="btn btn-primary" type="button" onClick={() => nav("/inscricoes")}>
            Ir para minhas inscrições
          </button>
        ) : (
          <button className="btn btn-primary" type="button" onClick={concluir} disabled={enviando}>
            {enviando ? <><Spin /> Concluindo</> : "Concluir e ir para minhas inscrições"}
          </button>
        )}
      </div>
    </>
  );
}

/** Instruções de assinatura do Processo Seletivo (/r/contrato): "1º Passo:" vira um passo da linha do tempo. */
function InstrucoesContrato({ linhas }: { linhas: string[] }) {
  const intro: string[] = [];
  const passos: { titulo: string; texto: string[] }[] = [];
  const fim: string[] = [];
  for (const l of linhas) {
    if (/^\d+\s*º?\s*passo\s*:?$/i.test(l)) passos.push({ titulo: l.replace(/:$/, ""), texto: [] });
    else if (!passos.length) intro.push(l);
    else if (passos[passos.length - 1].texto.length === 0) passos[passos.length - 1].texto.push(l);
    else fim.push(l);
  }
  return (
    <div className="contrato-instrucoes">
      {intro.map((l) => <p key={l}>{l}</p>)}
      {passos.length > 0 && (
        <ol className="timeline">
          {passos.map((s) => (
            <li key={s.titulo}>
              <div>
                <b>{s.titulo}</b>
                {s.texto.map((l) => <p key={l} className="muted">{l}</p>)}
              </div>
            </li>
          ))}
        </ol>
      )}
      {fim.map((l) => <p key={l} className="muted">{l}</p>)}
    </div>
  );
}
