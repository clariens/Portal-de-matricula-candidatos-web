import { useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { apiLog } from "../api/client";
import { useAuth } from "./auth";

export function Shell() {
  const { pessoa, sair } = useAuth();
  const nav = useNavigate();
  return (
    <>
      <header className="topbar">
        <div className="brand">
          <b>Clariens</b>
          <span>Educação</span>
          <span className="area">· Medicina</span>
        </div>
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
