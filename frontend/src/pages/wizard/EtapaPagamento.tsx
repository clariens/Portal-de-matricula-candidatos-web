import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { OpcoesPagamento, PagamentoIn, Plano } from "../../api/types";
import { ENDERECO_VAZIO, EnderecoFields, validarEndereco, type EnderecoForm } from "../../components/EnderecoFields";
import { Alert, Field, Select, Spin, useToast } from "../../components/ui";
import { brl, cnpjValido, cpfValido, dataValida, digits, emailValido } from "../../lib/format";
import { ESTADOS_CIVIS, SEXOS } from "./EtapaDados";
import { useWizard } from "./Wizard";

type TipoResp = PagamentoIn["tipoResp"];
interface RespForm {
  nome: string;
  documento: string;
  dataNascimento: string;
  sexo: string;
  estadoCivil: string;
  rg: string;
  email: string;
  celular: string;
  telefone: string;
  inscricaoEstadual: string;
  inscricaoMunicipal: string;
  endereco: EnderecoForm;
}
const RESP_VAZIO: RespForm = {
  nome: "", documento: "", dataNascimento: "", sexo: "", estadoCivil: "", rg: "", email: "", celular: "", telefone: "",
  inscricaoEstadual: "", inscricaoMunicipal: "", endereco: ENDERECO_VAZIO,
};

const TIPOS: [TipoResp, string, string][] = [
  ["Pessoa", "Eu mesmo(a)", "O contrato sai no seu nome"],
  ["OutraPessoa", "Outra pessoa", "Pai, mãe ou outro responsável"],
  ["Empresa", "Empresa", "Pagamento por CNPJ"],
];

export const COBRANCA_KEY = (id: string) => `cobranca:${id}`;
const vazio = (v: string) => v.trim() || null;

