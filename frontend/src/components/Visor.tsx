import { useEffect, useRef } from "react";

export interface Visto {
  nome: string;
  url: string;
  pdf: boolean;
  arquivo: string; // nome sugerido para baixar
  temporaria: boolean; // URL criada só para o visor (anexo local): liberada ao fechar
}

/** Visor do documento: imagem ou PDF, com opção de baixar. Usa o <dialog> nativo (foco e Esc do navegador). */
export function Visor({ visto, fechar }: { visto: Visto; fechar: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dlg = ref.current;
    if (dlg && !dlg.open) dlg.showModal();
  }, []);
  return (
    <dialog ref={ref} className="visor" aria-label={visto.nome} onClose={fechar} onClick={(e) => e.target === ref.current && fechar()}>
      <header>
        <h3>{visto.nome}</h3>
        <div>
          <a className="btn btn-ghost btn-sm" href={visto.url} download={visto.arquivo}>Baixar</a>
          <button className="btn btn-primary btn-sm" type="button" onClick={fechar} autoFocus>Fechar</button>
        </div>
      </header>
      {visto.pdf
        ? <iframe src={visto.url} title={visto.nome} />
        : <img src={visto.url} alt={visto.nome} />}
    </dialog>
  );
}
