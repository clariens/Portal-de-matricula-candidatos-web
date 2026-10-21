import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "../../api/client";
import type { DocumentoStatus } from "../../api/types";
import { Alert, Chip, Spin, useToast } from "../../components/ui";
import { norm } from "../../lib/format";
import { analisar, type OcrAnalise, type Regra } from "../../lib/ocr/analisar";
import { useWizard } from "./Wizard";

const MAX_MB = 10;

interface Local {
  nome: string;
  arquivo: File;
  thumb?: string;
  fase: "lendo" | "revisar" | "enviando";
  etapa: string;
  progresso: number;
  analise?: OcrAnalise;
  erro?: string;
}

const STATUS_SERVIDOR: Record<string, [string, string]> = {
  pendente: ["neutral", "Pendente"],
  anexado: ["info", "Pronto para envio"],
  enviado: ["ok", "Enviado"],
  em_conferencia: ["warn", "Em conferência"],
  aprovado: ["ok", "Aprovado"],
  recusado: ["bad", "Recusado"],
};
const VEREDITO: Record<string, [string, string]> = {
  ok: ["ok", "Conferido"],
  atencao: ["warn", "Verificar"],
  divergente: ["bad", "Divergente"],
  ilegivel: ["bad", "Ilegível"],
  erro: ["warn", "Conferência manual"],
};

