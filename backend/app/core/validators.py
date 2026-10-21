import re
from datetime import date, datetime


def digits(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")


def cpf_valido(v: str | None) -> bool:
    c = digits(v)
    if len(c) != 11 or c == c[0] * 11:
        return False
    for t in (9, 10):
        s = sum(int(c[i]) * (t + 1 - i) for i in range(t))
        if (s * 10) % 11 % 10 != int(c[t]):
            return False
    return True


def cnpj_valido(v: str | None) -> bool:
    c = digits(v)
    if len(c) != 14 or c == c[0] * 14:
        return False
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        p = pesos[-n:] if n == 12 else [6, *pesos]
        r = sum(int(c[i]) * p[i] for i in range(n)) % 11
        if (0 if r < 2 else 11 - r) != int(c[n]):
            return False
    return True


def mask_cpf(v: str) -> str:
    c = digits(v)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:11]}" if len(c) == 11 else v


def mask_cep(v: str) -> str:
    c = digits(v)
    return f"{c[:5]}-{c[5:8]}" if len(c) == 8 else v


def parse_data_br(v: str) -> date:
    return datetime.strptime(v, "%d/%m/%Y").date()


def normalizar_data_br(v: str | None) -> str:
    """Converte as variações vistas no Lyceum para dd/mm/aaaa.

    - "14032004" (form do legado: ddmmaaaa; a máscara 99/99/9999 só é aplicada no navegador)
    - "14/03/2004", "14/3/2004" (RG antigo), "14/03/2004 00:00:00"
    - "2004-03-14", "2004-03-14T00:00:00"
    Valor irreconhecível volta como veio (a validação do formulário aponta o erro).
    """
    s = (v or "").strip()
    if not s:
        return ""
    d = digits(s)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", s):
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)  # 14/03/2004, 14/3/2004, 14.03.2004 (+ hora)
    if m:
        return f"{int(m[1]):02d}/{int(m[2]):02d}/{m[3]}"
    if len(d) == 8 and s.isdigit():
        return f"{d[0:2]}/{d[2:4]}/{d[4:8]}"
    return s


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
