import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../components/auth";
import { Alert, Field, Spin, useToast } from "../components/ui";

const ICONES = [
  { tone: "", d: <path d="M3 12h4l2-5 4 10 2-5h6" /> },
  { tone: "v", d: <><path d="M6 3v6a4 4 0 0 0 8 0V3" /><path d="M10 13v3a5 5 0 0 0 10 0v-2" /><circle cx="20" cy="12" r="2" /></> },
  { tone: "l", d: <path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" /> },
  { tone: "", d: <><path d="M7 3c0 6 10 6 10 12s-10 6-10 6M17 3c0 6-10 6-10 12" /><path d="M8 7h8M8 17h8" /></> },
];

export function Login() {
  const { pessoa, entrar } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const toast = useToast();
  const [login, setLogin] = useState(import.meta.env.DEV ? "123.456.789-09" : "");
  const [senha, setSenha] = useState(import.meta.env.DEV ? "demonstracao" : "");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (pessoa) return <Navigate to="/inscricoes" replace />;

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
        <svg className="ecg" viewBox="0 0 1000 70" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 40 H260 l14 -6 l12 6 H330 l10 18 l16 -56 l16 60 l12 -22 H470 l18 -8 l16 8 H700 l10 18 l16 -56 l16 60 l12 -22 H1000" />
        </svg>
        <ol>
          <li><b>1</b>Dados pessoais</li>
          <li><b>2</b>Documentos com leitura automática</li>
          <li><b>3</b>Pagamento</li>
          <li><b>4</b>Contrato e disciplinas</li>
        </ol>
        <div className="brands">
          <span>ZARNS</span>
          <span>UNESUL BAHIA</span>
          <span>IMEPAC</span>
        </div>
      </div>
      <form className="card login-card" onSubmit={submit} noValidate>
        <div>
          <span className="eyebrow">Área do candidato</span>
          <h2>Entrar</h2>
        </div>
        {import.meta.env.DEV && (
          <p className="demo-note">Desenvolvimento: no modo mock, use CPF 123.456.789-09 e senha "demonstracao".</p>
        )}
        {erro && <Alert>{erro}</Alert>}
        <div className="grid">
          <Field id="l-user" label="E-mail ou CPF" value={login} onValue={setLogin} cls="" autoComplete="username" />
          <Field id="l-pass" label="Senha" value={senha} onValue={setSenha} cls="" type="password" autoComplete="current-password" />
        </div>
        <button className="btn btn-primary" type="submit" disabled={enviando}>
          {enviando ? <><Spin /> Entrando</> : "Entrar"}
        </button>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, flexWrap: "wrap", gap: 8 }}>
          <button type="button" className="btn-link" onClick={() => toast("Use a recuperação de senha do portal do Processo Seletivo.")}>
            Esqueci minha senha
          </button>
        </div>
      </form>
    </section>
  );
}
