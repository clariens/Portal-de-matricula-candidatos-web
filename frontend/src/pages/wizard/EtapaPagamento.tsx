import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { OpcoesPagamento, PagamentoIn, Plano } from "../../api/types";
import { ENDERECO_VAZIO, EnderecoFields, validarEndereco, type EnderecoForm } from "../../components/EnderecoFields";
import { Alert, Field, Spin } from "../../components/ui";
import { brl, cnpjValido, cpfValido, dataValida, digits, emailValido } from "../../lib/format";
import { useWizard } from "./Wizard";

type TipoResp = PagamentoIn["tipoResp"];
interface RespForm {
  nome: string;
  documento: string;
  dataNascimento: string;
  email: string;
  celular: string;
  endereco: EnderecoForm;
}
const RESP_VAZIO: RespForm = { nome: "", documento: "", dataNascimento: "", email: "", celular: "", endereco: ENDERECO_VAZIO };

const TIPOS: [TipoResp, string, string][] = [
  ["Pessoa", "Eu mesmo(a)", "O contrato sai no seu nome"],
  ["OutraPessoa", "Outra pessoa", "Pai, mãe ou outro responsável"],
  ["Empresa", "Empresa", "Pagamento por CNPJ"],
];

export const COBRANCA_KEY = (id: string) => `cobranca:${id}`;

