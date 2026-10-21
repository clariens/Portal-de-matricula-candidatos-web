import { expect, test, type Page } from "@playwright/test";

/** Gera no navegador uma imagem PNG com as linhas de texto (documento fictício) para o OCR real ler. */
async function documento(page: Page, linhas: string[], nome: string) {
  const dataUrl = await page.evaluate((ls) => {
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
    return cv.toDataURL("image/png");
  }, linhas);
  return { name: nome, mimeType: "image/png", buffer: Buffer.from(dataUrl.split(",")[1], "base64") };
}

const docRow = (page: Page, nome: string) => page.locator(".doc", { has: page.getByRole("heading", { name: nome, exact: true }) });

test("fluxo completo de matrícula (mock)", async ({ page }) => {
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

  // etapa 2: documentos com OCR real
  await expect(page.getByRole("heading", { name: "Seus documentos" })).toBeVisible();
  const nome = "ANA BEATRIZ ROCHA";
  await page.locator("#up-05").setInputFiles(await documento(page, ["CADASTRO DE PESSOA FISICA", `NOME ${nome}`, "CPF 123.456.789-09"], "cpf.png"));
  await expect(docRow(page, "CPF").locator(".chip")).toHaveText("Pronto para envio");

  await page.locator("#up-04").setInputFiles(await documento(page, ["REGISTRO GERAL", `NOME ${nome}`, "NASCIMENTO 14/03/2004"], "rg.png"));
  await expect(docRow(page, "Documento de Identidade").locator(".chip")).toHaveText("Pronto para envio");

  await page.locator("#up-03").setInputFiles(await documento(page, ["HISTORICO ESCOLAR", `ALUNO ${nome}`, "CONCLUSAO EM 2021"], "hist.png"));
  await expect(docRow(page, "Certificado de Conclusão / Histórico Escolar").locator(".chip")).toHaveText("Pronto para envio");

  // declaração com conclusão após 2022 → divergente, exige confirmação para conferência manual
  const decl = docRow(page, "Declaração de Conclusão do Ensino Médio até 31/12/2022");
  await page.locator("#up-02").setInputFiles(await documento(page, ["DECLARACAO DE CONCLUSAO", `ALUNO ${nome}`, "CONCLUIU EM 2023"], "decl.png"));
  await expect(decl.locator(".chip")).toHaveText("Divergente");
  await expect(decl).toContainText("aceita conclusões até 31/12/2022");
  await decl.getByRole("button", { name: "Enviar para conferência manual" }).click();
  await expect(decl.locator(".chip")).toHaveText("Pronto para envio");
  await expect(decl).toContainText("Será conferido pela secretaria.");

  // opcional anexado e removido
  const vacina = docRow(page, "Cartão de Vacina");
  await page.locator("#up-14").setInputFiles({ name: "foto.png", mimeType: "image/png", buffer: (await documento(page, ["CARTAO DE VACINA", `NOME ${nome}`], "v.png")).buffer });
  await expect(vacina.locator(".chip")).not.toHaveText("Pendente");
  await vacina.locator(".chip").filter({ hasText: /Pronto para envio|Verificar|Divergente/ }).waitFor();
  if (await vacina.getByRole("button", { name: "Enviar para conferência manual" }).isVisible()) await vacina.getByRole("button", { name: "Enviar para conferência manual" }).click();
  await vacina.getByRole("button", { name: "Remover" }).click();
  await expect(vacina.locator(".chip")).toHaveCount(0);

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
