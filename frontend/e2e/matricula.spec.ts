import { expect, test, type Page } from "@playwright/test";

/** Gera no navegador uma imagem PNG com as linhas de texto (documento fictício) para o OCR real ler. */
async function documento(page: Page, linhas: string[], nome: string, mime = "image/png") {
  const dataUrl = await page.evaluate(([ls, tipo]) => {
    const cv = document.createElement("canvas");
    cv.width = 1400;
    cv.height = 200 + ls.length * 110;
    const g = cv.getContext("2d")!;
    g.fillStyle = "#fff";
    g.fillRect(0, 0, cv.width, cv.height);
    g.fillStyle = "#111";
    ls.forEach((l, i) => {
      g.font = "bold 46px Arial";
      g.fillText(l, 70, 120 + i * 110);
    });
    return cv.toDataURL(tipo);
  }, [linhas, mime] as const);
  return { name: nome, mimeType: mime, buffer: Buffer.from(dataUrl.split(",")[1], "base64") };
}

const docRow = (page: Page, nome: string) => page.locator(".doc", { has: page.getByRole("heading", { name: nome, exact: true }) });

test("fluxo completo de matrícula (dublê do Lyceum)", async ({ page }) => {
  // login
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("E-mail ou CPF").fill("123.456.789-09");
  await page.getByLabel("Senha").fill("errada");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("alert")).toContainText("Usuário ou senha inválidos.");
  await page.getByLabel("Senha").fill("demonstracao");
  await page.getByRole("button", { name: "Entrar" }).click();

  // histórico
  await expect(page.getByRole("heading", { name: "Minhas inscrições" })).toBeVisible();
  await expect(page.locator("article.ins")).toHaveCount(4);
  await page.locator(".banner-call").getByRole("button", { name: "Fazer matrícula" }).click();

  // etapa 1: dados (erro por campo e correção)
  await expect(page.getByRole("heading", { name: "Seus dados" })).toBeVisible();
  const cel = page.getByLabel("Celular (WhatsApp)");
  await cel.fill("349");
  await page.getByRole("button", { name: "Salvar e continuar" }).click();
  await expect(page.getByText("Informe DDD + 9 dígitos.")).toBeVisible();
  await cel.fill("34991234567");
  // CEP: sair do campo sem mudar não busca; Tab com CEP novo busca; lupa sempre busca
  const cep = page.getByLabel("CEP", { exact: true });
  await cep.focus();
  await cep.press("Tab");
  await expect(page.getByLabel("Cidade")).toHaveValue("Araguari");
  await cep.fill("74215025");
  await cep.press("Tab");
  await expect(page.getByLabel("Cidade")).toHaveValue("Goiânia");
  await expect(page.getByLabel("Logradouro")).toHaveValue("Rua T-9");
  await expect(page.getByLabel("Número")).toBeFocused();
  await cep.fill("38440000");
  await cep.press("Enter");
  await expect(page.getByLabel("Cidade")).toHaveValue("Araguari");
  await page.getByRole("button", { name: "Buscar endereço pelo CEP" }).click();
  await expect(page.getByText("Endereço preenchido pelo CEP.")).toBeVisible();
  await cep.fill("00000000");
  await cep.press("Tab");
  await expect(page.getByText("CEP não encontrado. Preencha o endereço manualmente.")).toBeVisible();
  await cep.fill("74215025");
  await cep.press("Tab");
  await expect(page.getByLabel("Cidade")).toHaveValue("Goiânia");
  await page.getByLabel("Número").fill("100");
  await page.getByRole("button", { name: "Salvar e continuar" }).click();

  // etapa 2: documentos com OCR real — a conferência roda no momento em que cada arquivo é anexado
  await expect(page.getByRole("heading", { name: "Seus documentos" })).toBeVisible();
  const nome = "ANA BEATRIZ ROCHA";
  const cpfRow = docRow(page, "CPF");

  // RG anexado no lugar do CPF: ✗ "Documento não reconhecido" e só permite escolher outro arquivo
  await page.locator("#up-05").setInputFiles(await documento(page, ["REGISTRO GERAL", `NOME ${nome}`, "NASCIMENTO 14/03/2004"], "rg-no-lugar.png"));
  await expect(cpfRow.locator(".chip")).toContainText("Documento não reconhecido");
  await expect(cpfRow).toContainText("Este não é o documento que esperamos.");
  await expect(cpfRow).toContainText("não parece ser o CPF");
  await expect(cpfRow.getByText("Escolher outro arquivo")).toBeVisible();
  await expect(cpfRow.getByRole("button", { name: /conferência manual/ })).toHaveCount(0);

  // agora o CPF certo: ✓ conferido e anexado sozinho
  await page.locator("#up-05").setInputFiles(await documento(page, ["CADASTRO DE PESSOA FISICA", `NOME ${nome}`, "CPF 123.456.789-09"], "cpf.png"));
  await expect(cpfRow.locator(".chip")).toContainText("Conferido · pronto para envio");
  await expect(cpfRow).toContainText("Documento conferido: é o documento esperado");

  // identidade em WEBP: aceita, lida pelo OCR e anexada como JPG (o Lyceum não aceita WEBP)
  const rgRow = docRow(page, "Documento de Identidade");
  const rgWebp = await documento(page, ["REGISTRO GERAL", `NOME ${nome}`, "NASCIMENTO 14/03/2004"], "rg.webp", "image/webp");
  expect(rgWebp.buffer.subarray(8, 12).toString()).toBe("WEBP");
  await page.locator("#up-04").setInputFiles(rgWebp);
  await expect(rgRow.locator(".chip")).toContainText("Conferido · pronto para envio");
  await expect(rgRow).toContainText("rg.jpg (convertido de WEBP)");

  await page.locator("#up-03").setInputFiles(await documento(page, ["HISTORICO ESCOLAR", `ALUNO ${nome}`, "CONCLUSAO EM 2021"], "hist.png"));
  await expect(docRow(page, "Certificado de Conclusão / Histórico Escolar").locator(".chip")).toContainText("Conferido · pronto para envio");

  // declaração certa, mas concluída após 2022: ✗ dados não conferem → outro arquivo OU conferência manual
  const decl = docRow(page, "Declaração de Conclusão do Ensino Médio até 31/12/2022");
  await page.locator("#up-02").setInputFiles(await documento(page, ["DECLARACAO DE CONCLUSAO", `ALUNO ${nome}`, "CONCLUIU EM 2023"], "decl.png"));
  await expect(decl.locator(".chip")).toContainText("Dados não conferem");
  await expect(decl).toContainText("só vale para conclusões até 31/12/2022");
  await expect(decl.getByText("Escolher outro arquivo")).toBeVisible();
  await decl.getByRole("button", { name: "Manter este e enviar para conferência manual" }).click();
  await expect(decl.locator(".chip")).toContainText("Para conferência · pronto para envio");
  await expect(decl).toContainText("Anexado para a secretaria conferir:");

  // opcional anexado e removido
  const vacina = docRow(page, "Cartão de Vacina");
  await page.locator("#up-14").setInputFiles(await documento(page, ["CARTAO DE VACINA", `NOME ${nome}`, "DOSE 1 COVID 19"], "vacina.png"));
  await expect(vacina.locator(".chip")).toContainText("pronto para envio");
  await vacina.getByRole("button", { name: "Remover" }).click();
  await expect(vacina.locator(".chip")).toHaveCount(0);

  // os anexos ficam no navegador (o servidor não guarda nada): recarregar a página não perde nada
  await page.reload();
  await expect(page.getByRole("heading", { name: "Seus documentos" })).toBeVisible();
  await expect(cpfRow.locator(".chip")).toContainText("Conferido · pronto para envio");
  await expect(cpfRow).toContainText("cpf.png");
  await expect(rgRow).toContainText("rg.jpg (convertido de WEBP)");
  await expect(decl.locator(".chip")).toContainText("Para conferência · pronto para envio");
  await expect(vacina.locator(".chip")).toHaveCount(0); // o removido continua removido

  await page.getByRole("button", { name: "Enviar documentos e continuar" }).click();

  // etapa 3: pagamento
  await expect(page.getByRole("heading", { name: "Pagamento", exact: true })).toBeVisible();
  await expect(page.getByRole("radio", { name: /Cartão de crédito/ })).toBeDisabled();
  await page.getByLabel("Código do cupom").fill("XYZ");
  await page.getByRole("button", { name: "Aplicar" }).click();
  await expect(page.getByText("Cupom não encontrado para este curso.")).toBeVisible();
  await page.getByLabel("Código do cupom").fill("CLARIENS10");
  await page.getByRole("button", { name: "Aplicar" }).click();
  await expect(page.getByText("Cupom aplicado: 10% de desconto.")).toBeVisible();
  // como no legado, nenhuma forma vem marcada; outra pessoa pede os mesmos campos do formulário do legado
  await page.getByRole("button", { name: "Confirmar pagamento" }).click();
  await expect(page.getByText("Escolha a forma de pagamento.")).toBeVisible();
  await page.locator("label.choice", { hasText: "Outra pessoa" }).click();
  await page.getByRole("button", { name: "Confirmar pagamento" }).click();
  await expect(page.getByText("Selecione o estado civil.")).toBeVisible();
  await expect(page.getByLabel("Telefone")).toBeVisible();
  await page.locator("label.choice", { hasText: "Eu mesmo(a)" }).click();
  await page.locator("label.choice", { hasText: "Boleto" }).click();
  await page.getByRole("button", { name: "Confirmar pagamento" }).click();

  // etapa 4: conclusão
  await expect(page.getByRole("heading", { name: "Matrícula concluída" })).toBeVisible();
  await expect(page.locator(".mat")).toContainText("2716520002");
  await expect(page.getByText("O boleto da 1ª parcela foi enviado para o seu e-mail.")).toBeVisible();
  await expect(page.locator(".disc li")).toHaveCount(6);
  await page.getByRole("button", { name: "Concluir e ir para minhas inscrições" }).click();
  await expect(page.getByText("Questionário socioeconômico do ingressante")).toBeVisible();
  await page.getByRole("button", { name: "Ir para minhas inscrições" }).click();

  // histórico atualizado
  const card = page.locator("article.ins", { hasText: "#2027100000162" });
  await expect(card.locator(".chip")).toHaveText("Pré-Matriculado");
  await expect(card.getByRole("button", { name: "Ver contrato" })).toBeVisible();

  // sair
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page).toHaveURL(/\/login/);
});
