import { expect, test, type Browser, type BrowserContext, type Page } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedSimulationMaterialCourse } from "./support/seed-data";


const password = e2ePassword;

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}


test("@feature-acceptance teacher publishes and learner resets a sandboxed simulation", async ({ browser }) => {
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
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
