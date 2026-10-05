import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

import { newBrowserContext } from "./support/browser-context";
import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { login } from "./support/auth";
import { apiHeaders, expectApiOk } from "./support/api";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedSimulationMaterialCourse } from "./support/seed-data";


const password = e2ePassword;
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

test.describe("@feature-acceptance simulation materials", () => {
test("teacher publishes and learner resets a sandboxed simulation", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedSimulationMaterialCourse(teacher.page, learner.page, `Simulation ${unique}`);
    const title = `Zähler ${unique}`;
    const html = `<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Zähler</title></head>
      <body><button id="counter-button">Erhöhen</button><output id="counter">0</output><p id="security"></p>
      <script>
        let value = 0;
        document.getElementById('counter-button').onclick = () => document.getElementById('counter').textContent = String(++value);
        const denied = [];
        try { localStorage.setItem('state', 'x'); } catch { denied.push('storage'); }
        try { parent.document.body; } catch { denied.push('parent'); }
        document.getElementById('security').textContent = denied.sort().join(',');
      </script></body></html>`;

    await teacher.page.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.sectionId}`);
    const createForm = teacher.page.getByTestId("teacher-node-editor-create-slot");
    await createForm.getByLabel("Materialtyp").selectOption("simulation");
    await createForm.getByLabel("Titel").fill("Bundestag-Sitzverteilung");
    await createForm.getByLabel("Kurze Orientierung").fill("Untersuche zuerst die **Fraktionen**.");
    await createForm.getByLabel("HTML-Simulation").setInputFiles({
      name: "bundestag.html",
      mimeType: "text/html",
      buffer: Buffer.from(
        '<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Bundestag</title></head><body><img src="https://example.org/logo.png"><script>fetch("https://example.org/data.json")</script></body></html>',
        "utf-8"
      )
    });
    await createForm.getByRole("button", { name: "Material hinzufügen" }).click();

    const rejection = createForm.getByRole("alert");
    await expect(rejection).toContainText("Simulation konnte nicht hinzugefügt werden");
    await expect(rejection).toContainText("erneut aus");
    await expect(rejection).toContainText("example.org");
    await expect(createForm.getByLabel("Titel")).toHaveValue("Bundestag-Sitzverteilung");
    await expect(createForm.getByLabel("Kurze Orientierung")).toHaveValue("Untersuche zuerst die **Fraktionen**.");
    await expect(createForm.getByLabel("HTML-Simulation")).toHaveValue("");
    await expect
      .poll(() => createForm.getByLabel("Kurze Orientierung").evaluate((node) => getComputedStyle(node).maxHeight))
      .toBe("192px");

    await createForm.getByLabel("Titel").fill(title);
    await createForm.getByLabel("Kurze Orientierung").fill("Klicke auf **Erhöhen** und beobachte den Zähler.");
    await createForm.getByLabel("HTML-Simulation").setInputFiles({
      name: "zaehler.html",
      mimeType: "text/html",
      buffer: Buffer.from(html, "utf-8")
    });
    await createForm.getByRole("button", { name: "Material hinzufügen" }).click();

    await expect(teacher.page.getByText("Material angelegt.")).toBeVisible();
    await expect(teacher.page.locator(".workspace-node-editor-simulation-frame")).toHaveCount(0);
    await teacher.page.getByRole("button", { name: "Vorschau starten" }).click();
    await expect(teacher.page.locator(".workspace-node-editor-simulation-frame")).toHaveAttribute("sandbox", "allow-scripts");

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.getByText("Klicke auf Erhöhen und beobachte den Zähler.")).toBeVisible();
    await expect(learner.page.locator(".learning-material-simulation__frame")).toHaveCount(0);
    await learner.page.getByRole("button", { name: "Simulation starten" }).click();
    const frame = learner.page.frameLocator(".learning-material-simulation__frame");
    await expect(frame.locator("#counter")).toHaveText("0");
    await frame.locator("#counter-button").click();
    await expect(frame.locator("#counter")).toHaveText("1");
    await expect(frame.locator("#security")).toHaveText("parent,storage");

    const simulationUrl = await learner.page.locator(".learning-material-simulation__frame").getAttribute("src");
    expect(simulationUrl).toBeTruthy();
    const response = await learner.page.request.get(`${webBase}${simulationUrl}`);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-security-policy"]).toContain("sandbox allow-scripts");
    expect(response.headers()["content-security-policy"]).toContain("connect-src 'none'");

    await learner.page.getByRole("button", { name: "Zurücksetzen" }).click();
    await expect(learner.page.frameLocator(".learning-material-simulation__frame").locator("#counter")).toHaveText("0");
    await learner.page.getByRole("button", { name: "Simulation schließen" }).click();
    await expect(learner.page.locator(".learning-material-simulation__frame")).toHaveCount(0);

    const hide = await teacher.page.request.patch(
      `${webBase}/api/teaching/courses/${seeded.courseId}/modules/${seeded.moduleId}/sections/${seeded.sectionId}/visibility`,
      { headers: apiHeaders(), data: { visible: false } }
    );
    await expectApiOk(hide);
    const hidden = await learner.page.request.get(`${webBase}${simulationUrl}`);
    expect(hidden.status()).toBe(404);
    expect(hidden.headers()["cache-control"]).toBe("private, no-store");
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});

test("CLI uploads a canonical HTML simulation for teacher and learner", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = e2eEmail("cli.teacher");
  const learnerEmail = e2eEmail("learner");
  const tokenLabel = `Simulation CLI ${unique}`;
  const title = `CLI-Zähler ${unique}`;
  const filename = `cli-zaehler-${unique}.html`;
  const html = Buffer.from(
    `<!doctype html><html lang="de"><head><meta charset="utf-8"><title>CLI-Zähler</title></head>
    <body><button id="increment">Erhöhen</button><output id="value">0</output>
    <script>let value=0;document.getElementById('increment').onclick=()=>document.getElementById('value').textContent=String(++value);</script>
    </body></html>`,
    "utf8"
  );
  const configRoot = mkdtempSync(resolve(tmpdir(), "gustav-simulation-cli-"));

  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);
  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedSimulationMaterialCourse(
      teacher.page,
      learner.page,
      `CLI-Simulation ${unique}`
    );

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
    writeFileSync(source, html);
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
      title,
      "--kind",
      "simulation",
      "--mime-type",
      "text/html",
      "--body-md",
      "Starte den **CLI-Zähler**."
    ]);

    await teacher.page.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.sectionId}`);
    const teacherCard = teacher.page.locator(".workspace-node-editor-entry").filter({ hasText: title });
    await expect(teacherCard).toBeVisible();
    await teacherCard.getByRole("button").first().click();
    await teacherCard.getByRole("button", { name: "Vorschau starten" }).click();
    const teacherFrame = teacherCard.frameLocator(".workspace-node-editor-simulation-frame");
    await expect(teacherFrame.locator("#value")).toHaveText("0");

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    const learnerCard = learner.page.locator(".learning-work-item--material").filter({ hasText: title });
    await expect(learnerCard.getByText("Starte den CLI-Zähler.")).toBeVisible();
    await learnerCard.getByRole("button", { name: "Simulation starten" }).click();
    const learnerFrame = learnerCard.frameLocator(".learning-material-simulation__frame");
    await expect(learnerFrame.locator("#value")).toHaveText("0");
    await learnerFrame.locator("#increment").click();
    await expect(learnerFrame.locator("#value")).toHaveText("1");

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
