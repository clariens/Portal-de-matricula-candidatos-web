import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { api, apiLog } from "../api/client";
import type { Cabecalho } from "../api/types";
import logo from "../assets/clariens-educacao.png";
import { useAuth } from "./auth";

export function Shell() {
  const { pessoa, sair } = useAuth();
  const nav = useNavigate();
  const [cab, setCab] = useState<Cabecalho | null>(null);
  useEffect(() => {
    api.cabecalho().then(setCab).catch(() => setCab(null)); // sem o menu, o portal segue funcionando
  }, []);
  return (
    <>
      <header className="topbar">
        <Link className="brand-logo" to="/" aria-label="Clariens Educação: início">
          <img src={logo} alt="Clariens Educação" width={87} height={34} />
        </Link>
        <AreasDeInteresse cab={cab} />
        {!pessoa && (
          <nav aria-label="Conta">
            <a className="btn-cadastro" href={cab?.cadastroUrl} target="_blank" rel="noopener noreferrer"
               aria-disabled={!cab || undefined}>
              Cadastre-se
            </a>
          </nav>
        )}
        {pessoa && (
          <nav aria-label="Principal">
            <button type="button" onClick={() => nav("/inscricoes")}>
              Minhas inscrições
            </button>
            <button
              type="button"
              onClick={async () => {
                await sair();
                nav("/login");
              }}
            >
              Sair
            </button>
          </nav>
        )}
      </header>
      <main className="wrap" id="conteudo">
        <Outlet />
      </main>
      {import.meta.env.DEV && <ApiInspector />}
    </>
  );
}

/** Painel de chamadas ao BFF, visível só em desenvolvimento (herdado do protótipo). */
function ApiInspector() {
  const [logs, setLogs] = useState(() => apiLog.list().slice());
  const [aberto, setAberto] = useState(false);
  useEffect(() => apiLog.subscribe(() => setLogs(apiLog.list().slice())), []);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, []);
  return (
    <>
      <button className="api-fab" type="button" onClick={() => setAberto(true)} aria-controls="drawer">
        Chamadas de API <span className="count">{logs.length}</span>
      </button>
      <aside className="drawer" id="drawer" hidden={!aberto} aria-label="Chamadas de API">
        <header>
          <div>
            <h3>Chamadas de API</h3>
            <p className="muted" style={{ fontSize: 12 }}>
              BFF /api/v1 · modo desenvolvimento
            </p>
          </div>
          <button className="btn btn-ghost" type="button" onClick={() => setAberto(false)}>
            Fechar
          </button>
        </header>
        <div className="list">
          {logs.length === 0 && <p className="muted">As chamadas aparecem aqui conforme você navega.</p>}
          {logs.map((l, i) => (
            <div className="call" key={i}>
              <div className="h">
                <span className={`m ${l.method === "GET" ? "get" : ""}`}>{l.method}</span>
                <span className="u">{l.path}</span>
                <span className="muted" style={{ marginLeft: "auto" }}>
                  {l.status} · {l.ms} ms · {l.t}
                </span>
              </div>
              {l.body !== undefined && <pre className="p">{JSON.stringify(l.body, null, 2)}</pre>}
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}

/** "Área de interesse": os subgrupos do Processo Seletivo (abrem no portal do Processo Seletivo).
 *  O botão aparece desde o início (carregando) para o cabeçalho não "pular" quando a lista chega. */
function AreasDeInteresse({ cab }: { cab: Cabecalho | null }) {
  const [aberto, setAberto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setAberto(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto]);
  return (
    <div className="areas" ref={ref}>
      <button type="button" className="areas-botao" aria-expanded={aberto} aria-controls="menu-areas"
              aria-busy={!cab || undefined} disabled={!cab} onClick={() => setAberto((a) => !a)}>
        Área de interesse <span aria-hidden="true">▾</span>
      </button>
      {aberto && cab && (
        <div className="areas-menu" id="menu-areas">
          {cab.areas.map((a) => (
            <div key={a.nome}>
              <span className="areas-grupo">{a.nome}</span>
              <ul>
                {a.itens.map((i) => (
                  <li key={i.url}>
                    <a href={i.url} target="_blank" rel="noopener noreferrer" onClick={() => setAberto(false)}>
                      {i.nome}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
