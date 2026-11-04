# "Meus Dados" no Processo Seletivo (legado): dados de contato, endereço e senha

Mapeado em 04/11/2026 no DEV (`/processo-seletivo/r/alterarDados`, conta de teste), só lendo a página e o script
`js/alteracaoDados.js`. Nada foi enviado. Serve de base para uma tela "Meus dados" no portal.

## A página
Link "Meus Dados" no topo do legado (ao lado de "Histórico" e "Logout"). Títulos: **Dados de Contato**, **Dados de
Endereço** e **Alteração de Senha**. Um seletor (`tipoAcao`: "Dados" ou "Senha") mostra um dos dois formulários.
Nome, CPF e data de nascimento **não** são editáveis aqui.

O portal já usa essa página no login: o `idPessoa` vem do campo oculto dela.

## 1. Dados de contato e endereço (`frm-pessoa-fisica`)
| Campo | Regra no navegador |
|---|---|
| `idPessoa` (oculto) | vem da página; no portal, sempre da sessão, nunca do navegador |
| `dddCelular`, `celular` | obrigatórios (`obrigatorioDddCel`/`obrigatorioCelular` = `true` no DEV); DDD até 3, celular mínimo 8 |
| `dddFone`, `telefone` | opcionais no DEV (`obrigatorioDddFone`/`obrigatorioTelefone` vazios); telefone mínimo 8 |
| `email` | obrigatório, formato de e-mail, até 100 |
| `cep` | obrigatório, `99999-999`; ao sair do campo busca o endereço (`GET endereco/obterEnderecoPorUf`) |
| `enderecoMunicipio` (select) + `enderecoMunicipioCode` (oculto) | obrigatório; lista por `GET endereco/listarMunicipios` / `listarMunicipiosCodigo` |
| `endereco` | obrigatório, até 50 |
| `enderecoNum` | obrigatório, até 15 |
| `enderecoCompl` | opcional, até 50 |
| `enderecoBairro` | obrigatório, até 50 |

**Salvar:** `POST r/alterarDados/alterarPessoaFisica.json` com o formulário em JSON (`lyceumJsonPOST`). Sucesso:
"Dados alterados com sucesso !". Erro: mensagem do `lyceumRetorno` e nova busca do CEP.

Controles ocultos lidos pelo script: `verificafraudeInput` e `requerTelefoneInput` (`N` no DEV; com `S`, o telefone
passa a ter validação extra de antifraude).

## 2. Alteração de senha (`frm-altera-senha`)
| Campo | Regra |
|---|---|
| `idPessoa` (oculto) | idem: no portal, da sessão |
| `senhaAtual` | obrigatória |
| `senha` | obrigatória |
| `senhaRepeticao` | obrigatória, igual a `senha`, até 40 caracteres |
| `tokenCaptcha` (oculto) | reCAPTCHA do Google, **só quando a página tem o bloco `#recaptcha`** (não tem no DEV; conferir em produção) |

**Salvar:** `POST r/alterarDados/alterarSenhaPessoa.json` com o formulário em JSON. Sucesso: "Senha alterada com
sucesso !" e os campos são limpos.

## Diferenças em relação ao que o portal já tem
- A etapa "Seus dados" da matrícula grava por `POST /r/ingresso/atualizar.json` (dados do ingresso, com nome,
  documentos, nascimento). "Meus Dados" é outra rota, só contato e endereço, e vale fora da matrícula.
- O portal já tem "Esqueci minha senha" (`/recuperarsenha`); a troca com a senha atual seria nova.

## Para implementar (proposta)
- BFF: `GET /api/v1/meus-dados` (lê o `frm-pessoa-fisica`), `PUT /api/v1/meus-dados` (`alterarPessoaFisica.json`)
  e `POST /api/v1/meus-dados/senha` (`alterarSenhaPessoa.json`), sempre com o `idPessoa` da sessão.
- Tela "Meus dados" no menu do topo (logado), com as mesmas regras acima; o CEP reusa o ViaCEP do portal.
- Gravações reais: `alterarPessoaFisica.json` altera os dados da pessoa e `alterarSenhaPessoa.json` troca a senha
  da conta. Testar só com autorização e numa conta de teste (a troca de senha muda o acesso dela).
