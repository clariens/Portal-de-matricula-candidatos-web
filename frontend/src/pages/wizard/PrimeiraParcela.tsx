import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { PagamentoResultado, Pix } from "../../api/types";
import { Alert, Chip, Spin, useToast } from "../../components/ui";
import { brl } from "../../lib/format";

type Cobranca = PagamentoResultado["cobranca"];
type Forma = "Boleto" | "PIX";

// Boleto e PIX geram cobrança no banco: cada inscrição gera uma vez por página aberta (o StrictMode do React e
// as remontagens não podem pedir de novo). "Tentar de novo" limpa a entrada daquela inscrição.
const geracoes = new Map<string, Promise<Blob | Pix>>();

function gerar(ref: string, forma: Forma): Promise<Blob | Pix> {
  const chave = `${forma}:${ref}`;
  let p = geracoes.get(chave);
  if (!p) {
    p = forma === "Boleto" ? api.boleto(ref) : api.pix(ref);
    p.catch(() => geracoes.delete(chave));
    geracoes.set(chave, p);
  }
  return p;
}

/** 1ª parcela depois de confirmar o pagamento: boleto em PDF ou PIX com QR code e copia e cola, gerados na hora
 *  pelo Processo Seletivo. Sem a forma (aba nova), a pessoa escolhe qual gerar. */
export function PrimeiraParcela({ inscRef, cobranca }: { inscRef: string; cobranca: Cobranca | null }) {
  const forma = cobranca?.formaPagamento;
  const [escolhida, setEscolhida] = useState<Forma | null>(forma === "Boleto" || forma === "PIX" ? forma : null);

  return (
    <section className="card panel" style={{ marginTop: 16 }}>
      <div className="panel-head">
        <h2>Primeira parcela</h2>
        {forma && <Chip tone="info">{forma === "Cartao" ? "Cartão" : forma}</Chip>}
      </div>
      {cobranca && (
        <div className="cobranca">
          <span>
            {cobranca.valorParcela != null ? <><b>{brl(cobranca.valorParcela)}</b>/mês · {cobranca.numParcelas} mensalidades</> : `${cobranca.numParcelas} mensalidades`}
            {cobranca.vencimento ? ` · vencimento ${cobranca.vencimento}` : ""}
          </span>
          {forma === "Cartao" && <span className="muted">{cobranca.instrucoes}</span>}
        </div>
      )}
      {forma !== "Cartao" && !escolhida && (
        <div className="parcela-escolha">
          <span className="muted">Gere o pagamento da 1ª parcela:</span>
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => setEscolhida("Boleto")}>Boleto</button>
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => setEscolhida("PIX")}>PIX</button>
        </div>
      )}
      {escolhida && <Gerado key={escolhida} inscRef={inscRef} forma={escolhida} />}
    </section>
  );
}

function Gerado({ inscRef, forma }: { inscRef: string; forma: Forma }) {
  const toast = useToast();
  const [res, setRes] = useState<{ url?: string; pix?: Pix } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    let url: string | undefined;
    setErro(null);
    setRes(null);
    gerar(inscRef, forma)
      .then((r) => {
        if (!ativo) return;
        if (r instanceof Blob) {
          url = URL.createObjectURL(r);
          setRes({ url });
        } else setRes({ pix: r });
      })
      .catch((e) => ativo && setErro(e instanceof ApiError ? e.message : `Não foi possível gerar o ${forma === "PIX" ? "PIX" : "boleto"}.`));
    return () => {
      ativo = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [inscRef, forma, tentativa]);

  async function copiar(codigo: string) {
    try {
      await navigator.clipboard.writeText(codigo);
      toast("Código PIX copiado.");
    } catch {
      toast("Não foi possível copiar. Selecione o código e copie manualmente.");
    }
  }

  if (erro)
    return (
      <div className="parcela">
        <Alert tone="warn">{erro}</Alert>
        <div>
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => setTentativa((n) => n + 1)}>Tentar de novo</button>
        </div>
      </div>
    );
  if (!res)
    return (
      <p className="parcela muted" role="status">
        <Spin /> {forma === "PIX" ? "Gerando o PIX…" : "Gerando o boleto…"}
      </p>
    );
  if (res.url)
    return (
      <div className="parcela parcela-boleto">
        <p>O boleto da 1ª parcela está pronto.</p>
        <div className="parcela-acoes">
          <a className="btn btn-primary btn-sm" href={res.url} target="_blank" rel="noopener noreferrer">Abrir boleto</a>
          <a className="btn btn-ghost btn-sm" href={res.url} download="boleto-1a-parcela.pdf">Baixar</a>
        </div>
      </div>
    );
  const pix = res.pix!;
  return (
    <div className="parcela parcela-pix">
      <img className="pix-qr" src={pix.qrCode} alt="QR code do PIX da 1ª parcela" width={220} height={220} />
      <div className="pix-dados">
        <p>Aponte a câmera do aplicativo do banco para o QR code ou use o código copia e cola.</p>
        {pix.valor != null && <p>Valor: <b>{brl(pix.valor)}</b></p>}
        {pix.recebedor && <p className="muted">Antes de pagar, confira se o recebedor é <b>{pix.recebedor}</b>.</p>}
        <label className="pix-codigo">
          <span>Código copia e cola</span>
          <textarea readOnly rows={3} value={pix.copiaECola} onFocus={(e) => e.currentTarget.select()} />
        </label>
        <div className="parcela-acoes">
          <button className="btn btn-primary btn-sm" type="button" onClick={() => copiar(pix.copiaECola)}>Copiar código</button>
        </div>
      </div>
    </div>
  );
}
