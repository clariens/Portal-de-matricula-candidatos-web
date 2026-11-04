import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { DocumentoStatus, Inscricao } from "../api/types";
import { Alert, Chip } from "../components/ui";
import { Visor, type Visto } from "../components/Visor";
import { miniatura } from "../lib/imagem";

const STATUS: Record<string, [string, string]> = {
  enviado: ["ok", "Enviado"],
  em_conferencia: ["warn", "Em conferência"],
  aprovado: ["ok", "Aprovado"],
  recusado: ["bad", "Recusado"],
  pendente: ["neutral", "Não enviado"],
};

interface Previa {
  url?: string;
  pdf?: boolean;
  thumb?: string;
  indisponivel?: boolean; // o Lyceum registrou o documento, mas não devolve o arquivo
}

/** Documentos de ingresso (botão "Documentos" do histórico): o que o Lyceum registrou, com a prévia do arquivo. */
export function DocumentosIngresso() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [insc, setInsc] = useState<Inscricao | null>(null);
  const [docs, setDocs] = useState<DocumentoStatus[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [previas, setPrevias] = useState<Record<string, Previa>>({});
  const previasRef = useRef(previas);
  previasRef.current = previas;
  const [vendo, setVendo] = useState<Visto | null>(null);

  useEffect(() => {
    Promise.all([api.inscricao(id), api.documentos(id)])
      .then(([i, d]) => {
        setInsc(i);
        setDocs(d);
      })
      .catch((e) => setErro(e instanceof ApiError ? e.message : "Não foi possível carregar os documentos."));
  }, [id]);

  // prévias do que o Lyceum guardou: 2 de cada vez, em segundo plano; liberadas da memória ao sair
  useEffect(() => {
    if (!docs) return;
    const fila = docs.filter((d) => d.status !== "pendente").map((d) => d.codigo);
    let ativo = true;
    const proximo = async (): Promise<void> => {
      const tipo = ativo ? fila.shift() : undefined;
      if (!tipo) return;
      try {
        const blob = await api.arquivoDocumento(id, tipo);
        const pdf = blob.type === "application/pdf";
        const thumb = pdf ? undefined : await miniatura(new File([blob], tipo, { type: blob.type })).catch(() => undefined);
        if (ativo) setPrevias((x) => ({ ...x, [tipo]: { url: URL.createObjectURL(blob), pdf, thumb } }));
      } catch {
        if (ativo) setPrevias((x) => ({ ...x, [tipo]: { indisponivel: true } }));
      }
      return proximo();
    };
    void Promise.all([proximo(), proximo()]);
    return () => {
      ativo = false;
    };
  }, [docs, id]);
  useEffect(() => () => Object.values(previasRef.current).forEach((p) => p.url && URL.revokeObjectURL(p.url)), []);

  return (
    <>
      <div className="page-head">
        <div>
          <span className="eyebrow">{insc ? `Inscrição #${insc.codCandidato}` : "Inscrição"}</span>
          <h1>Documentos de ingresso</h1>
        </div>
        {docs && <span className="muted">{docs.length} documento(s)</span>}
      </div>
      {erro && <Alert>{erro}</Alert>}
      {!erro && !docs && <div className="skel" style={{ minHeight: 240 }} />}
      {docs && (
        <section className="card panel">
          {insc && <p className="muted" style={{ marginTop: 0 }}>{insc.curso} · {insc.unidade}</p>}
          {docs.length === 0 && <p className="muted">Nenhum documento registrado no Lyceum ainda.</p>}
          <div className="docs">
            {docs.map((d) => {
              const p = previas[d.codigo];
              const [tom, rotulo] = STATUS[d.status ?? "pendente"] ?? STATUS.pendente;
              return (
                <div key={d.codigo} className="doc" data-doc={d.codigo}>
                  {p?.url ? (
                    <button type="button" className="thumb-btn" aria-label={`Ver ${d.nome}`} title="Ver documento"
                            onClick={() => setVendo({ nome: d.nome, url: p.url!, pdf: !!p.pdf, arquivo: `${d.nome}${p.pdf ? ".pdf" : ".jpg"}`, temporaria: false })}>
                      {p.thumb ? <img className="thumb" src={p.thumb} alt="" /> : <span className="thumb thumb-pdf">PDF</span>}
                    </button>
                  ) : (
                    <span className="code">{d.codigo}</span>
                  )}
                  <div style={{ minWidth: 0 }}>
                    <h4>{d.nome}</h4>
                    <div className="sub">
                      {d.obrigatorio ? <b style={{ color: "var(--bad)" }}>Obrigatório</b> : "Opcional"}
                      {d.enviadoEm ? ` · enviado em ${d.enviadoEm}` : ""}
                      {p?.indisponivel && <span className="previa-off"> · prévia indisponível</span>}
                    </div>
                  </div>
                  <div className="right">
                    <Chip tone={tom}>{rotulo}</Chip>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
      {vendo && <Visor visto={vendo} fechar={() => setVendo(null)} />}
      <div className="foot">
        <button className="btn btn-ghost" type="button" onClick={() => nav("/inscricoes")}>
          Voltar para minhas inscrições
        </button>
      </div>
    </>
  );
}
