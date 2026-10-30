import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "../../api/client";
import type { DocumentoStatus, OcrResultado } from "../../api/types";
import { guardarAnexo, listarAnexos, removerAnexo, type AnexoLocal } from "../../lib/anexosLocais";
import { Alert, Spin, useToast } from "../../components/ui";
import { norm } from "../../lib/format";
import { canvasParaJpeg, ehWebp, imagemParaCanvas, miniatura } from "../../lib/imagem";
import { ACAO_POR_VEREDITO, analisar, type OcrAnalise, type Veredito } from "../../lib/ocr/analisar";
import { useWizard } from "./Wizard";

const MAX_MB = 10;

/** Tamanho para o candidato: KB abaixo de 1 MB (os limites do Lyceum são de ~1 MB). */
const tamanho = (n: number) =>
  n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;

/** Extensões que o candidato pode escolher: as do Lyceum + WEBP (convertido para JPG antes de anexar). */
function extensoesAceitas(d: DocumentoStatus): string[] {
  const ext = d.extensoes ?? [];
  return ext.some((e) => e === "jpg" || e === "jpeg") ? [...ext, "webp"] : ext;
}

// A análise começa assim que o arquivo é escolhido (não no envio final):
// formato → leitura (OCR) → é o documento certo? → os dados conferem? → resultado na própria linha.
interface Local {
  nome: string;
  arquivo: File;
  convertidoDe?: string; // ex.: "WEBP" → anexado como JPG
  thumb?: string;
  fase: "lendo" | "analisando" | "revisar" | "enviando" | "anexado";
  etapa: string;
  progresso: number;
  analise?: OcrAnalise;
  erro?: string;
}

type Tom = "ok" | "warn" | "bad" | "info" | "neutral";
const ICONE: Record<Tom, string> = { ok: "✓", warn: "⚠", bad: "✗", info: "", neutral: "" };

/** Selo de cada resultado da análise. */
const RESULTADO: Record<Veredito, { tom: Tom; selo: string; titulo: string }> = {
  ok: { tom: "ok", selo: "Documento conferido", titulo: "Documento conferido: é o documento esperado e os dados batem com o seu cadastro." },
  atencao: { tom: "warn", selo: "Conferido com ressalva", titulo: "Documento reconhecido, com um ponto que a secretaria vai conferir:" },
  divergente: { tom: "bad", selo: "Dados não conferem", titulo: "Os dados deste documento não conferem com o seu cadastro:" },
  tipo_errado: { tom: "bad", selo: "Documento não reconhecido", titulo: "Este não é o documento que esperamos." },
  ilegivel: { tom: "warn", selo: "Ilegível", titulo: "Não foi possível ler este arquivo." },
  erro: { tom: "warn", selo: "Não conferido", titulo: "Não foi possível conferir este documento automaticamente." },
};

const STATUS_SERVIDOR: Record<string, [Tom, string]> = {
  enviado: ["ok", "Enviado"],
  em_conferencia: ["warn", "Em conferência"],
  aprovado: ["ok", "Aprovado"],
  recusado: ["bad", "Recusado"],
};

function Selo({ tom, children, carregando }: { tom: Tom; children: string; carregando?: boolean }) {
  return (
    <span className={`chip ${tom} chip-icone`}>
      {carregando ? <Spin /> : ICONE[tom] && <b aria-hidden="true">{ICONE[tom]}</b>}
      {children}
    </span>
  );
}

