# Cabeçalho do Processo Seletivo (produção): mapeamento

Levantado em 29/10/2026 em `https://portal.clariens.com.br/processo-seletivo/home`, só com leitura: páginas
públicas e uma busca. O formulário de cadastro não foi enviado. Serve de base para o cabeçalho do portal novo.

## O que o cabeçalho tem

| Item | Onde | O que faz |
|---|---|---|
| Logo | canto superior esquerdo | `GET /processo-seletivo/recurso/LOGO` (imagem), link para `/home` |
| **Escolha a área do seu interesse** | menu suspenso, à esquerda | **Graduação** com 5 subgrupos (abaixo), cada um é um link |
| **Qual curso você procura?** | campo de busca | `POST /processo-seletivo/busca`, form `buscar=<texto>` (obrigatório), resposta em HTML |
| **Login** | direita | link para `/processo-seletivo/r/historico` (sem sessão, mostra o login) |
| **Cadastre-se** | direita | link para `/processo-seletivo/cadastro?et=4` |

### Subgrupos de Graduação (ids fixos no HTML)

| Subgrupo | Rota |
|---|---|
| Vestibular Tradicional | `GET /processo-seletivo/subgrupo?id=4` |
| Transferência Externa | `GET /processo-seletivo/subgrupo?id=15` |
| Enem | `GET /processo-seletivo/subgrupo?id=16` |
| Segunda Graduação | `GET /processo-seletivo/subgrupo?id=17` |
| Tradicional Catalão | `GET /processo-seletivo/subgrupo?id=31` |

A página do subgrupo e a da busca devolvem **HTML** com uma tabela "Curso · Descrição · Ver detalhes". Cada linha
aponta para `GET /processo-seletivo/oferta?id=<oferta>`. Exemplo do Enem (2027.1): ofertas 8541 (Zarns
Salvador), 8549 (Zarns Itumbiara), 8553 (IMEPAC Medicina), 8556 (Zarns Pouso Alegre Medicina), 8557 (Unesulbahia
Medicina) e 8562 (Zarns Pouso Alegre Odontologia). A busca por "medicina" trouxe ofertas de todos os subgrupos.
Não há API JSON para a lista: o portal novo teria que ler o HTML (como já faz com o histórico) ou usar a API v2.

## Cadastro (`/cadastro?et=4`)

Formulário `form-cadastro-completo` com: `NOME_COMPLETO`, `NOME_SOCIAL`, `CPF`, `RG`, `PASSAPORTE`,
`DATA_DE_NASCIMENTO`, `SEXO`, `NACIONALIDADE`, `E_MAIL`, `DDD_FONE_CELULAR`/`FONE_CELULAR`,
`DDD_FONE_RESIDENCIAL`/`FONE_RESIDENCIAL`, `CEP`, `PAIS`, `UF`, `MUNICIPIO`, `ENDERECO`, `NUMERO`,
`COMPLEMENTO`, `BAIRRO`, `RESIDENCIA_ESTRANGEIRA` (`CEPES`, `UFES`, `MUNICIPIOES`), `ESCOLA_NOME_OUTRA`,
`SENHA`, `SENHA_CONFIRMACAO` e o aceite LGPD (`contratoAceiteLGPD`). Rotas chamadas pelo `js/cadastro.js`:

| Rota | Quando |
|---|---|
| `GET cadastro/validarPessoa?cpf=…` | ao sair do campo CPF. Se já existir cadastro, manda para o login |
| `GET cadastro/validarCampo?valor=…&nome=…` | validações pontuais de campo |
| `GET endereco/listarUfs`, `endereco/listarMunicipios`, `endereco/obterEnderecoPorUf` | UF, cidade e CEP (já usadas no portal) |
| `GET endereco/listarUfsEstrangeiros` | residência no exterior |
| **`POST cadastro/cadastrar.json`** (JSON do form) | **cria a conta**. Em sucesso, `item[0]` é a URL para onde seguir |

Na home há também `POST home/cadastroResponsavel.json` (cadastro de responsável) e o link "Criar conta" vira
`/cadastrosimples` em algumas URLs.

## Login e senha

- Login: `POST /processo-seletivo/j_security_check` (já usado pelo portal).
- **Esqueci minha senha:** `/processo-seletivo/recuperarsenha` (link na tela de login do legado).
- "Cadastre-se aqui" na tela de login chama `redirectCadastro()` e vai para o cadastro.

## Implementado no portal (29/10/2026)

| Tela | Rota do portal (BFF) | No legado (`LYCEUM_LEGADO_BASE_URL`, hoje o DEV) |
|---|---|---|
| Cabeçalho: **Área de interesse** (à esquerda) e **Cadastre-se** (à direita, só sem login) | `GET /api/v1/publico/cabecalho` (público) | lê o menu de `GET /home` (cache de 10 min). Com o legado fora, usa os subgrupos conhecidos (4, 15, 16, 17, 31). Links abrem em nova aba |
| Login: **Esqueci minha senha** | `POST /api/v1/auth/recuperar-senha` `{login}` | `GET /recuperarsenha`, depois `POST /recuperarsenha/recuperar.json` `{"login": …}` e `GET /recuperarsenha/sucesso`, na mesma sessão anônima. Mensagem de erro e de sucesso são as do legado |

O "Entrar" não aparece no cabeçalho, porque ele já está na própria tela de login.

## Proposta para o portal novo

1. Cabeçalho com "Área de interesse → Graduação → subgrupos" e a busca. Para começar, os links abrem as páginas do
   legado. Depois, uma lista própria lida de `subgrupo?id=` / `busca`.
2. "Cadastre-se" e "Esqueci minha senha" apontam para as páginas do legado (`/cadastro?et=4`, `/recuperarsenha`).
   Um cadastro próprio só se `cadastro/cadastrar.json` for aprovado como rota oficial, porque ele cria a pessoa no
   Lyceum.
3. Atenção: os ids dos subgrupos e das ofertas são de **produção**. No DEV podem ser outros, então é preciso
   conferir em `desenvolvimento-lyceum` antes.
