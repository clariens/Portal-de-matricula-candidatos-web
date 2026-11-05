import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { MeusDados as Dados } from "../api/types";
import { EnderecoFields, validarEndereco, type EnderecoForm } from "../components/EnderecoFields";
import { Alert, Field, Spin, useToast } from "../components/ui";
import { digits, emailValido, maskPhone } from "../lib/format";

interface Form {
  email: string;
  celular: string;
  telefone: string;
  endereco: EnderecoForm;
}

function paraForm(d: Dados): Form {
  const e = d.endereco;
  return {
    email: d.email, celular: maskPhone(d.celular), telefone: maskPhone(d.telefone ?? ""),
    endereco: {
      pais: e.pais ?? "BRASIL", cep: e.cep, uf: e.uf, municipio: e.municipio, municipioCodigo: e.municipioCodigo,
      endereco: e.endereco, numero: e.numero, complemento: e.complemento ?? "", bairro: e.bairro,
    },
  };
}

function validar(f: Form) {
  const er: Record<string, string> = {};
  if (!emailValido(f.email)) er.email = "E-mail inválido.";
  if (digits(f.celular).length !== 11) er.celular = "Informe DDD + 9 dígitos.";
  if (f.telefone && ![0, 10, 11].includes(digits(f.telefone).length)) er.telefone = "Telefone com DDD.";
  return { ...er, ...validarEndereco(f.endereco) };
}

const focarPrimeiroErro = () =>
  requestAnimationFrame(() => (document.querySelector(".input.invalid") as HTMLElement | null)?.focus());

/** Meus dados (como "Meus Dados" do Processo Seletivo): contato e endereço, e troca de senha. Nome, CPF e
 *  nascimento não mudam aqui. */
export function MeusDados() {
  const nav = useNavigate();
  const toast = useToast();
  const [f, setF] = useState<Form | null>(null);
  const [erroCarga, setErroCarga] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    api.meusDados().then((d) => setF(paraForm(d)))
      .catch((e) => setErroCarga(e instanceof ApiError ? e.message : "Não foi possível carregar seus dados."));
  }, []);

  const set = <K extends keyof Form>(k: K) => (v: Form[K]) => setF((x) => (x ? { ...x, [k]: v } : x));

  async function salvar(e: FormEvent) {
    e.preventDefault();
    if (!f) return;
    const er = validar(f);
    setErrors(er);
    setErroGeral(null);
    if (Object.keys(er).length) {
      toast("Revise os campos destacados.");
      focarPrimeiroErro();
      return;
    }
    setSalvando(true);
    try {
      const d = await api.salvarMeusDados({
        email: f.email, celular: f.celular, telefone: f.telefone || null,
        endereco: { ...f.endereco, complemento: f.endereco.complemento || null },
      });
      setF(paraForm(d));
      toast("Dados salvos.");
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.campos);
        setErroGeral(err.message);
        focarPrimeiroErro();
      } else setErroGeral("Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <span className="eyebrow">Sua conta</span>
          <h1>Meus dados</h1>
        </div>
      </div>
      {erroCarga && <Alert>{erroCarga}</Alert>}
      {!erroCarga && !f && <div className="skel" style={{ minHeight: 320 }} />}
      {f && (
        <form onSubmit={salvar} noValidate>
          {erroGeral && <Alert>{erroGeral}</Alert>}
          <fieldset disabled={salvando} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
            <section className="card panel">
              <h2>Dados de contato</h2>
              <p className="muted" style={{ marginTop: 0 }}>Nome, CPF e data de nascimento são alterados pela secretaria.</p>
              <div className="grid g12">
                <Field id="email" label="E-mail" type="email" value={f.email} onValue={set("email")} error={errors.email} autoComplete="email" />
                <Field id="celular" label="Celular (WhatsApp)" value={f.celular} onValue={set("celular")} cls="c3" mask="phone" inputMode="tel" error={errors.celular} autoComplete="tel" />
                <Field id="telefone" label="Telefone fixo" value={f.telefone} onValue={set("telefone")} cls="c3" mask="phone" inputMode="tel" hint="Opcional" error={errors.telefone} />
              </div>
            </section>
            <section className="card panel">
              <h2>Endereço</h2>
              <EnderecoFields value={f.endereco} onChange={set("endereco")} errors={errors} />
            </section>
          </fieldset>
          <div className="foot">
            <button className="btn btn-ghost" type="button" onClick={() => nav("/inscricoes")}>
              Voltar para minhas inscrições
            </button>
            <button className="btn btn-primary" type="submit" disabled={salvando}>
              {salvando ? <><Spin /> Salvando</> : "Salvar dados"}
            </button>
          </div>
        </form>
      )}
      <AlterarSenha />
    </>
  );
}

function AlterarSenha() {
  const toast = useToast();
  const vazio = { senhaAtual: "", novaSenha: "", confirmacao: "" };
  const [s, setS] = useState(vazio);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const set = (k: keyof typeof vazio) => (v: string) => setS((x) => ({ ...x, [k]: v }));

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const er: Record<string, string> = {};
    if (!s.senhaAtual) er.senhaAtual = "Informe a senha atual.";
    if (!s.novaSenha) er.novaSenha = "Informe a nova senha.";
    else if (s.novaSenha.length > 40) er.novaSenha = "Máximo de 40 caracteres.";
    else if (s.novaSenha === s.senhaAtual) er.novaSenha = "A nova senha deve ser diferente da atual.";
    if (s.confirmacao !== s.novaSenha) er.confirmacao = "As senhas não conferem.";
    setErrors(er);
    setErro(null);
    setOk(null);
    if (Object.keys(er).length) return focarPrimeiroErro();
    setEnviando(true);
    try {
      const r = await api.alterarSenha(s);
      setS(vazio);
      setOk(r.mensagem);
      toast(r.mensagem);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.campos);
        setErro(err.message);
      } else setErro("Não foi possível alterar a senha.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate>
      <section className="card panel" style={{ marginTop: 16 }}>
        <h2>Alterar senha</h2>
        {erro && <Alert>{erro}</Alert>}
        {ok && <Alert tone="ok">{ok}</Alert>}
        <fieldset disabled={enviando} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
          <div className="grid g12">
            <Field id="senhaAtual" label="Senha atual" type="password" value={s.senhaAtual} onValue={set("senhaAtual")} cls="c4" autoComplete="current-password" error={errors.senhaAtual} />
            <Field id="novaSenha" label="Nova senha" type="password" value={s.novaSenha} onValue={set("novaSenha")} cls="c4" autoComplete="new-password" maxLength={40} error={errors.novaSenha} />
            <Field id="confirmacao" label="Confirme a nova senha" type="password" value={s.confirmacao} onValue={set("confirmacao")} cls="c4" autoComplete="new-password" maxLength={40} error={errors.confirmacao} />
          </div>
        </fieldset>
        <div className="acoes-direita">
          <button className="btn btn-primary" type="submit" disabled={enviando}>
            {enviando ? <><Spin /> Alterando</> : "Alterar senha"}
          </button>
        </div>
      </section>
    </form>
  );
}
