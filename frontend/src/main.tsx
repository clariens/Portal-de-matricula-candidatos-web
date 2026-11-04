import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./components/auth";
import { Shell } from "./components/Shell";
import { ToastProvider } from "./components/ui";
import { ContratoInscricao } from "./pages/ContratoInscricao";
import { DocumentosIngresso } from "./pages/DocumentosIngresso";
import { Historico } from "./pages/Historico";
import { Login } from "./pages/Login";
import { Wizard } from "./pages/wizard/Wizard";
import "./styles/app.css";

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { path: "/login", element: <Login /> },
      { path: "/inscricoes", element: <RequireAuth><Historico /></RequireAuth> },
      { path: "/inscricoes/:id/contrato", element: <RequireAuth><ContratoInscricao /></RequireAuth> },
      { path: "/inscricoes/:id/documentos", element: <RequireAuth><DocumentosIngresso /></RequireAuth> },
      { path: "/matricula/:id/:etapa?", element: <RequireAuth><Wizard /></RequireAuth> },
      { path: "*", element: <Navigate to="/inscricoes" replace /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ToastProvider>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ToastProvider>
  </StrictMode>,
);
