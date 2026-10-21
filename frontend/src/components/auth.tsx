import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, setUnauthorizedHandler } from "../api/client";
import type { Pessoa } from "../api/types";
import { Spin } from "./ui";

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
    setUnauthorizedHandler(() => setPessoa(null));
    api.me().then(setPessoa).catch(() => setPessoa(null)).finally(() => setCarregando(false));
  }, []);

  const entrar = useCallback(async (login: string, senha: string) => {
    setPessoa(await api.login(login, senha));
  }, []);
  const sair = useCallback(async () => {
    await api.logout().catch(() => {});
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