export function EtapaDocumentos() {
  const { insc, candidato, recarregar, ir, somenteLeitura } = useWizard();
  const toast = useToast();
  const [docs, setDocs] = useState<DocumentoStatus[] | null>(null);
  const [local, setLocal] = useState<Record<string, Local>>({});
  const [filtro, setFiltro] = useState<"todos" | "obrig" | "pend">("todos");
  const [erro, setErro] = useState<string | null>(null);
  const [drag, setDrag] = useState<string | null>(null);
  const [avancando, setAvancando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const localRef = useRef(local);
  localRef.current = local;

  useEffect(() => {
    api.documentos(insc.codCandidato).then(setDocs).catch((e) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar documentos."));
  }, [insc.codCandidato]);

  const patch = (tipo: string, p: Partial<Local>) =>
    setLocal((s) => (s[tipo] ? { ...s, [tipo]: { ...s[tipo], ...p } } : s));
  const ref = {
    nomeCompleto: candidato.nomeCompleto, cpf: candidato.cpf, dataNascimento: candidato.dataNascimento,
    cep: candidato.endereco.cep,
  };

  async function enviar(tipo: string) {
    const l = localRef.current[tipo];
    if (!l) return;
    patch(tipo, { fase: "enviando", erro: undefined });
    try {
      const a = l.analise;
      // O texto bruto do OCR não é enviado: só veredito, confiança, campos e alertas.
      const ocr = a ? { veredito: a.veredito, confianca: a.confianca ?? null, campos: a.campos, alertas: a.alertas } : undefined;
      const st = await api.enviarDocumento(insc.codCandidato, tipo, l.arquivo, ocr);
      setDocs((d) => d?.map((x) => (x.codigo === tipo ? st : x)) ?? d);
      setLocal((s) => {
        const { [tipo]: _, ...rest } = s;
        return rest;
      });
      toast(st.observacao ? "Documento anexado. Ele irá para conferência manual." : "Documento anexado. Ele será enviado quando você continuar.");
    } catch (e) {
      patch(tipo, { fase: "revisar", erro: e instanceof ApiError ? e.message : "Falha no envio. Tente novamente." });
    }
  }

  async function processar(d: DocumentoStatus, file: File) {
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!(d.extensoes ?? []).includes(ext)) return toast(`Formato não aceito. Envie: ${(d.extensoes ?? []).join(", ").toUpperCase()}.`);
    if (file.size > MAX_MB * 1024 * 1024) return toast(`Arquivo acima de ${MAX_MB} MB. Reduza o tamanho e tente de novo.`);
    const tipo = d.codigo;
    setLocal((s) => ({ ...s, [tipo]: { nome: file.name, arquivo: file, fase: "lendo", etapa: "Preparando arquivo", progresso: 0 } }));
    let analise: OcrAnalise;
    try {
      const { fileToCanvas, reconhecer } = await import("../../lib/ocr/engine");
      const cv = await fileToCanvas(file);
      patch(tipo, { thumb: cv.toDataURL("image/jpeg", 0.5) });
      if (d.regra === "foto") {
        analise = { veredito: "ok", campos: [], alertas: [], texto: "" };
      } else {
        const r = await reconhecer(cv, (p) => patch(tipo, { etapa: p.etapa, progresso: p.progresso }));
        analise = { ...analisar(r.texto, (d.regra ?? "nome") as Regra, ref), confianca: r.confianca };
      }
    } catch (e) {
      console.error(e);
      analise = {
        veredito: "erro", campos: [], texto: "",
        alertas: ["Não foi possível ler este arquivo no navegador. Ele será enviado para conferência manual."],
      };
    }
    patch(tipo, { analise, fase: "revisar" });
    // Documento conferido segue direto; divergente/ilegível pede confirmação antes do envio.
    if (analise.veredito === "ok") {
      localRef.current = { ...localRef.current, [tipo]: { ...localRef.current[tipo], analise } };
      await enviar(tipo);
    }
  }

  async function amostra() {
    const cv = document.createElement("canvas");
    cv.width = 1400;
    cv.height = 820;
    const g = cv.getContext("2d")!;
    g.fillStyle = "#fff";
    g.fillRect(0, 0, cv.width, cv.height);
    g.strokeStyle = "#222";
    g.lineWidth = 4;
    g.strokeRect(30, 30, 1340, 760);
    g.fillStyle = "#111";
    g.font = "bold 46px Arial";
    g.fillText("DOCUMENTO DE EXEMPLO - SEM VALOR LEGAL", 70, 120);
    g.font = "34px Arial";
    g.fillText("Cadastro de Pessoa Fisica", 70, 190);
    [["Nome", norm(candidato.nomeCompleto)], ["CPF", candidato.cpf ?? ""], ["Data de Nascimento", candidato.dataNascimento]].forEach(([k, v], i) => {
      g.font = "30px Arial";
      g.fillText(k, 70, 300 + i * 150);
      g.font = "bold 48px Arial";
      g.fillText(v, 70, 360 + i * 150);
    });
    const blob = await new Promise<Blob>((r) => cv.toBlob((b) => r(b!), "image/png"));
    const d = docs?.find((x) => x.codigo === "05");
    if (d) processar(d, new File([blob], "cpf-exemplo.png", { type: "image/png" }));
  }

  async function remover(tipo: string) {
    try {
      const st = await api.removerDocumento(insc.codCandidato, tipo);
      setDocs((d) => d?.map((x) => (x.codigo === tipo ? st : x)) ?? d);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Não foi possível remover.");
    }
  }

  async function continuar() {
    setAvancando(true);
    setErroEnvio(null);
    try {
      const r = await api.enviarDocumentos(insc.codCandidato);
      toast(r.mensagem);
      await recarregar();
      ir("pagamento");
    } catch (e) {
      setErroEnvio(e instanceof ApiError ? e.message : "Não foi possível enviar os documentos.");
      setAvancando(false);
    }
  }

  if (erro)
    return (
      <div className="grid">
        <Alert>{erro}</Alert>
        <div>
          <button className="btn btn-ghost" type="button" onClick={() => ir("dados")}>
            Voltar para Seus dados
          </button>
        </div>
      </div>
    );
  if (!docs) return <div className="skel" style={{ minHeight: 320 }} />;

  const obrig = docs.filter((d) => d.obrigatorio);
  const enviadosObrig = obrig.filter((d) => d.status !== "pendente").length;
  const ocupado = Object.values(local).some((l) => l.fase !== "revisar");
  const lista = docs.filter((d) => (filtro === "obrig" ? d.obrigatorio : filtro === "pend" ? d.status === "pendente" : true));

  const onDrop = (d: DocumentoStatus) => (e: DragEvent) => {
    e.preventDefault();
    setDrag(null);
    const f = e.dataTransfer.files[0];
    if (f && !somenteLeitura) processar(d, f);
  };

  return (
    <>
      <section className="card panel">
        {!somenteLeitura && (
          <div className="ocr-intro">
            <p>
              <b>Leitura automática (OCR).</b> Anexe cada documento: o texto é lido aqui mesmo no seu dispositivo e comparado com
              os seus dados. Divergências aparecem na hora. Os arquivos só vão para a secretaria quando você clicar em
              &quot;Enviar documentos e continuar&quot;.
            </p>
            {import.meta.env.DEV && (
              <button className="btn btn-ghost" type="button" onClick={amostra}>
                Testar com documento de exemplo
              </button>
            )}
          </div>
        )}
        <div className="panel-head">
          <div className="filter" role="group" aria-label="Filtrar documentos">
            {([["todos", "Todos"], ["obrig", "Obrigatórios"], ["pend", "Pendentes"]] as const).map(([v, t]) => (
              <button key={v} type="button" aria-pressed={filtro === v} onClick={() => setFiltro(v)}>
                {t}
              </button>
            ))}
          </div>
          <span className="muted" style={{ fontSize: 13 }}>
            {enviadosObrig} de {obrig.length} obrigatórios enviados
          </span>
        </div>
        <div className="docs">
          {lista.length === 0 && <p className="muted">Nenhum documento neste filtro.</p>}
          {lista.map((d) => {
            const l = local[d.codigo];
            const [tom, rotulo] = l?.analise ? VEREDITO[l.analise.veredito] : STATUS_SERVIDOR[d.status ?? "pendente"];
            return (
              <div
                key={d.codigo}
                className={`doc ${drag === d.codigo ? "drag" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDrag(d.codigo); }}
                onDragLeave={() => setDrag(null)}
                onDrop={onDrop(d)}
              >
                {l?.thumb ? <img className="thumb" src={l.thumb} alt="" /> : <span className="code">{d.codigo}</span>}
                <div style={{ minWidth: 0 }}>
                  <h4>{d.nome}</h4>
                  <div className="sub">
                    {d.obrigatorio ? <b style={{ color: "var(--bad)" }}>Obrigatório</b> : "Opcional"}
                    {l ? <> · <span className="mono">{l.nome}</span></> : d.arquivo ? <> · <span className="mono">{d.arquivo}</span>{d.enviadoEm ? ` · ${d.enviadoEm}` : ""}</> : !somenteLeitura && " · arraste o arquivo aqui"}
                  </div>
                </div>
                <div className="right">
                  {(l || d.status !== "pendente") && (
                    <Chip tone={l?.fase === "lendo" || l?.fase === "enviando" ? "info" : tom}>
                      {l?.fase === "lendo" ? <><Spin /> Lendo…</> : l?.fase === "enviando" ? <><Spin /> Enviando…</> : rotulo}
                    </Chip>
                  )}
                  {!somenteLeitura && (
                    <>
                      <label className="btn btn-ghost btn-sm" htmlFor={`up-${d.codigo}`} aria-disabled={l?.fase === "lendo"}>
                        {l || d.status !== "pendente" ? "Trocar" : "Anexar"}
                      </label>
                      {!l && d.status === "anexado" && (
                        <button className="btn btn-ghost btn-sm" type="button" onClick={() => remover(d.codigo)}>
                          Remover
                        </button>
                      )}
                      <input
                        className="sr"
                        type="file"
                        id={`up-${d.codigo}`}
                        accept={(d.extensoes ?? []).map((e) => "." + e).join(",")}
                        disabled={l?.fase === "lendo" || l?.fase === "enviando"}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          e.target.value = "";
                          if (f) processar(d, f);
                        }}
                      />
                    </>
                  )}
                </div>
                {l?.fase === "lendo" && (
                  <div className="ocr">
                    <div className="inline-status">
                      {l.etapa}
                      {l.progresso ? ` · ${Math.round(l.progresso * 100)}%` : ""}
                    </div>
                    <div className="bar">
                      <i style={{ width: `${Math.round(l.progresso * 100)}%` }} />
                    </div>
                  </div>
                )}
                {l?.analise && l.fase !== "lendo" && d.regra !== "foto" && (
                  <div className="ocr">
                    {l.analise.campos.length > 0 && (
                      <div className="found">
                        {l.analise.campos.map((c) => (
                          <span key={c.k} className={`kv ${c.ok ? "ok" : "bad"}`}>
                            {c.k}: <b>{c.v}</b> {c.ok ? "✓" : "✗"}
                          </span>
                        ))}
                        {l.analise.confianca != null && (
                          <span className="kv">
                            Confiança da leitura: <b>{l.analise.confianca}%</b>
                          </span>
                        )}
                      </div>
                    )}
                    {l.analise.alertas.map((a) => (
                      <p key={a} style={{ fontSize: 13, color: `var(--${["atencao", "erro"].includes(l.analise!.veredito) ? "warn" : "bad"})` }}>
                        {a}
                      </p>
                    ))}
                    {l.erro && <Alert>{l.erro}</Alert>}
                    {l.fase === "revisar" && (
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button className="btn btn-primary btn-sm" type="button" onClick={() => enviar(d.codigo)}>
                          {l.analise.veredito === "ok" ? "Tentar enviar de novo" : "Enviar para conferência manual"}
                        </button>
                        <label className="btn btn-ghost btn-sm" htmlFor={`up-${d.codigo}`}>
                          Escolher outro arquivo
                        </label>
                      </div>
                    )}
                    {l.analise.texto && (
                      <details className="raw">
                        <summary>Ver texto lido</summary>
                        <pre>{l.analise.texto.trim()}</pre>
                      </details>
                    )}
                  </div>
                )}
                {!l && d.observacao && (
                  <div className="ocr">
                    <p className="muted" style={{ fontSize: 13 }}>{d.observacao}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <p className="muted" style={{ fontSize: 12 }}>
          Formatos: JPG, PNG ou PDF (a primeira página é lida) · até {MAX_MB} MB por arquivo.
        </p>
      </section>
      {erroEnvio && <Alert>{erroEnvio}</Alert>}
      <div className="foot">
        <button className="btn btn-ghost" type="button" onClick={() => ir(somenteLeitura ? "conclusao" : "dados")}>
          Voltar
        </button>
        {!somenteLeitura && (
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <span className="muted" style={{ fontSize: 13 }} aria-live="polite">
              {ocupado ? "Aguarde a leitura terminar." : enviadosObrig < obrig.length ? `Faltam ${obrig.length - enviadosObrig} obrigatório(s).` : "Tudo pronto."}
            </span>
            <button
              className="btn btn-primary"
              type="button"
              disabled={enviadosObrig < obrig.length || ocupado || avancando}
              onClick={continuar}
            >
              {avancando ? <><Spin /> Enviando documentos</> : "Enviar documentos e continuar"}
            </button>
          </div>
        )}
      </div>
    </>
  );
}
