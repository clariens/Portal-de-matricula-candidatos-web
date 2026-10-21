import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../api/client";
import type { Candidato, CandidatoUpdate } from "../../api/types";
import { EnderecoFields, validarEndereco, type EnderecoForm } from "../../components/EnderecoFields";
import { Alert, Chip, Field, Select, Spin, useToast } from "../../components/ui";
import { cpfValido, dataValida, digits, emailValido, maskCPF, maskDate, maskPhone } from "../../lib/format";
import { useWizard } from "./Wizard";

type Form = Omit<CandidatoUpdate, "endereco" | "telefone" | "cpf" | "identidade" | "sexo" | "estadoCivil"> & {
  sexo: string; // "" quando o Lyceum ainda não tem o dado; obrigatório ao salvar
  estadoCivil: string;
  cpf: string;
  identidade: string;
  telefone: string;
  endereco: EnderecoForm;
};

// Valores aceitos pelo Lyceum (mesma lista do select do portal legado)
const ESTADOS_CIVIS = ["Solteiro", "Casado", "Divorciado", "Viúvo", "União Estável", "Marital", "Separado",
  "Separado Consensualmente", "Separado Judicialmente"];
const SEXOS: [string, string][] = [["F", "Feminino"], ["M", "Masculino"], ["O", "Outros"]];

function paraForm(c: Candidato): Form {
  return {
    nomeCompleto: c.nomeCompleto, dataNascimento: maskDate(c.dataNascimento), sexo: c.sexo ?? "", tipoDoc: c.tipoDoc ?? "cpf",
    cpf: maskCPF(c.cpf ?? ""), identidade: c.identidade ?? "", passaporte: c.passaporte ?? null, estadoCivil: c.estadoCivil ?? "",
    emailPessoal: c.emailPessoal, celular: maskPhone(c.celular), telefone: maskPhone(c.telefone ?? ""),
    paisNascimento: c.paisNascimento, municipioNascimento: c.municipioNascimento,
    endereco: {
      pais: c.endereco.pais ?? "BRASIL", cep: c.endereco.cep, uf: c.endereco.uf, municipio: c.endereco.municipio,
      municipioCodigo: c.endereco.municipioCodigo, endereco: c.endereco.endereco, numero: c.endereco.numero,
      complemento: c.endereco.complemento ?? "", bairro: c.endereco.bairro,
    },
  };
}

function validar(f: Form) {
  const er: Record<string, string> = {};
  if (f.nomeCompleto.trim().split(/\s+/).length < 2) er.nomeCompleto = "Informe nome e sobrenome.";
  if (!dataValida(f.dataNascimento)) er.dataNascimento = "Use o formato dd/mm/aaaa.";
  if (!f.sexo) er.sexo = "Selecione o sexo.";
  if (!f.estadoCivil) er.estadoCivil = "Selecione o estado civil.";
  if (f.tipoDoc === "cpf" && !cpfValido(f.cpf)) er.cpf = "CPF inválido. Confira os dígitos.";
  if (!emailValido(f.emailPessoal)) er.emailPessoal = "E-mail inválido.";
  if (digits(f.celular).length !== 11) er.celular = "Informe DDD + 9 dígitos.";
  if (f.telefone && ![0, 10, 11].includes(digits(f.telefone).length)) er.telefone = "Telefone com DDD.";
  return { ...er, ...validarEndereco(f.endereco) };
}

export function EtapaDados() {
  const { insc, candidato, setCandidato, recarregar, ir, somenteLeitura } = useWizard();
  const toast = useToast();
  const [f, setF] = useState<Form>(() => paraForm(candidato));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const set = <K extends keyof Form>(k: K) => (v: Form[K]) => setF((x) => ({ ...x, [k]: v }));

  function focarPrimeiroErro() {
    requestAnimationFrame(() => (document.querySelector(".input.invalid") as HTMLElement | null)?.focus());
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
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
      const body: CandidatoUpdate = {
        ...f, sexo: f.sexo as CandidatoUpdate["sexo"], telefone: f.telefone || null, cpf: f.tipoDoc === "cpf" ? f.cpf : null,
        endereco: { ...f.endereco, complemento: f.endereco.complemento || null },
      };
      setCandidato(await api.salvarCandidato(insc.codCandidato, body));
      await recarregar();
      ir("documentos");
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
    <form onSubmit={submit} noValidate>
      {erroGeral && <Alert>{erroGeral}</Alert>}
      <fieldset disabled={somenteLeitura || salvando} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <section className="card panel">
          <div className="panel-head">
            <h2>Dados pessoais</h2>
            <Chip tone="ok">Preenchido a partir da inscrição</Chip>
          </div>
          <div className="grid g12">
            <Field id="nomeCompleto" label="Nome completo" value={f.nomeCompleto} onValue={set("nomeCompleto")} cls="c8" error={errors.nomeCompleto} autoComplete="name" />
            <Field id="dataNascimento" label="Data de nascimento" value={f.dataNascimento} onValue={set("dataNascimento")} cls="c4" mask="date" inputMode="numeric" placeholder="dd/mm/aaaa" error={errors.dataNascimento} />
            <Select id="sexo" label="Sexo" value={f.sexo} onValue={set("sexo")} options={[["", "Selecione"], ...SEXOS]} error={errors.sexo} />
            <Select id="estadoCivil" label="Estado civil" value={f.estadoCivil} onValue={set("estadoCivil")} options={[["", "Selecione"], ...ESTADOS_CIVIS.map((e): [string, string] => [e, e])]} error={errors.estadoCivil} />
            <Field id="cpf" label="CPF" value={f.cpf} onValue={set("cpf")} cls="c3" mask="cpf" inputMode="numeric" error={errors.cpf} />
            <Field id="identidade" label="RG" value={f.identidade} onValue={set("identidade")} cls="c3" error={errors.identidade} />
          </div>
        </section>
        <section className="card panel">
          <h2>Contato</h2>
          <div className="grid g12">
            <Field id="emailPessoal" label="E-mail" type="email" value={f.emailPessoal} onValue={set("emailPessoal")} error={errors.emailPessoal} autoComplete="email" />
            <Field id="celular" label="Celular (WhatsApp)" value={f.celular} onValue={set("celular")} cls="c3" mask="phone" inputMode="tel" hint="Recebe o contrato para assinatura" error={errors.celular} />
            <Field id="telefone" label="Telefone fixo" value={f.telefone} onValue={set("telefone")} cls="c3" mask="phone" inputMode="tel" hint="Opcional" error={errors.telefone} />
          </div>
        </section>
        <section className="card panel">
          <h2>Endereço</h2>
          <EnderecoFields value={f.endereco} onChange={set("endereco")} errors={errors} />
        </section>
      </fieldset>
      <div className="foot">
        <span className="muted" style={{ fontSize: 13 }}>
          {somenteLeitura ? "Dados bloqueados após a pré-matrícula." : "Salvo ao avançar"}
        </span>
        {!somenteLeitura && (
          <button className="btn btn-primary" type="submit" disabled={salvando}>
            {salvando ? <><Spin /> Salvando</> : "Salvar e continuar"}
          </button>
        )}
      </div>
    </form>
  );
}
