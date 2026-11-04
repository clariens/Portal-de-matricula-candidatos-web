import type { Matricula } from "../api/types";
import { Chip } from "./ui";

export const CONTRATO: Record<string, [string, string]> = {
  nao_enviado: ["neutral", "Contrato em preparação"],
  aguardando_assinatura: ["warn", "Aguardando assinatura"],
  assinado: ["ok", "Contrato assinado"],
};

/** Como assinar o contrato: as instruções do Processo Seletivo (/r/contrato) ou, sem elas, os passos da Clicksign. */
export function AssinaturaContrato({ contrato }: { contrato: Matricula["contrato"] }) {
  const [tom, rotulo] = CONTRATO[contrato.status];
  return (
    <section className="card panel" style={{ marginTop: 16 }}>
      <div className="panel-head">
        <h2>Assine o contrato</h2>
        <Chip tone={tom}>{rotulo}</Chip>
      </div>
      {contrato.instrucoes?.length ? (
        <InstrucoesContrato linhas={contrato.instrucoes} />
      ) : (
        <ol className="timeline">
          <li>
            <div>
              <b>Abra a mensagem da Clicksign no WhatsApp</b>
              <p className="muted">Enviada para {contrato.destinatario ?? "o celular do responsável financeiro"}.</p>
            </div>
          </li>
          <li>
            <div>
              <b>Confirme CPF e data de nascimento</b>
              <p className="muted">São os dados do responsável financeiro.</p>
            </div>
          </li>
          <li>
            <div>
              <b>Digite o token recebido</b>
              <p className="muted">Uma cópia assinada chega no seu e-mail.</p>
            </div>
          </li>
        </ol>
      )}
    </section>
  );
}

/** Instruções de assinatura do Processo Seletivo (/r/contrato): "1º Passo:" vira um passo da linha do tempo. */
function InstrucoesContrato({ linhas }: { linhas: string[] }) {
  const intro: string[] = [];
  const passos: { titulo: string; texto: string[] }[] = [];
  const fim: string[] = [];
  for (const l of linhas) {
    if (/^\d+\s*º?\s*passo\s*:?$/i.test(l)) passos.push({ titulo: l.replace(/:$/, ""), texto: [] });
    else if (!passos.length) intro.push(l);
    else if (passos[passos.length - 1].texto.length === 0) passos[passos.length - 1].texto.push(l);
    else fim.push(l);
  }
  return (
    <div className="contrato-instrucoes">
      {intro.map((l) => <p key={l}>{l}</p>)}
      {passos.length > 0 && (
        <ol className="timeline">
          {passos.map((s) => (
            <li key={s.titulo}>
              <div>
                <b>{s.titulo}</b>
                {s.texto.map((l) => <p key={l} className="muted">{l}</p>)}
              </div>
            </li>
          ))}
        </ol>
      )}
      {fim.map((l) => <p key={l} className="muted">{l}</p>)}
    </div>
  );
}
