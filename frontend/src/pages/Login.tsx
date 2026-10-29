import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import logo from "../assets/clariens-educacao.png";
import { useAuth } from "../components/auth";
import { Alert, Field, Spin } from "../components/ui";

const ICONES = [
  { tone: "", d: <path d="M3 12h4l2-5 4 10 2-5h6" /> },
  { tone: "v", d: <><path d="M6 3v6a4 4 0 0 0 8 0V3" /><path d="M10 13v3a5 5 0 0 0 10 0v-2" /><circle cx="20" cy="12" r="2" /></> },
  { tone: "l", d: <path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" /> },
  { tone: "", d: <><path d="M7 3c0 6 10 6 10 12s-10 6-10 6M17 3c0 6-10 6-10 12" /><path d="M8 7h8M8 17h8" /></> },
];

const ECG = "M0 40 H260 l14 -6 l12 6 H330 l10 18 l16 -56 l16 60 l12 -22 H470 l18 -8 l16 8 H700 l10 18 l16 -56 l16 60 l12 -22 H975";

export function Login() {
  const { pessoa, entrar } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [modo, setModo] = useState<"entrar" | "recuperar">("entrar");
  const [recuperado, setRecuperado] = useState<string | null>(null);
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // o fundo do antigo card de apresentação vira o fundo da tela inteira (só no login)
  useEffect(() => {
    document.body.classList.add("tela-login");
    return () => document.body.classList.remove("tela-login");
  }, []);

  if (pessoa) return <Navigate to="/inscricoes" replace />;

  function trocarModo(m: "entrar" | "recuperar") {
    setModo(m);
    setErro(null);
    setRecuperado(null);
  }

  /** Esqueci minha senha: o Processo Seletivo envia as instruções ao e-mail cadastrado. */
  async function recuperar(e: FormEvent) {
    e.preventDefault();
    if (login.trim().length < 3) {
      setErro("Informe o e-mail, CPF, RG ou passaporte cadastrado.");
      return;
    }
    setEnviando(true);
    setErro(null);
    try {
      setRecuperado((await api.recuperarSenha(login.trim())).mensagem);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível enviar agora. Tente novamente.");
    } finally {
      setEnviando(false);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!login.trim() || !senha) {
      setErro("Informe e-mail ou CPF e a senha.");
      return;
    }
    setEnviando(true);
    setErro(null);
    try {
      await entrar(login, senha);
      nav((loc.state as { from?: string } | null)?.from || "/inscricoes", { replace: true });
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="login">
      <div className="hero">
        <div className="hexes" aria-hidden="true">
          {ICONES.map((i, k) => (
            <span key={k} className={`hx ${i.tone}`}>
              <svg viewBox="0 0 24 24">{i.d}</svg>
            </span>
          ))}
        </div>
        <span className="eyebrow" style={{ color: "var(--on-deep-muted)" }}>
          Educação médica · Processo Seletivo
        </span>
        <h1>
          Seu jaleco começa na <em>matrícula</em>.
        </h1>
        <p>
          Da convocação ao primeiro dia de aula em quatro passos: confira seus dados, envie os documentos pelo celular,
          escolha como pagar e assine o contrato.
        </p>
        {/* monitor cardíaco: a linha é desenhada, um sinal percorre o traçado e o coração bate no fim */}
        <div className="ecg" aria-hidden="true">
          <svg viewBox="0 0 1000 70" preserveAspectRatio="none">
            <path className="ecg-linha" pathLength={1000} d={ECG} />
            <path className="ecg-sinal" pathLength={1000} d={ECG} />
          </svg>
          <span className="ecg-coracao">
            <svg viewBox="0 0 24 24"><path d="M12 21s-7.5-4.6-9.6-9.2C.9 8.4 2.9 4.5 6.6 4.5c2.2 0 3.6 1.2 4.4 2.6.8-1.4 2.2-2.6 4.4-2.6 3.7 0 5.7 3.9 4.2 7.3C19.5 16.4 12 21 12 21z" /></svg>
          </span>
        </div>
        <div className="brands">
          <span>ZARNS</span>
          <span>UNESUL BAHIA</span>
          <span>IMEPAC</span>
        </div>
      </div>
      {modo === "entrar" ? (
        <form className="card login-card" onSubmit={submit} noValidate>
          <img className="login-logo" src={logo} alt="Clariens Educação" width={204} height={80} />
          <h2>Entrar</h2>
          {erro && <Alert>{erro}</Alert>}
          <div className="grid">
            <Field id="l-user" label="E-mail ou CPF" value={login} onValue={setLogin} cls="" autoComplete="username" />
            <Field id="l-pass" label="Senha" value={senha} onValue={setSenha} cls="" type="password" autoComplete="current-password" />
          </div>
          <button className="btn btn-primary" type="submit" disabled={enviando}>
            {enviando ? <><Spin /> Entrando</> : "Entrar"}
          </button>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, flexWrap: "wrap", gap: 8 }}>
            <button type="button" className="btn-link" onClick={() => trocarModo("recuperar")}>
              Esqueci minha senha
            </button>
          </div>
        </form>
      ) : (
        <form className="card login-card" onSubmit={recuperar} noValidate>
          <img className="login-logo" src={logo} alt="Clariens Educação" width={204} height={80} />
          <h2>Recuperar senha</h2>
          {recuperado ? (
            <Alert tone="ok">{recuperado}</Alert>
          ) : (
            <>
              <p className="muted" style={{ fontSize: 14, margin: 0 }}>
                Informe o e-mail, CPF, RG ou passaporte do seu cadastro. Enviaremos as instruções para o e-mail cadastrado.
              </p>
              {erro && <Alert>{erro}</Alert>}
              <Field id="r-login" label="E-mail, CPF, RG ou passaporte" value={login} onValue={setLogin} cls="" autoComplete="username" />
              <button className="btn btn-primary" type="submit" disabled={enviando}>
                {enviando ? <><Spin /> Enviando</> : "Enviar instruções"}
              </button>
            </>
          )}
          <div style={{ fontSize: 14 }}>
            <button type="button" className="btn-link" onClick={() => trocarModo("entrar")}>
              Voltar para entrar
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
