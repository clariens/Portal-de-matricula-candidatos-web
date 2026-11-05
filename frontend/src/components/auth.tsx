import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, setUnauthorizedHandler, setWriteHandler } from "../api/client";
import type { Pessoa } from "../api/types";
import { Spin } from "./ui";
import { definirDono, limparAnexos } from "../lib/anexosLocais";
import { cacheTelas, invalidarApos } from "../lib/cacheTelas";

interface AuthState {
  pessoa: Pessoa | null;
  carregando: boolean;
  entrar: (login: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
}
const Ctx = createContext<AuthState>(null!);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [pessoa, setPessoa] = useState<Pessoa | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      cacheTelas.limpar();
      setPessoa(null);
    });
    setWriteHandler(invalidarApos);
    api.me()
      .catch(() => null)
      .then((p) => {
        // documentos guardados só valem para quem está logado: sem sessão, ou vencidos, saem ao abrir o portal
        definirDono(p?.codPessoa ?? null).catch(() => {});
        setPessoa(p);
      })
      .finally(() => setCarregando(false));
  }, []);

  const entrar = useCallback(async (login: string, senha: string) => {
    const p = await api.login(login, senha);
    cacheTelas.limpar(); // nada de outra conta fica para trás
    await definirDono(p.codPessoa).catch(() => {}); // documentos de outra pessoa neste navegador são apagados
    setPessoa(p);
  }, []);
  const sair = useCallback(async () => {
    await api.logout().catch(() => {});
    await limparAnexos(); // documentos pessoais não ficam guardados no computador depois de sair
    cacheTelas.limpar();
    try {
      sessionStorage.clear(); // forma e valor da cobrança guardados para a conclusão
    } catch {
      /* sem sessionStorage: nada a limpar */
    }
    setPessoa(null);
  }, []);

  return <Ctx.Provider value={{ pessoa, carregando, entrar, sair }}>{children}</Ctx.Provider>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { pessoa, carregando } = useAuth();
  const loc = useLocation();
  if (carregando)
    return (
      <div className="center">
        <Spin />
      </div>
    );
  if (!pessoa) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}