export function EtapaDocumentos() {
  const { insc, ref: inscRef, candidato, recarregar, ir, somenteLeitura } = useWizard();
  const toast = useToast();
  const [docs, setDocs] = useState<DocumentoStatus[] | null>(null);
  const [local, setLocal] = useState<Record<string, Local>>({});
  const [filtro, setFiltro] = useState<"todos" | "obrig" | "pend">("todos");
  const [erro, setErro] = useState<string | null>(null);
  const [drag, setDrag] = useState<string | null>(null);
  const [avancando, setAvancando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  // documentos recusados no envio final (ex.: acima do limite de tamanho): código → aviso na linha
  const [recusados, setRecusados] = useState<Record<string, string>>({});
  const limparRecusa = (tipo: string) =>
    setRecusados((r) => { const { [tipo]: _, ...rest } = r; return rest; });
  // documento indo ao Lyceum agora (um por chamada) e a posição dele na fila
  const [enviando, setEnviando] = useState<{ tipo: string; n: number; total: number } | null>(null);
  // "ia": o servidor confere com IA (Claude); "navegador": OCR local (Tesseract)
  const [modo, setModo] = useState<"ia" | "navegador" | null>(null);
  const localRef = useRef(local);
  localRef.current = local;

  useEffect(() => {
    api.recursos().then((r) => setModo(r.conferenciaDocumentos)).catch(() => setModo("navegador"));
  }, []);

  /** Documentos do Lyceum + anexos guardados neste navegador (ficam aqui até o envio final). */
  async function carregar() {
    const id = insc.codCandidato; // chave dos anexos guardados neste navegador
    const [ds, guardados] = await Promise.all([api.documentos(inscRef), listarAnexos(id)]);
    const restaurados: Record<string, Local> = {};
    const lista = ds.map((d) => {
      const g = guardados.find((x) => x.tipo === d.codigo);
      if (!g) return d;
      if (d.status !== "pendente") {
        void removerAnexo(id, d.codigo); // o Lyceum já tem este documento
        return d;
      }
      const arquivo = new File([g.arquivo], g.nome, { type: g.arquivo.type });
      restaurados[d.codigo] = {
        nome: g.nome, arquivo, convertidoDe: g.convertidoDe, fase: "anexado", etapa: "", progresso: 0,
        analise: paraAnalise(g.analise),
      };
      miniatura(arquivo).then((thumb) => thumb && patch(d.codigo, { thumb })).catch(() => {});
      return anexadoLocal(d, g);
    });
    setDocs(lista);
    setLocal((l) => ({ ...restaurados, ...l }));
  }

  useEffect(() => {
    carregar().catch((e) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar documentos."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [insc.codCandidato]);

  /** Guarda no navegador o arquivo conferido + selo do servidor (devolvidos no envio final). */
  async function guardar(tipo: string, st: DocumentoStatus, arquivo: File, convertidoDe?: string) {
    if (st.status !== "anexado" || !st.selo) return;
    await guardarAnexo({ cand: insc.codCandidato, tipo, nome: arquivo.name, arquivo, selo: st.selo,
                         analise: st.analise ?? null, convertidoDe });
  }

  const patch = (tipo: string, p: Partial<Local>) =>
    setLocal((s) => (s[tipo] ? { ...s, [tipo]: { ...s[tipo], ...p } } : s));
  const ref = {
    nomeCompleto: candidato.nomeCompleto, cpf: candidato.cpf, dataNascimento: candidato.dataNascimento,
    cep: candidato.endereco.cep,
  };

  /** Anexa no portal (fica "pronto para envio"; o envio ao Lyceum é só no final). */
  async function anexar(tipo: string) {
    const l = localRef.current[tipo];
    if (!l) return;
    patch(tipo, { fase: "enviando", erro: undefined });
    try {
      const a = l.analise;
      // O texto bruto do OCR não é enviado: só veredito, confiança, campos e alertas.
      const ocr = a ? { veredito: a.veredito, confianca: a.confianca ?? null, campos: a.campos, alertas: a.alertas } : undefined;
      const st = await api.enviarDocumento(inscRef, tipo, l.arquivo, ocr);
      await guardar(tipo, st, l.arquivo, l.convertidoDe);
      setDocs((d) => d?.map((x) => (x.codigo === tipo ? st : x)) ?? d);
      patch(tipo, { fase: "anexado" });
      toast(a && a.veredito !== "ok" ? "Documento anexado. A secretaria vai conferir o ponto indicado." : "Documento conferido e anexado.");
    } catch (e) {
      patch(tipo, { fase: "revisar", erro: e instanceof ApiError ? e.message : "Falha ao anexar. Tente novamente." });
    }
  }

  /** Modo IA: o arquivo vai direto ao servidor, que lê com IA e confere; a tela só mostra o resultado. */
  async function processarIA(d: DocumentoStatus, file: File) {
    const tipo = d.codigo;
    setLocal((s) => ({ ...s, [tipo]: { nome: file.name, arquivo: file, fase: "analisando", etapa: "", progresso: 0 } }));
    let arquivo = file;
    try {
      if (ehWebp(file)) {
        // o Lyceum não aceita WEBP: envia a mesma imagem em JPG
        arquivo = await canvasParaJpeg(await imagemParaCanvas(file), file.name);
        if (arquivo.size > MAX_MB * 1024 * 1024) {
          setLocal((s) => { const { [tipo]: _, ...rest } = s; return rest; });
          return toast(`A imagem convertida passou de ${MAX_MB} MB. Envie um arquivo menor.`);
        }
        patch(tipo, { arquivo, nome: arquivo.name, convertidoDe: "WEBP" });
      }
      miniatura(arquivo).then((thumb) => thumb && patch(tipo, { thumb })).catch(() => {});
      const st = await api.enviarDocumento(inscRef, tipo, arquivo);
      await guardar(tipo, st, arquivo, arquivo === file ? undefined : "WEBP");
      setDocs((ds) => ds?.map((x) => (x.codigo === tipo ? st : x)) ?? ds);
      const a = st.analise;
      const analise: OcrAnalise | undefined = a
        ? { veredito: a.veredito, campos: a.campos ?? [], alertas: a.alertas ?? [], texto: "", confianca: a.confianca ?? undefined }
        : undefined;
      patch(tipo, { analise, fase: st.status === "anexado" ? "anexado" : "revisar" });
      if (st.status === "anexado")
        toast(analise && analise.veredito !== "ok" ? "Documento anexado. A secretaria vai conferir o ponto indicado." : "Documento conferido e anexado.");
    } catch (e) {
      patch(tipo, {
        fase: "revisar",
        analise: { veredito: "erro", campos: [], texto: "", alertas: [] },
        erro: e instanceof ApiError ? e.message : "Falha ao enviar. Tente novamente.",
      });
    }
  }

  async function processar(d: DocumentoStatus, file: File) {
    limparRecusa(d.codigo);
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    const aceitas = extensoesAceitas(d);
    if (!aceitas.includes(ext)) return toast(`Formato não aceito. Envie: ${aceitas.join(", ").toUpperCase()}.`);
    if (file.size > MAX_MB * 1024 * 1024) return toast(`Arquivo acima de ${MAX_MB} MB. Reduza o tamanho e tente de novo.`);
    if (modo === "ia") return processarIA(d, file);
    const tipo = d.codigo;
    setLocal((s) => ({ ...s, [tipo]: { nome: file.name, arquivo: file, fase: "lendo", etapa: "Preparando arquivo", progresso: 0 } }));
    let analise: OcrAnalise;
    let arquivo = file;
    try {
      const { canvasParaJpeg, ehWebp, fileToCanvas, reconhecer } = await import("../../lib/ocr/engine");
      const cv = await fileToCanvas(file);
      patch(tipo, { thumb: cv.toDataURL("image/jpeg", 0.5) });
      if (ehWebp(file)) {
        // o Lyceum não aceita WEBP: anexa a mesma imagem em JPG
        arquivo = await canvasParaJpeg(cv, file.name);
        if (arquivo.size > MAX_MB * 1024 * 1024) {
          setLocal((s) => { const { [tipo]: _, ...rest } = s; return rest; });
          return toast(`A imagem convertida passou de ${MAX_MB} MB. Envie um arquivo menor.`);
        }
        patch(tipo, { arquivo, nome: arquivo.name, convertidoDe: "WEBP" });
      }
      if (d.regra === "foto") {
        analise = { veredito: "ok", campos: [], alertas: [], texto: "" };
      } else {
        const r = await reconhecer(cv, (p) => patch(tipo, { etapa: p.etapa, progresso: p.progresso }));
        analise = analisar(r.texto, d, ref, r.confianca);
      }
    } catch (e) {
      console.error(e);
      analise = {
        veredito: "erro", campos: [], texto: "",
        alertas: ["O navegador não conseguiu ler este arquivo (ex.: PDF protegido). Envie outro arquivo ou mantenha este para a secretaria conferir."],
      };
    }
    patch(tipo, { analise, fase: "revisar" });
    // arquivo explícito: o estado pode ainda não ter renderizado a troca WEBP → JPG
    localRef.current = { ...localRef.current, [tipo]: { ...localRef.current[tipo], analise, fase: "revisar", arquivo, nome: arquivo.name } };
    const acao = ACAO_POR_VEREDITO[analise.veredito];
    if (acao === "anexar" || acao === "anexar_com_aviso") await anexar(tipo);
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

  /** Remove só do navegador: o arquivo ainda não foi ao Lyceum. */
  async function remover(tipo: string) {
    limparRecusa(tipo);
    await removerAnexo(insc.codCandidato, tipo);
    setDocs((d) => d?.map((x) => (x.codigo === tipo
      ? { ...x, status: "pendente", arquivo: null, ocrVeredito: null, observacao: null, analise: null, selo: null }
      : x)) ?? d);
    setLocal((s) => {
      const { [tipo]: _, ...rest } = s;
      return rest;
    });
  }

  /** Aviso acima do botão (e em toast), com rolagem até ele para não passar despercebido. */
  function avisarEnvio(msg: string) {
    setErroEnvio(msg);
    toast(msg);
    requestAnimationFrame(() => document.getElementById("erro-envio")?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }

  /** Envia ao Lyceum UM documento por chamada: o que passar já fica enviado e o que for recusado fica marcado na
   *  linha, com o motivo. Obrigatórios primeiro, do menor para o maior (o primeiro envio abre a etapa no legado). */
  async function continuar() {
    setAvancando(true);
    setErroEnvio(null);
    setRecusados({});
    const id = insc.codCandidato; // chave dos anexos guardados neste navegador
    const lista = docs ?? [];
    const doc = (tipo: string) => lista.find((d) => d.codigo === tipo);
    const noLyceum = new Set(lista.filter((d) => STATUS_SERVIDOR[d.status ?? ""]).map((d) => d.codigo));
    try {
      const guardados = await listarAnexos(id);
      if (!guardados.length) {
        // nada guardado aqui: o servidor confere se os obrigatórios já estão no Lyceum
        const r = await api.enviarDocumentos(inscRef, []);
        toast(r.mensagem);
        await recarregar();
        return ir("pagamento");
      }
      const fila = [...guardados].sort((a, b) =>
        Number(!!doc(b.tipo)?.obrigatorio) - Number(!!doc(a.tipo)?.obrigatorio) || a.arquivo.size - b.arquivo.size);
      const recusas: Record<string, string> = {};
      let simulado = false;
      let falhaGeral: string | null = null;
      for (const [i, g] of fila.entries()) {
        setEnviando({ tipo: g.tipo, n: i + 1, total: fila.length });
        let motivo: string | null = null;
        try {
          const r = await api.enviarDocumentos(inscRef, [{ tipo: g.tipo, nome: g.nome, arquivo: g.arquivo, selo: g.selo }]);
          const st = r.documentos.find((d) => d.codigo === g.tipo);
          if (r.simulado) {
            simulado = true;
          } else if (!r.recusados?.[g.tipo] && st && STATUS_SERVIDOR[st.status ?? ""]) {
            // entrou no Lyceum: sai do navegador e a linha passa a "Enviado"
            await removerAnexo(id, g.tipo);
            setLocal((s) => { const { [g.tipo]: _, ...rest } = s; return rest; });
            setDocs((ds) => ds?.map((x) => (x.codigo === g.tipo ? st : x)) ?? ds);
            noLyceum.add(g.tipo);
          } else {
            motivo = r.recusados?.[g.tipo] ?? "O Processo Seletivo não registrou este arquivo. Tente enviar de novo.";
          }
        } catch (e) {
          // recusa deste documento (vem marcada pelo código) ou 413 de um limite antes do portal (ex.: Vercel)
          motivo = e instanceof ApiError
            ? e.campos[g.tipo] ?? (e.status === 413 ? `Arquivo de ${tamanho(g.arquivo.size)}: passou do limite de tamanho do envio. Escolha um arquivo menor.` : null)
            : null;
          // sem conexão, sessão expirada, Lyceum fora do ar: para tudo (o que já foi enviado fica)
          if (!motivo) falhaGeral = e instanceof ApiError ? e.message : "Não foi possível enviar os documentos.";
        }
        if (falhaGeral) break;
        if (motivo) {
          recusas[g.tipo] = motivo;
          setRecusados({ ...recusas });
          // primeiro envio recusado: não tenta os outros (só depois que o primeiro entra é que eles podem ir)
          if (!noLyceum.size) break;
        }
      }
      setEnviando(null);
      const faltando = Object.keys(recusas);
      if (faltando.length) setFiltro("todos"); // a linha marcada não pode ficar escondida pelo filtro
      if (falhaGeral) {
        const ja = fila.filter((g) => noLyceum.has(g.tipo)).length;
        return avisarEnvio(ja ? `${falhaGeral} ${ja} documento(s) já foram enviados; envie de novo para continuar.` : falhaGeral);
      }
      if (faltando.length) {
        const nomes = faltando.map((t) => doc(t)?.nome ?? t).join(", ");
        const enviados = fila.filter((g) => noLyceum.has(g.tipo)).length;
        return avisarEnvio(enviados
          ? `Enviados ${enviados} de ${fila.length}. Falta trocar: ${nomes}.`
          : `${nomes} não foi enviado: ${recusas[faltando[0]]} Os outros documentos só vão depois que este entrar no Lyceum.`);
      }
      if (simulado) toast("Envio simulado (ambiente de desenvolvimento): nada foi enviado ao Lyceum.");
      else toast("Documentos enviados.");
      if (simulado || lista.every((d) => !d.obrigatorio || noLyceum.has(d.codigo))) {
        await recarregar();
        return ir("pagamento");
      }
      // obrigatório que não estava anexado (o botão impede, mas o Lyceum é quem decide)
      await carregar();
    } catch (e) {
      setEnviando(null);
      avisarEnvio(e instanceof ApiError ? e.message : "Não foi possível enviar os documentos.");
    } finally {
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
  const prontosObrig = obrig.filter((d) => d.status !== "pendente").length;
  const ocupado = Object.values(local).some((l) => l.fase === "lendo" || l.fase === "enviando" || l.fase === "analisando");
  const lista = docs.filter((d) => (filtro === "obrig" ? d.obrigatorio : filtro === "pend" ? d.status === "pendente" : true));

  const onDrop = (d: DocumentoStatus) => (e: DragEvent) => {
    e.preventDefault();
    setDrag(null);
    const f = e.dataTransfer.files[0];
    if (f && !somenteLeitura) processar(d, f);
  };

  /** Selo da linha: análise em andamento/resultado, ou situação guardada no servidor. */
  function selo(d: DocumentoStatus, l?: Local) {
    if (enviando?.tipo === d.codigo) return <Selo tom="info" carregando>Enviando…</Selo>;
    if (recusados[d.codigo]) return <Selo tom="bad">Não enviado · troque o arquivo</Selo>;
    if (l?.fase === "lendo") return <Selo tom="info" carregando>{l.progresso ? `Lendo… ${Math.round(l.progresso * 100)}%` : "Lendo…"}</Selo>;
    if (l?.fase === "enviando") return <Selo tom="info" carregando>Anexando…</Selo>;
    if (l?.fase === "analisando")
      return (
        <span className="chip info chip-icone">
          <span className="pulsando">Analisando</span>
        </span>
      );
    if (l?.analise && l.fase === "revisar") {
      const r = RESULTADO[l.analise.veredito];
      return <Selo tom={r.tom}>{r.selo}</Selo>;
    }
    if (d.status === "anexado")
      return d.ocrVeredito === "ok" || d.regra === "foto"
        ? <Selo tom="ok">Conferido · pronto para envio</Selo>
        : <Selo tom="warn">Para conferência · pronto para envio</Selo>;
    const s = STATUS_SERVIDOR[d.status ?? ""];
    return s ? <Selo tom={s[0]}>{s[1]}</Selo> : null;
  }

  return (
    <>
      <section className="card panel">
        {!somenteLeitura && (
          <div className="ocr-intro">
            <p>
              <b>Conferência automática.</b>{" "}
              {modo === "ia"
                ? "Assim que você anexa, o documento é analisado (leva alguns segundos): verificamos se é o documento pedido e se os dados batem com o seu cadastro. Pode anexar vários ao mesmo tempo."
                : "Assim que você anexa, o documento é lido aqui no seu dispositivo: verificamos se é o documento pedido e se os dados batem com o seu cadastro."} <span className="ok-txt">✓</span> conferido,{" "}
              <span className="warn-txt">⚠</span> a secretaria confere, <span className="bad-txt">✗</span> envie outro arquivo.
              Os arquivos só vão para a secretaria quando você clicar em &quot;Enviar documentos e continuar&quot;.
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
            {prontosObrig} de {obrig.length} obrigatórios anexados
          </span>
        </div>
        <div className="docs">
          {lista.length === 0 && <p className="muted">Nenhum documento neste filtro.</p>}
          {lista.map((d) => {
            const l = local[d.codigo];
            const a = l?.analise;
            // depois de anexado para conferência manual, o destaque deixa de ser "✗" e vira "⚠"
            const r = !a ? null : l.fase === "anexado" && a.veredito !== "ok"
              ? { ...RESULTADO[a.veredito], tom: "warn" as Tom, titulo: "Anexado para a secretaria conferir:" }
              : RESULTADO[a.veredito];
            const acao = a ? ACAO_POR_VEREDITO[a.veredito] : null;
            const mostrarAnalise = a && l.fase !== "lendo" && (d.regra !== "foto" || a.veredito !== "ok");
            return (
              <div
                key={d.codigo}
                className={`doc ${drag === d.codigo ? "drag" : ""} ${recusados[d.codigo] ? "doc-bad" : r && l?.fase === "revisar" ? `doc-${r.tom}` : ""}`}
                data-doc={d.codigo}
                onDragOver={(e) => { e.preventDefault(); setDrag(d.codigo); }}
                onDragLeave={() => setDrag(null)}
                onDrop={onDrop(d)}
              >
                {l?.thumb ? <img className="thumb" src={l.thumb} alt="" /> : <span className="code">{d.codigo}</span>}
                <div style={{ minWidth: 0 }}>
                  <h4>{d.nome}</h4>
                  <div className="sub">
                    {d.obrigatorio ? <b style={{ color: "var(--bad)" }}>Obrigatório</b> : "Opcional"}
                    {l ? <> · <span className="mono">{l.nome}</span>{l.convertidoDe ? ` (convertido de ${l.convertidoDe})` : ""}</> : d.arquivo ? <> · <span className="mono">{d.arquivo}</span>{d.enviadoEm ? ` · ${d.enviadoEm}` : ""}</> : !somenteLeitura && " · arraste o arquivo aqui"}
                  </div>
                </div>
                <div className="right">
                  {selo(d, l)}
                  {!somenteLeitura && (
                    <>
                      <label className="btn btn-ghost btn-sm" htmlFor={`up-${d.codigo}`} aria-disabled={l?.fase === "lendo" || avancando}>
                        {l || d.status !== "pendente" ? "Trocar" : "Anexar"}
                      </label>
                      {d.status === "anexado" && l?.fase !== "lendo" && l?.fase !== "enviando" && !avancando && (
                        <button className="btn btn-ghost btn-sm" type="button" onClick={() => remover(d.codigo)}>
                          Remover
                        </button>
                      )}
                      <input
                        className="sr"
                        type="file"
                        id={`up-${d.codigo}`}
                        accept={extensoesAceitas(d).map((e) => "." + e).join(",")}
                        disabled={l?.fase === "lendo" || l?.fase === "enviando" || avancando}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          e.target.value = "";
                          if (f) processar(d, f);
                        }}
                      />
                    </>
                  )}
                </div>
                {l?.fase === "analisando" && (
                  <div className="ocr analisando">
                    <div className="bar indeterminada" aria-hidden="true"><i /></div>
                    <span className="pulsando" role="status">
                      Analisando o documento… leva alguns segundos. Você pode anexar os outros enquanto isso.
                    </span>
                  </div>
                )}
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
                {mostrarAnalise && r && (
                  <div className="ocr">
                    <p className={`resultado ${r.tom}`}>
                      <b aria-hidden="true">{ICONE[r.tom]}</b> {r.titulo}
                    </p>
                    {a.alertas.map((t) => (
                      <p key={t} className="resultado-detalhe">{t}</p>
                    ))}
                    {a.campos.length > 0 && (
                      <div className="found">
                        {a.campos.map((c) => (
                          <span key={c.k} className={`kv ${c.ok ? "ok" : "bad"}`}>
                            {c.k}: <b>{c.v}</b> {c.ok ? "✓" : "✗"}
                          </span>
                        ))}
                        {a.confianca != null && (
                          <span className="kv">
                            Confiança da leitura: <b>{a.confianca}%</b>
                          </span>
                        )}
                      </div>
                    )}
                    {l.erro && <Alert>{l.erro}</Alert>}
                    {l.fase === "revisar" && !somenteLeitura && (
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {(acao === "trocar" || acao === "manual_ou_trocar") && (
                          <label className="btn btn-primary btn-sm" htmlFor={`up-${d.codigo}`}>
                            Escolher outro arquivo
                          </label>
                        )}
                        {modo === "ia" && l.erro && (
                          <button className="btn btn-ghost btn-sm" type="button" onClick={() => processarIA(d, l.arquivo)}>
                            Tentar de novo
                          </button>
                        )}
                        {acao === "manual_ou_trocar" && modo !== "ia" && (
                          <button className="btn btn-ghost btn-sm" type="button" onClick={() => anexar(d.codigo)}>
                            Manter este e enviar para conferência manual
                          </button>
                        )}
                        {(acao === "anexar" || acao === "anexar_com_aviso") && l.erro && (
                          <button className="btn btn-primary btn-sm" type="button" onClick={() => anexar(d.codigo)}>
                            Tentar de novo
                          </button>
                        )}
                      </div>
                    )}
                    {a.texto && (
                      <details className="raw">
                        <summary>Ver texto lido</summary>
                        <pre>{a.texto.trim()}</pre>
                      </details>
                    )}
                  </div>
                )}
                {recusados[d.codigo] && (
                  <div className="ocr" role="alert">
                    <p className="resultado bad">
                      <b aria-hidden="true">✗</b> {recusados[d.codigo]}
                    </p>
                    {!somenteLeitura && (
                      <div>
                        <label className="btn btn-primary btn-sm" htmlFor={`up-${d.codigo}`}>
                          Escolher outro arquivo
                        </label>
                      </div>
                    )}
                  </div>
                )}
                {!l && d.observacao && (
                  <div className="ocr">
                    <p className="resultado warn"><b aria-hidden="true">⚠</b> {d.observacao}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <p className="muted" style={{ fontSize: 12 }}>
          Formatos: JPG, PNG, WEBP (enviado como JPG) ou PDF (a primeira página é lida) · até {MAX_MB} MB por arquivo.
        </p>
      </section>
      {erroEnvio && (
        <div id="erro-envio" style={{ marginTop: 16 }}>
          <Alert>
            {erroEnvio}
            {Object.keys(recusados).length > 0 && " O que precisa ser trocado está marcado em vermelho na lista acima."}
          </Alert>
        </div>
      )}
      <div className="foot">
        <button className="btn btn-ghost" type="button" onClick={() => ir(somenteLeitura ? "conclusao" : "dados")}>
          Voltar
        </button>
        {!somenteLeitura && (
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <span className="muted" style={{ fontSize: 13 }} aria-live="polite">
              {ocupado ? "Aguarde a conferência terminar." : prontosObrig < obrig.length ? `Faltam ${obrig.length - prontosObrig} obrigatório(s).` : "Tudo pronto."}
            </span>
            <button
              className="btn btn-primary"
              type="button"
              disabled={prontosObrig < obrig.length || ocupado || avancando}
              onClick={continuar}
            >
              {avancando
                ? <><Spin /> {enviando ? `Enviando ${enviando.n} de ${enviando.total}` : "Enviando documentos"}</>
                : "Enviar documentos e continuar"}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

/** Resultado guardado da conferência → formato da tela. */
function paraAnalise(a?: OcrResultado | null): OcrAnalise | undefined {
  return a ? { veredito: a.veredito, campos: a.campos ?? [], alertas: a.alertas ?? [], texto: "", confianca: a.confianca ?? undefined } : undefined;
}

/** Linha do documento anexado neste navegador (ainda não enviado ao Lyceum). */
function anexadoLocal(d: DocumentoStatus, g: AnexoLocal): DocumentoStatus {
  const v = g.analise?.veredito ?? null;
  return { ...d, status: "anexado", arquivo: g.nome, ocrVeredito: v, analise: g.analise ?? null, selo: g.selo,
           observacao: v === "ok" || d.regra === "foto" ? null : "Será conferido pela secretaria." };
}
