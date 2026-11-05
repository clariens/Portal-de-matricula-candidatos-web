/** Depois do login, volta para onde a pessoa estava, mas só dentro do portal: "//site", "/\site" ou uma URL
 *  completa levariam para fora (redirecionamento aberto). */
export function destinoSeguro(from: string | undefined): string {
  return from && /^\/(?![/\\])/.test(from) ? from : "/inscricoes";
}

/** Link vindo do servidor (ex.: questionário do legado): só https. O React não bloqueia `javascript:` no href,
 *  que rodaria código na origem do portal. Devolve null quando não for seguro (a tela mostra só o texto). */
export function urlExternaSegura(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}
