"""Etapa 1 no legado: leitura do form-candidato (/r/ingresso) e corpo de /r/ingresso/atualizar.json.

HTML reduzido no formato observado em DEV (20/10/2026), com dados fictícios.
"""

import httpx
import pytest
import respx

from app.config import Settings
from app.core.errors import PortalError
from app.core.session import sessao_atual
from app.schemas.candidato import CandidatoUpdate
from app.services.lyceum.legado import candidato_de_form, parse_form, payload_atualizar
from app.services.lyceum.techne import TechneGateway

INGRESSO_HTML = """
<form id="frm-busca-oferta"><input type="text" name="buscar" value=""></form>
<form id="form-candidato" method="post">
  <input type="hidden" name="codCandidato" value="2027100000285">
  <input type="hidden" name="codConcurso" value="1363">
  <input type="text" id="nomeCompleto" name="nomeCompleto" value="Candidato de Teste">
  <input type="text" name="dataNascimento" value="10/05/2003">
  <select id="sexo" name="sexo" class="form-control" value="M"><option value="">Sexo</option>
    <option value="F">Feminino</option><option value="M">Masculino</option><option value="O">Outros</option></select>
  <select class="form-control" id="tipoDoc" name="tipoDoc"><option value="">Tipo</option><option value="cpf">CPF</option></select>
  <input type="text" name="cpf" value="529.982.247-25">
  <input type="text" name="identidade" value="1234567">
  <input type="text" name="passaporte" value="">
  <select id="estadoCivil" name="estadoCivil"><option value="">Estado Civil</option><option value="Solteiro">Solteiro</option></select>
  <input type="text" name="emailPessoal" value="teste@exemplo.com">
  <input type="text" name="dddFone" value="66"><input type="text" name="telefone" value="34210000">
  <input type="text" name="dddFoneCelular" value=""><input type="text" name="celular" value="">
  <input type="hidden" name="obrigatorioDddFone" value=""><input type="hidden" name="obrigatorioDddCel" value="true">
  <input type="hidden" name="pais" value="BRASIL">
  <input type="text" name="cep" value="78731610"><input type="text" name="cepEs" value="78731610">
  <input type="hidden" name="enderecoMunicipioCode" value="004462">
  <select name="municipio"></select>
  <input type="hidden" name="paisNascimento" value="Brasil">
  <input type="text" name="endereco" value="Rua A"><input type="text" name="numero" value="10">
  <input type="text" name="complemento" value=""><input type="text" name="bairro" value="Centro">
  <input type="text" name="cursoFormacao" value="Ensino M&eacute;dio"><input type="text" name="anoConclusao" value="2021">
  <input type="hidden" name="codigoCandidato" value="2027100000285"><input type="hidden" name="codigoConcurso" value="1363">
  <input type="hidden" name="pessoa" value="100001">
</form>"""
MUNICIPIO = {"codigo": "004462", "nome": "RONDONÓPOLIS", "uf": "MT", "cep": "NULL"}


def test_parse_form_restringe_ao_form_e_le_select():
    c = parse_form(INGRESSO_HTML, "form-candidato")
    assert "buscar" not in c  # campo de outro form
    assert (c["sexo"], c["tipoDoc"], c["estadoCivil"]) == ("M", "", "")
    assert c["cursoFormacao"] == "Ensino Médio" and c["pessoa"] == "100001"


def test_candidato_de_form():
    cand = candidato_de_form(parse_form(INGRESSO_HTML, "form-candidato"), MUNICIPIO)
    assert (cand.cod_candidato, cand.cod_concurso, cand.sexo, cand.tipo_doc) == ("2027100000285", "1363", "M", "cpf")
    assert cand.estado_civil is None and cand.celular == "" and cand.telefone == "6634210000"
    e = cand.endereco
    assert (e.cep, e.uf, e.municipio, e.municipio_codigo) == ("78731-610", "MT", "RONDONÓPOLIS", "004462")


def _update(**kw):
    d = {"nomeCompleto": "Candidato de Teste", "dataNascimento": "10/05/2003", "sexo": "M", "tipoDoc": "cpf",
         "cpf": "529.982.247-25", "identidade": "1234567", "estadoCivil": "Solteiro",
         "emailPessoal": "teste@exemplo.com", "celular": "(66) 99999-1234", "telefone": "",
         "endereco": {"pais": "BRASIL", "cep": "78731-610", "uf": "MT", "municipio": "RONDONÓPOLIS",
                      "municipioCodigo": "004462", "endereco": "Rua <b>A</b>", "numero": "10", "bairro": "Centro"}}
    d.update(kw)
    return CandidatoUpdate.model_validate(d)


def test_update_exige_sexo_e_estado_civil():
    with pytest.raises(ValueError):
        CandidatoUpdate.model_validate({**_update().model_dump(by_alias=True), "estadoCivil": None})
    with pytest.raises(ValueError):
        d = _update().model_dump(by_alias=True)
        d.pop("sexo")
        CandidatoUpdate.model_validate(d)


