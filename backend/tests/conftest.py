import os

import pytest
from fastapi.testclient import TestClient

os.environ["PORTAL_ENV_FILE"] = "__sem_env_nos_testes__"  # nunca ler o backend/.env real
os.environ.setdefault("PORTAL_SESSION_SECRET", "segredo-de-teste")

from app.main import app
from tests.fake_lyceum import FakeLyceum

app.state.gateway_factory = lambda settings, client: FakeLyceum()

H = {"X-Requested-With": "fetch"}
INSC = "2027100000162"


@pytest.fixture
def client():
    with TestClient(app) as c:
        app.state.gateway.reset()
        yield c


@pytest.fixture
def logged(client):
    r = client.post("/api/v1/auth/login", json={"login": "123.456.789-09", "senha": "demonstracao"}, headers=H)
    assert r.status_code == 200, r.text
    return client


CANDIDATO_OK = {
    "nomeCompleto": "Ana Beatriz Rocha",
    "dataNascimento": "14/03/2004",
    "sexo": "F",
    "tipoDoc": "cpf",
    "cpf": "123.456.789-09",
    "identidade": "5123456",
    "estadoCivil": "Solteiro",
    "emailPessoal": "ana.rocha@exemplo.com",
    "celular": "(34) 99123-4567",
    "endereco": {
        "pais": "BRASIL", "cep": "38440-000", "uf": "MG", "municipio": "Araguari",
        "endereco": "Avenida Minas Gerais", "numero": "1200", "bairro": "Centro",
    },
}

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def ref(c, cod=INSC):
    """Referência opaca da inscrição, lida do histórico como o front faz (a URL não leva o número)."""
    if "refs" not in c.__dict__:
        c.__dict__["refs"] = {i["codCandidato"]: i["ref"] for i in c.get("/api/v1/inscricoes", headers=H).json()}
    return c.__dict__["refs"][cod]