export function EtapaPagamento() {
  const { insc, ir, recarregar } = useWizard();
  const toast = useToast();
  const [op, setOp] = useState<OpcoesPagamento | null>(null);
  const [fechada, setFechada] = useState(false);
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
  const [simulado, setSimulado] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api
      .opcoesPagamento(insc.codCandidato)
      .then((o) => {
        setOp(o);
        setPlanos(o.planos);
        if (o.cupomAplicado) {
          setCupom(o.cupomAplicado);
          setCupomAplicado(o.cupomAplicado);
        }
      })
      .catch((e) => {
        // O Processo Seletivo só abre o pagamento depois de confirmar os dados na mesma sessão
        setFechada(e instanceof ApiError && e.status === 409);
        setErro(e instanceof ApiError ? e.message : "Erro ao carregar as opções de pagamento.");
      });
  }, [insc.codCandidato]);

  const setR = <K extends keyof RespForm>(k: K) => (v: RespForm[K]) => setResp((r) => ({ ...r, [k]: v }));

  async function aplicarCupom() {
    const c = cupom.trim();
    if (!c) return;
    setValidando(true);
    try {
      const r = await api.validarCupom(insc.codCandidato, c);
      setCupomMsg({ ok: r.valido, msg: r.mensagem });
      setCupomAplicado(r.valido ? c.toUpperCase() : null);
      if (r.valido && r.planos) setPlanos(r.planos);
    } catch (e) {
      setCupomMsg({ ok: false, msg: e instanceof ApiError ? e.message : "Não foi possível validar o cupom." });
    } finally {
      setValidando(false);
    }
  }

  function validar() {
    const er: Record<string, string> = {};
    if (!plano) er.codigoPlano = "Escolha a forma de pagamento.";
    if (tipo === "Pessoa") return er;
    if (resp.nome.trim().length < 3) er["responsavel.nome"] = "Campo obrigatório.";
    if (tipo === "Empresa") {
      if (!cnpjValido(resp.documento)) er["responsavel.documento"] = "CNPJ inválido.";
    } else {
      if (!cpfValido(resp.documento)) er["responsavel.documento"] = "CPF do responsável inválido.";
      if (!dataValida(resp.dataNascimento)) er["responsavel.dataNascimento"] = "Use o formato dd/mm/aaaa.";
      if (!resp.sexo) er["responsavel.sexo"] = "Selecione o sexo.";
      if (!resp.estadoCivil) er["responsavel.estadoCivil"] = "Selecione o estado civil.";
      if (!emailValido(resp.email)) er["responsavel.email"] = "E-mail inválido.";
      if (digits(resp.celular).length !== 11) er["responsavel.celular"] = "Informe DDD + 9 dígitos.";
      if (![10, 11].includes(digits(resp.telefone).length)) er["responsavel.telefone"] = "Telefone com DDD.";
    }
    Object.assign(er, validarEndereco(resp.endereco, "responsavel.endereco"));
    return er;
  }

  function responsavel(): PagamentoIn["responsavel"] {
    if (tipo === "Pessoa") return null;
    const endereco = { ...resp.endereco, complemento: vazio(resp.endereco.complemento ?? "") };
    if (tipo === "Empresa")
      return {
        nome: resp.nome, documento: resp.documento, endereco,
        inscricaoEstadual: vazio(resp.inscricaoEstadual), inscricaoMunicipal: vazio(resp.inscricaoMunicipal),
      };
    return {
      nome: resp.nome, documento: resp.documento, dataNascimento: resp.dataNascimento, endereco,
      sexo: resp.sexo as "M" | "F" | "O", estadoCivil: resp.estadoCivil, rg: vazio(resp.rg),
      email: resp.email, celular: resp.celular, telefone: resp.telefone,
    };
  }

  async function confirmar() {
    const er = validar();
    setErrors(er);
    setErro(null);
    setSimulado(null);
    if (Object.keys(er).length) {
      toast("Revise os campos destacados.");
      requestAnimationFrame(() => (document.querySelector(".input.invalid") as HTMLElement | null)?.focus());
      return;
    }
    setEnviando(true);
    try {
      const r = await api.efetivarPagamento(insc.codCandidato, {
        tipoResp: tipo, codigoPlano: plano, voucher: cupomAplicado, responsavel: responsavel(),
      });
      if (r.simulado) {
        // Ambiente de desenvolvimento: nada foi gravado no Lyceum, então o candidato continua nesta etapa
        setSimulado(r.mensagem ?? "Pagamento simulado.");
        return;
      }
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
        toast(e.message);
      } else setErro("Não foi possível confirmar o pagamento.");
    } finally {
      setEnviando(false);
    }
  }

  if (!op)
    return erro ? (
      <>
        <Alert>{erro}</Alert>
        {fechada && (
          <div className="foot">
            <button className="btn btn-primary" type="button" onClick={() => ir("dados")}>
              Revisar meus dados
            </button>
          </div>
        )}
      </>
    ) : (
      <div className="skel" style={{ minHeight: 320 }} />
    );

  const outra = tipo === "OutraPessoa";
  return (
    <>
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
              <Field id="r-nome" label={outra ? "Nome do responsável" : "Razão social"} value={resp.nome} onValue={setR("nome")} cls="c8" error={errors["responsavel.nome"]} />
              <Field id="r-doc" label={outra ? "CPF do responsável" : "CNPJ"} value={resp.documento} onValue={setR("documento")} cls="c4" mask={outra ? "cpf" : "cnpj"} inputMode="numeric" error={errors["responsavel.documento"]} />
              {outra ? (
                <>
                  <Field id="r-nasc" label="Data de nascimento" value={resp.dataNascimento} onValue={setR("dataNascimento")} cls="c3" mask="date" inputMode="numeric" placeholder="dd/mm/aaaa" error={errors["responsavel.dataNascimento"]} />
                  <Select id="r-sexo" label="Sexo" value={resp.sexo} onValue={setR("sexo")} options={[["", "Selecione"], ...SEXOS]} error={errors["responsavel.sexo"]} />
                  <Select id="r-civil" label="Estado civil" value={resp.estadoCivil} onValue={setR("estadoCivil")} options={[["", "Selecione"], ...ESTADOS_CIVIS.map((e): [string, string] => [e, e])]} error={errors["responsavel.estadoCivil"]} />
                  <Field id="r-rg" label="RG (opcional)" value={resp.rg} onValue={setR("rg")} cls="c3" error={errors["responsavel.rg"]} />
                  <Field id="r-email" label="E-mail" type="email" value={resp.email} onValue={setR("email")} cls="c6" error={errors["responsavel.email"]} />
                  <Field id="r-cel" label="Celular (WhatsApp)" value={resp.celular} onValue={setR("celular")} cls="c3" mask="phone" inputMode="tel" error={errors["responsavel.celular"]} />
                  <Field id="r-tel" label="Telefone" value={resp.telefone} onValue={setR("telefone")} cls="c3" mask="phone" inputMode="tel" error={errors["responsavel.telefone"]} />
                </>
              ) : (
                <>
                  <Field id="r-ie" label="Inscrição estadual (opcional)" value={resp.inscricaoEstadual} onValue={setR("inscricaoEstadual")} cls="c6" error={errors["responsavel.inscricaoEstadual"]} />
                  <Field id="r-im" label="Inscrição municipal (opcional)" value={resp.inscricaoMunicipal} onValue={setR("inscricaoMunicipal")} cls="c6" error={errors["responsavel.inscricaoMunicipal"]} />
                </>
              )}
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
              {/* numParcelas é o nº de mensalidades do plano do curso (igual em todas as formas), não parcelamento */}
              {p.valorParcela != null && (
                <span className="price">
                  {brl(p.valorParcela)}
                  <small className="muted">/mês</small>
                </span>
              )}
              <small className="muted">
                {p.numParcelas} mensalidades no semestre{p.valorTotal != null ? ` · total ${brl(p.valorTotal)}` : ""}
              </small>
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
              setCupomAplicado(null);
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
      {erro && <Alert>{erro}</Alert>}
      {simulado && <Alert tone="info">{simulado}</Alert>}
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
