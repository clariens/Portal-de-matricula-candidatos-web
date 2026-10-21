// Máscaras e validações portadas do protótipo.
export const digits = (s: unknown) => String(s ?? "").replace(/\D/g, "");
export const brl = (v: number) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
export const norm = (s: unknown) =>
  String(s ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toUpperCase();

export function maskCPF(v: string) {
  v = digits(v).slice(0, 11);
  return v.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}
export function maskCNPJ(v: string) {
  v = digits(v).slice(0, 14);
  return v
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}
export function maskDate(v: string) {
  v = digits(v).slice(0, 8);
  return v.replace(/(\d{2})(\d)/, "$1/$2").replace(/(\d{2})(\d)/, "$1/$2");
}
export function maskCEP(v: string) {
  v = digits(v).slice(0, 8);
  return v.replace(/(\d{5})(\d)/, "$1-$2");
}
export function maskPhone(v: string) {
  v = digits(v).slice(0, 11);
  if (v.length <= 10) return v.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d)/, "$1-$2");
  return v.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2");
}
export function cpfValido(c: string) {
  c = digits(c);
  if (c.length !== 11 || /^(\d)\1+$/.test(c)) return false;
  for (let t = 9; t < 11; t++) {
    let s = 0;
    for (let i = 0; i < t; i++) s += +c[i] * (t + 1 - i);
    if (((s * 10) % 11) % 10 !== +c[t]) return false;
  }
  return true;
}
export function cnpjValido(c: string) {
  c = digits(c);
  if (c.length !== 14 || /^(\d)\1+$/.test(c)) return false;
  const calc = (n: number) => {
    const pesos = n === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const r = pesos.reduce((s, p, i) => s + +c[i] * p, 0) % 11;
    return r < 2 ? 0 : 11 - r;
  };
  return calc(12) === +c[12] && calc(13) === +c[13];
}
export const emailValido = (v: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim());
export const dataValida = (v: string) => {
  if (!/^\d{2}\/\d{2}\/\d{4}$/.test(v)) return false;
  const [d, m, a] = v.split("/").map(Number);
  const dt = new Date(a, m - 1, d);
  return dt.getFullYear() === a && dt.getMonth() === m - 1 && dt.getDate() === d;
};
export const MASKS = { cpf: maskCPF, cnpj: maskCNPJ, date: maskDate, cep: maskCEP, phone: maskPhone } as const;
export type MaskName = keyof typeof MASKS;