def test_payload_atualizar_preserva_ocultos_e_formata_como_o_legado():
    campos = parse_form(INGRESSO_HTML, "form-candidato")
    p = payload_atualizar(campos, _update(), "004462")
    assert p["pessoa"] == "100001" and p["codigoCandidato"] == "2027100000285"  # ocultos preservados
    assert p["cursoFormacao"] == "Ensino Médio" and p["obrigatorioDddCel"] == "true"
    assert (p["dddFoneCelular"], p["celular"], p["dddFone"], p["telefone"]) == ("66", "999991234", None, None)
    assert (p["cep"], p["cepEs"], p["enderecoUf"], p["municipio"], p["enderecoMunicipioCode"]) == (
        "78731-610", "78731610", "MT", "004462", "004462")
    assert p["estadoCivil"] == "Solteiro" and p["passaporte"] is None and p["complemento"] is None
    assert p["endereco"] == "Rua A"  # tags removidas, como no sanitizeJson


# ---------- CEP pela API v2 ----------
BASE = "https://api.exemplo/api"


VIACEP_74215025 = {"cep": "74215-025", "logradouro": "Avenida T-9", "bairro": "Setor Bueno",
                   "localidade": "Goiânia", "uf": "GO", "ibge": "5208707"}
LYCEUM_74215025 = {"data": {"municipio": "002174", "nomeMunicipio": "GOIÂNIA", "nomeBairro": "SETOR BUENO",
                            "ufSigla": "GO", "txbLogradouro": "AVENIDA T 9"}}


def _gw_settings():
    return Settings(_env_file=None, lyceum_mode="techne", lyceum_api_base_url=BASE, lyceum_api_basic_user="u",
                    lyceum_api_basic_password="p")


@respx.mock
async def test_cep_viacep_com_codigo_do_lyceum():
    respx.get("https://viacep.com.br/ws/74215025/json/").mock(return_value=httpx.Response(200, json=VIACEP_74215025))
    respx.get(f"{BASE}/v2/comum/cep/74215025/enderecos").mock(return_value=httpx.Response(200, json=LYCEUM_74215025))
    async with httpx.AsyncClient() as c:
        r = await TechneGateway(_gw_settings(), c).buscar_cep("74215-025")
    # texto do ViaCEP, código de município do Lyceum
    assert (r.endereco, r.bairro, r.municipio, r.uf, r.municipio_codigo) == (
        "Avenida T-9", "Setor Bueno", "Goiânia", "GO", "002174")


@respx.mock
async def test_cep_viacep_sem_lyceum_fica_sem_codigo():
    respx.get("https://viacep.com.br/ws/74215025/json/").mock(return_value=httpx.Response(200, json=VIACEP_74215025))
    respx.get(f"{BASE}/v2/comum/cep/74215025/enderecos").mock(side_effect=httpx.ConnectTimeout("t"))
    async with httpx.AsyncClient() as c:
        r = await TechneGateway(_gw_settings(), c).buscar_cep("74215025")
    assert (r.municipio, r.municipio_codigo) == ("Goiânia", None)  # resolvido pelo nome ao salvar


@respx.mock
async def test_cep_viacep_fora_usa_lyceum():
    respx.get("https://viacep.com.br/ws/74215025/json/").mock(side_effect=httpx.ConnectTimeout("viacep fora"))
    respx.get(f"{BASE}/v2/comum/cep/74215025/enderecos").mock(return_value=httpx.Response(200, json=LYCEUM_74215025))
    async with httpx.AsyncClient() as c:
        r = await TechneGateway(_gw_settings(), c).buscar_cep("74215025")
    assert (r.municipio, r.municipio_codigo, r.endereco) == ("GOIÂNIA", "002174", "AVENIDA T 9")


@respx.mock
async def test_cep_inexistente():
    respx.get("https://viacep.com.br/ws/00000000/json/").mock(return_value=httpx.Response(200, json={"erro": "true"}))
    lyc = respx.get(f"{BASE}/v2/comum/cep/00000000/enderecos").mock(return_value=httpx.Response(500, json={}))
    async with httpx.AsyncClient() as c:
        assert await TechneGateway(_gw_settings(), c).buscar_cep("00000000") is None
    assert lyc.call_count <= 1  # não houve retentativa nem espera desnecessária


@pytest.mark.parametrize("entrada,saida", [
    ("10052003", "10/05/2003"), ("10/05/2003", "10/05/2003"), ("10/05/2003 00:00:00", "10/05/2003"),
    ("2003-05-10", "10/05/2003"), ("2003-05-10T00:00:00", "10/05/2003"), ("", ""), (None, ""),
])
def test_normalizar_data(entrada, saida):
    from app.core.validators import normalizar_data_br
    assert normalizar_data_br(entrada) == saida


def test_data_do_form_legado_vem_formatada():
    html_8_digitos = INGRESSO_HTML.replace('value="10/05/2003"', 'value="10052003"')
    cand = candidato_de_form(parse_form(html_8_digitos, "form-candidato"), MUNICIPIO)
    assert cand.data_nascimento == "10/05/2003"


@respx.mock
async def test_ingresso_fechado_409():
    from app.services.lyceum.legado import ClienteLegado, SessoesLegado
    leg = "https://legado.exemplo/ps"
    sessoes = SessoesLegado()
    sessoes.criar("sid-i", httpx.Cookies())
    respx.get(f"{leg}/r/ingresso").mock(return_value=httpx.Response(200, text="<html>sem formulário</html>"))
    sessao_atual.set("sid-i")
    with pytest.raises(PortalError) as e:
        await ClienteLegado(leg, 5, sessoes).candidato("sid-i", "2027100000285", "1363")
    assert e.value.status == 409
