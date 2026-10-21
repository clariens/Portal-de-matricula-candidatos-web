import { useRef, useState } from "react";
import { api } from "../api/client";
import { digits } from "../lib/format";
import { Field, Select, Spin } from "./ui";

export interface EnderecoForm {
  pais: string;
  cep: string;
  uf: string;
  municipio: string;
  municipioCodigo?: string | null;
  endereco: string;
  numero: string;
  complemento: string;
  bairro: string;
}
export const ENDERECO_VAZIO: EnderecoForm = {
  pais: "BRASIL", cep: "", uf: "", municipio: "", municipioCodigo: null, endereco: "", numero: "", complemento: "", bairro: "",
};
export const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

export function validarEndereco(e: EnderecoForm, prefixo = "endereco"): Record<string, string> {
  const er: Record<string, string> = {};
  if (digits(e.cep).length !== 8) er[`${prefixo}.cep`] = "CEP com 8 dígitos.";
  if (!e.uf) er[`${prefixo}.uf`] = "Selecione a UF.";
  (["municipio", "endereco", "numero", "bairro"] as const).forEach((k) => {
    if (!String(e[k]).trim()) er[`${prefixo}.${k}`] = "Campo obrigatório.";
  });
  return er;
}

export function EnderecoFields({
  value, onChange, errors, prefixo = "endereco", disabled,
}: {
  value: EnderecoForm;
  onChange: (e: EnderecoForm) => void;
  errors: Record<string, string>;
  prefixo?: string;
  disabled?: boolean;
}) {
  const [cepSt, setCepSt] = useState<"idle" | "busca" | "ok" | "nao" | "invalido">("idle");
  const numeroRef = useRef<HTMLDivElement>(null);
  // CEP cujos dados já estão nos campos (o que veio do Lyceum ou a última busca): sair do campo sem mudar não busca
  const cepConhecido = useRef(digits(value.cep));
  const busca = useRef(0);
  const set = (k: keyof EnderecoForm) => (v: string) => onChange({ ...value, [k]: v });
  const err = (k: string) => errors[`${prefixo}.${k}`];

  /** Busca o CEP (ViaCEP + código de município do Lyceum, pelo BFF) e preenche os campos.
   *  Disparada por Tab/saída do campo (só se o CEP mudou), Enter ou pela lupa (sempre). */
  async function buscar(forcar: boolean) {
    const cep = digits(value.cep);
    if (cep.length !== 8) {
      if (cep.length > 0 || forcar) setCepSt("invalido");
      return;
    }
    if (!forcar && cep === cepConhecido.current) return;
    const id = ++busca.current;
    setCepSt("busca");
    try {
      const r = await api.cep(cep);
      if (id !== busca.current) return; // resposta de uma busca antiga
      cepConhecido.current = cep;
      onChange({
        ...value, cep: value.cep, uf: r.uf, municipio: r.municipio, municipioCodigo: r.municipioCodigo ?? null,
        bairro: r.bairro ?? "", endereco: r.endereco ?? "",
      });
      setCepSt("ok");
      numeroRef.current?.querySelector("input")?.focus();
    } catch {
      if (id === busca.current) setCepSt("nao");
    }
  }

  return (
    <div className="grid g12">
      <div className="field c4">
        <label htmlFor={`${prefixo}-cep`}>CEP</label>
        <div className="cep-group">
          <input
            id={`${prefixo}-cep`}
            className={`input ${err("cep") ? "invalid" : ""}`}
            inputMode="numeric"
            autoComplete="postal-code"
            placeholder="00000-000"
            value={value.cep}
            disabled={disabled}
            aria-invalid={err("cep") ? true : undefined}
            aria-describedby={`${prefixo}-cep-st`}
            onChange={(e) => {
              onChange({ ...value, cep: digits(e.target.value).slice(0, 8).replace(/(d{5})(d)/, "$1-$2") });
              setCepSt("idle");
            }}
            onBlur={() => buscar(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault(); // não envia o formulário
                buscar(true);
              }
            }}
          />
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            onMouseDown={(e) => e.preventDefault()} // mantém o foco no CEP: evita a busca dupla (saída do campo + clique)
            onClick={() => buscar(true)}
            disabled={disabled || cepSt === "busca"}
            aria-label="Buscar endereço pelo CEP"
            title="Buscar endereço pelo CEP"
          >
            {cepSt === "busca" ? <Spin /> : (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.5-3.5" />
              </svg>
            )}
          </button>
        </div>
        <span id={`${prefixo}-cep-st`} aria-live="polite" className={err("cep") ? "err" : "hint"}>
          {err("cep") ?? ({
            idle: "Digite o CEP e tecle Tab, Enter ou a lupa",
            busca: "Buscando endereço…",
            ok: "Endereço preenchido pelo CEP. Confira e informe o número.",
            nao: "CEP não encontrado. Preencha o endereço manualmente.",
            invalido: "O CEP precisa ter 8 dígitos.",
          } as const)[cepSt]}
        </span>
      </div>
      <Select id={`${prefixo}-uf`} label="UF" value={value.uf} onValue={set("uf")} options={[["", "—"], ...UFS.map((u) => [u, u] as [string, string])]} cls="c2" error={err("uf")} />
      <Field id={`${prefixo}-municipio`} label="Cidade" value={value.municipio} onValue={(v) => onChange({ ...value, municipio: v, municipioCodigo: null })} error={err("municipio")} disabled={disabled} />
      <Field id={`${prefixo}-endereco`} label="Logradouro" value={value.endereco} onValue={set("endereco")} cls="c8" error={err("endereco")} disabled={disabled} autoComplete="address-line1" />
      <div ref={numeroRef} style={{ display: "contents" }}>
        <Field id={`${prefixo}-numero`} label="Número" value={value.numero} onValue={set("numero")} cls="c4" error={err("numero")} disabled={disabled} />
      </div>
      <Field id={`${prefixo}-complemento`} label="Complemento" value={value.complemento} onValue={set("complemento")} hint="Opcional" disabled={disabled} />
      <Field id={`${prefixo}-bairro`} label="Bairro" value={value.bairro} onValue={set("bairro")} error={err("bairro")} disabled={disabled} />
    </div>
  );
}
