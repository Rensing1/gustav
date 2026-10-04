import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

import { newBrowserContext } from "./support/browser-context";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedSimulationMaterialCourse } from "./support/seed-data";

const projectRoot = resolve(process.cwd(), "..");
const python = resolve(projectRoot, ".venv/bin/python");

// CLI tokens are revealed exactly once and must never be persisted in a trace.
test.use({ trace: "off" });

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await newBrowserContext(browser, { baseURL: webBase });
  return { context, page: await context.newPage() };
}

function runCli(configRoot: string, args: string[], input?: string): string {
  const localCa = resolve(projectRoot, ".tmp/caddy-root.crt");
  return execFileSync(python, ["-m", "backend.tools.gustav_cli", ...args], {
    cwd: projectRoot,
    env: {
      ...process.env,
      GUSTAV_CONFIG_HOME: configRoot,
      ...(existsSync(localCa) ? { SSL_CERT_FILE: localCa } : {})
    },
    encoding: "utf8",
    input
  });
}

async function expectMaterialDownload(
  page: Page,
  title: string,
  expectedFilename: string,
  expectedBytes: Buffer
): Promise<void> {
  const card = page.locator(".learning-work-item--material").filter({ hasText: title });
  await expect(card).toBeVisible();
  const link = card.getByRole("link", { name: "Herunterladen" });
  await expect(link).toHaveAttribute("href", /disposition=attachment/);
  await expect(link).not.toHaveAttribute("target", "_blank");

  const href = await link.getAttribute("href");
  expect(href).toBeTruthy();
  const response = await page.request.get(`${webBase}${href}`);
  expect(response.status()).toBe(200);
  const contentDisposition = response.headers()["content-disposition"];
  expect(contentDisposition).toContain("attachment");
  expect(contentDisposition).toContain(
    `filename*=UTF-8''${encodeURIComponent(expectedFilename)}`
  );
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  expect(Buffer.from(await response.body())).toEqual(expectedBytes);

  const downloadPromise = page.waitForEvent("download");
  await link.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);
  const downloadPath = await download.path();
  expect(downloadPath).toBeTruthy();
  expect(readFileSync(downloadPath!)).toEqual(expectedBytes);
}

test.describe("@feature-acceptance program file materials", () => {
test("teacher uploads a Scratch material and learner downloads exact bytes", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  const title = `Scratch-Projekt ${unique}`;
  const filename = `программа-${unique}.sb3`;
  const content = Buffer.from(`PK\u0003\u0004GUSTAV-Scratch-${unique}`, "utf8");

  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, e2ePassword);
    await login(learner.page, learnerEmail, e2ePassword);
    const seeded = await seedSimulationMaterialCourse(teacher.page, learner.page, `Dateimaterial ${unique}`);

    await teacher.page.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.sectionId}`);
    const createForm = teacher.page.getByTestId("teacher-node-editor-create-slot");
    await createForm.getByLabel("Materialtyp").selectOption("file");
    await createForm.getByLabel("Titel").fill(title);
    await createForm.getByLabel("Datei", { exact: true }).setInputFiles({
      name: filename,
      mimeType: "application/x.scratch.sb3",
      buffer: content
    });
    await createForm.getByRole("button", { name: "Material hinzufügen" }).click();
    await expect(teacher.page.getByText("Material angelegt.")).toBeVisible();

    const teacherCard = teacher.page.locator(".workspace-node-editor-entry").filter({ hasText: title });
    await expect(teacherCard.getByRole("link", { name: "Herunterladen" })).toBeVisible();
    await expect(teacherCard.getByRole("link", { name: "Vorschau öffnen" })).toHaveCount(0);

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expectMaterialDownload(learner.page, title, filename, content);
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});

test("CLI uploads Python material and learner downloads it", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("cli.teacher");
  const learnerEmail = e2eEmail("learner");
  const tokenLabel = `Material CLI ${unique}`;
  const title = `Python-Programm ${unique}`;
  const filename = `sortieren-${unique}.py`;
  const content = Buffer.from(`print("GUSTAV ${unique}")\n`, "utf8");
  const configRoot = mkdtempSync(resolve(tmpdir(), "gustav-material-cli-"));

  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, e2ePassword);
    await login(learner.page, learnerEmail, e2ePassword);
    const seeded = await seedSimulationMaterialCourse(teacher.page, learner.page, `CLI-Dateimaterial ${unique}`);

    await teacher.page.goto("/profile");
    await teacher.page.getByLabel("Tokenname").fill(tokenLabel);
    await teacher.page.getByLabel("read", { exact: true }).check();
    await teacher.page.getByLabel("write", { exact: true }).check();
    await teacher.page.getByRole("button", { name: "CLI-Token erstellen" }).click();
    await expect(teacher.page.getByText("Token jetzt sicher kopieren")).toBeVisible();
    const rawToken = (await teacher.page.locator("code").first().textContent())?.trim();
    expect(rawToken).toBeTruthy();

    runCli(configRoot, ["auth", "configure", "--base-url", webBase, "--token-stdin"], `${rawToken}\n`);
    const source = resolve(configRoot, filename);
    writeFileSync(source, content);
    runCli(configRoot, [
      "materials",
      "upload",
      "--unit-id",
      seeded.unitId,
      "--section-id",
      seeded.sectionId,
      "--file",
      source,
      "--title",
      title
    ]);

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expectMaterialDownload(learner.page, title, filename, content);

    await teacher.page.goto("/profile");
    const tokenRow = teacher.page.locator("form").filter({ hasText: tokenLabel });
    await tokenRow.getByRole("button", { name: "CLI-Token widerrufen" }).click();
    await expect(teacher.page.getByText("Das CLI-Token wurde widerrufen.")).toBeVisible();
  } finally {
    rmSync(configRoot, { recursive: true, force: true });
    await learner.context.close();
    await teacher.context.close();
  }
});
});