export function EtapaPagamento() {
  const { insc, ir, recarregar } = useWizard();
  const [op, setOp] = useState<OpcoesPagamento | null>(null);
  const [planos, setPlanos] = useState<Plano[]>([]);
  const [tipo, setTipo] = useState<TipoResp>("Pessoa");
  const [resp, setResp] = useState<RespForm>(RESP_VAZIO);
  const [plano, setPlano] = useState<string>("");
  const [cupom, setCupom] = useState("");
  const [cupomMsg, setCupomMsg] = useState<{ ok: boolean; msg: string } | null>(null);
  const [cupomAplicado, setCupomAplicado] = useState<string | null>(null);
  const [validando, setValidando] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api
      .opcoesPagamento(insc.codCandidato)
      .then((o) => {
        setOp(o);
        setPlanos(o.planos);
        setPlano(o.planos.find((p) => p.disponivel)?.codigo ?? "");
        if (o.cupomAplicado) {
          setCupom(o.cupomAplicado);
          setCupomAplicado(o.cupomAplicado);
        }
      })
      .catch((e) => setErro(e instanceof ApiError ? e.message : "Erro ao carregar as opções de pagamento."));
  }, [insc.codCandidato]);

  const setR = <K extends keyof RespForm>(k: K) => (v: RespForm[K]) => setResp((r) => ({ ...r, [k]: v }));

  async function aplicarCupom() {
    const c = cupom.trim();
    if (!c) return;
    setValidando(true);
    try {
      const r = await api.validarCupom(insc.codCandidato, c);
      setCupomMsg({ ok: r.valido, msg: r.mensagem });
      if (r.valido) {
        setCupomAplicado(c.toUpperCase());
        if (r.planos) setPlanos(r.planos);
      }
    } catch (e) {
      setCupomMsg({ ok: false, msg: e instanceof ApiError ? e.message : "Não foi possível validar o cupom." });
    } finally {
      setValidando(false);
    }
  }

  function validar() {
    const er: Record<string, string> = {};
    if (!plano) er.codigoPlano = "Escolha a forma de pagamento.";
    if (tipo !== "Pessoa") {
      if (resp.nome.trim().length < 3) er["responsavel.nome"] = "Campo obrigatório.";
      if (tipo === "OutraPessoa" && !cpfValido(resp.documento)) er["responsavel.documento"] = "CPF do responsável inválido.";
      if (tipo === "Empresa" && !cnpjValido(resp.documento)) er["responsavel.documento"] = "CNPJ inválido.";
      if (tipo === "OutraPessoa" && !dataValida(resp.dataNascimento)) er["responsavel.dataNascimento"] = "Use o formato dd/mm/aaaa.";
      if (!emailValido(resp.email)) er["responsavel.email"] = "E-mail inválido.";
      if (digits(resp.celular).length !== 11) er["responsavel.celular"] = "Informe DDD + 9 dígitos.";
      Object.assign(er, validarEndereco(resp.endereco, "responsavel.endereco"));
    }
    return er;
  }

  async function confirmar() {
    const er = validar();
    setErrors(er);
    setErro(null);
    if (Object.keys(er).length) {
      requestAnimationFrame(() => (document.querySelector(".input.invalid") as HTMLElement | null)?.focus());
      return;
    }
    setEnviando(true);
    try {
      const body: PagamentoIn = {
        tipoResp: tipo,
        codigoPlano: plano,
        voucher: cupomAplicado,
        responsavel:
          tipo === "Pessoa"
            ? null
            : {
                nome: resp.nome, documento: resp.documento, email: resp.email, celular: resp.celular,
                dataNascimento: tipo === "OutraPessoa" ? resp.dataNascimento : null,
                endereco: { ...resp.endereco, complemento: resp.endereco.complemento || null },
              },
      };
      const r = await api.efetivarPagamento(insc.codCandidato, body);
      try {
        sessionStorage.setItem(COBRANCA_KEY(insc.codCandidato), JSON.stringify(r.cobranca));
      } catch {
        /* sessionStorage indisponível: a conclusão funciona sem a cobrança */
      }
      await recarregar();
      ir("conclusao");
    } catch (e) {
      if (e instanceof ApiError) {
        setErrors(e.campos);
        setErro(e.message);
      } else setErro("Não foi possível confirmar o pagamento.");
    } finally {
      setEnviando(false);
    }
  }

  if (!op) return erro ? <Alert>{erro}</Alert> : <div className="skel" style={{ minHeight: 320 }} />;

  return (
    <>
      {erro && <Alert>{erro}</Alert>}
      <section className="card panel">
        <h2>Responsável financeiro</h2>
        <div className="choices" role="radiogroup" aria-label="Responsável financeiro">
          {TIPOS.filter(([v]) => op.tiposResponsavel.includes(v)).map(([v, t, d]) => (
            <label key={v} className="choice">
              <input type="radio" name="resp" value={v} checked={tipo === v} onChange={() => setTipo(v)} />
              <b>{t}</b>
              <span className="muted" style={{ fontSize: 13 }}>
                {d}
              </span>
            </label>
          ))}
        </div>
        {tipo !== "Pessoa" && (
          <>
            <div className="grid g12">
              <Field id="r-nome" label={tipo === "Empresa" ? "Razão social" : "Nome do responsável"} value={resp.nome} onValue={setR("nome")} cls="c8" error={errors["responsavel.nome"]} />
              <Field id="r-doc" label={tipo === "Empresa" ? "CNPJ" : "CPF do responsável"} value={resp.documento} onValue={setR("documento")} cls="c4" mask={tipo === "Empresa" ? "cnpj" : "cpf"} inputMode="numeric" error={errors["responsavel.documento"]} />
              {tipo === "OutraPessoa" && (
                <Field id="r-nasc" label="Data de nascimento" value={resp.dataNascimento} onValue={setR("dataNascimento")} cls="c4" mask="date" inputMode="numeric" placeholder="dd/mm/aaaa" error={errors["responsavel.dataNascimento"]} />
              )}
              <Field id="r-email" label="E-mail" type="email" value={resp.email} onValue={setR("email")} cls={tipo === "OutraPessoa" ? "c4" : "c6"} error={errors["responsavel.email"]} />
              <Field id="r-cel" label="Celular (WhatsApp)" value={resp.celular} onValue={setR("celular")} cls={tipo === "OutraPessoa" ? "c4" : "c6"} mask="phone" inputMode="tel" hint="Recebe o contrato para assinatura" error={errors["responsavel.celular"]} />
            </div>
            <h3 className="sub-title">Endereço do responsável</h3>
            <EnderecoFields value={resp.endereco} onChange={setR("endereco")} errors={errors} prefixo="responsavel.endereco" />
          </>
        )}
      </section>
      <section className="card panel">
        <h2>Forma de pagamento</h2>
        <div className="choices" role="radiogroup" aria-label="Forma de pagamento">
          {planos.map((p) => (
            <label key={p.codigo} className="choice" title={p.motivoIndisponivel ?? undefined}>
              <input type="radio" name="plano" value={p.codigo} checked={plano === p.codigo} disabled={!p.disponivel} onChange={() => setPlano(p.codigo)} />
              {p.tag && p.disponivel && <span className="tag">{p.tag}</span>}
              {!p.disponivel && <span className="tag" style={{ background: "var(--surface-2)", color: "var(--muted)" }}>Em breve</span>}
              <b>{p.nome}</b>
              <span className="price">
                {p.numParcelas}× {brl(p.valorParcela)}
              </span>
              <small className="muted">Total {brl(p.valorTotal)}</small>
              <span className="muted" style={{ fontSize: 13 }}>
                {p.disponivel ? p.descricao : p.motivoIndisponivel}
              </span>
            </label>
          ))}
        </div>
        {errors.codigoPlano && <span className="err">{errors.codigoPlano}</span>}
      </section>
      <section className="card panel">
        <h2>Cupom de desconto</h2>
        <div className="voucher">
          <input
            className={`input ${errors.voucher ? "invalid" : ""}`}
            placeholder="Código do cupom"
            aria-label="Código do cupom"
            value={cupom}
            onChange={(e) => {
              setCupom(e.target.value);
              setCupomMsg(null);
            }}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), aplicarCupom())}
          />
          <button className="btn btn-ghost" type="button" onClick={aplicarCupom} disabled={validando || !cupom.trim()}>
            {validando ? <Spin /> : "Aplicar"}
          </button>
        </div>
        <p style={{ fontSize: 13 }} aria-live="polite">
          {cupomMsg && <span style={{ color: cupomMsg.ok ? "var(--ok)" : "var(--bad)" }}>{cupomMsg.msg}</span>}
          {errors.voucher && <span className="err">{errors.voucher}</span>}
        </p>
      </section>
      <div className="foot">
        <button className="btn btn-ghost" type="button" onClick={() => ir("documentos")}>
          Voltar
        </button>
        <button className="btn btn-primary" type="button" onClick={confirmar} disabled={enviando}>
          {enviando ? <><Spin /> Confirmando</> : "Confirmar pagamento"}
        </button>
      </div>
    </>
  );
}
