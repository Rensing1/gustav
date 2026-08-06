import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import {
  expectLearnerMaterialContrast,
  expectLearnerTaskTheme,
  expectNoViewportOverflow
} from "./support/layout-sanity";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance follows graph, reading and task as one authenticated learning path", async ({ browser }) => {
  test.setTimeout(90_000);
  const unique = Date.now();
  const teacherEmail = `navigation_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `navigation_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Lernweg ${unique}`);

    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await expect(learner.page.getByText("Lernpfad", { exact: true })).toBeVisible();
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    await expect(learner.page).toHaveURL(new RegExp(`\\?module=${seeded.graphModuleId}$`));
    await expect(learner.page.getByText("Dieses Material ist beim ersten Lesen vollständig geöffnet.")).toBeVisible();

    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await expect(learner.page).toHaveURL(
      new RegExp(`\\?module=${seeded.graphModuleId}&task=${seeded.taskId}$`)
    );
    await expect(learner.page.getByRole("button", { name: "← Zurück zu Modul Grundlagen" })).toBeVisible();
    await expectNoViewportOverflow(learner.page);
    await expectLearnerTaskTheme(learner.page, "light");
    const workbench = learner.page.getByRole("region", { name: "Aufgabe bearbeiten" });
    const book = learner.page.getByRole("complementary", { name: "Aufgabe und Kontext" });
    await expect(book.getByRole("heading", { name: "Materialien" })).toBeVisible();
    await expect(book.getByText("Dieses Material ist beim ersten Lesen vollständig geöffnet.")).toBeVisible();
    const secondMaterial = book.getByRole("button", {
      name: `${seeded.secondMaterialTitle} ein- oder ausklappen`
    });
    await expect(secondMaterial).toHaveAttribute("aria-expanded", "false");
    await secondMaterial.click();
    await expect(secondMaterial).toHaveAttribute("aria-expanded", "true");
    await expect(book.getByText("Dieses zweite Modulmaterial beginnt in der Arbeitsfläche eingeklappt.")).toBeVisible();

    await learner.page.getByRole("button", { name: "Dark Mode aktivieren", exact: true }).click();
    await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "dark");
    await expectLearnerTaskTheme(learner.page, "dark");
    await learner.page.setViewportSize({ width: 390, height: 844 });
    await expectNoViewportOverflow(learner.page);
    await expectLearnerTaskTheme(learner.page, "dark");
    await learner.page.setViewportSize({ width: 1280, height: 900 });
    await learner.page.getByRole("button", { name: "Light Mode aktivieren", exact: true }).click();
    await expect(learner.page.locator(".app-shell")).toHaveAttribute("data-theme", "light");

    const answerFormat = learner.page.getByRole("group", { name: "Antwortform" });
    const textEditor = learner.page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    await expect(answerFormat.getByRole("radio", { name: "Text schreiben" })).toBeChecked();
    await textEditor.fill("Dieser Entwurf bleibt beim Wechsel erhalten.");

    await answerFormat.getByRole("radio", { name: "Text schreiben" }).focus();
    await learner.page.keyboard.press("ArrowRight");
    await expect(answerFormat.getByRole("radio", { name: "Datei hochladen" })).toBeChecked();
    await learner.page.getByLabel("Datei auswählen").setInputFiles({
      name: "beleg.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n%%EOF\n")
    });
    await expect(learner.page.getByText("beleg.pdf")).toBeVisible();

    await answerFormat.getByText("Text schreiben", { exact: true }).click();
    await expect(answerFormat.getByRole("radio", { name: "Text schreiben" })).toBeChecked();
    await expect(textEditor).toContainText("Dieser Entwurf bleibt beim Wechsel erhalten.");
    await answerFormat.getByText("Datei hochladen", { exact: true }).click();
    await expect(answerFormat.getByRole("radio", { name: "Datei hochladen" })).toBeChecked();
    await expect(learner.page.getByText("beleg.pdf")).toBeVisible();
    await expect(learner.page.getByRole("group", { name: "Antwortform" })).toHaveCount(1);

    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await learner.page.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await expect(learner.page.getByText("Aufgabe wird weiterbearbeitet.")).toBeVisible();
    await expect(learner.page.getByRole("button", { name: "Zurück zur Aufgabe" })).toBeVisible();
    await learner.page.getByRole("button", { name: /Quellen/ }).click();
    await expect(learner.page).toHaveURL(
      new RegExp(`\\?module=${seeded.graphModuleId}&task=${seeded.taskId}$`)
    );
    await expect(workbench.getByRole("button", { name: "Materialien", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    const contextImage = book.getByRole("img", { name: seeded.contextImageAltText });
    await expect(contextImage).toBeVisible();
    await expect.poll(() => contextImage.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
    await expect(book.getByRole("button", { name: "Modul Quellen schließen" })).toBeVisible();
    await expect(book.getByRole("button", { name: "Modul Grundlagen schließen" })).toHaveCount(0);
    await expectLearnerMaterialContrast(learner.page);

    await book.getByRole("button", { name: "Modul Quellen schließen" }).click();
    await expect(book.getByRole("heading", { name: "Quellen" })).toHaveCount(0);
    const undo = book.getByRole("status");
    await expect(undo).toContainText("Modul „Quellen“ geschlossen.");
    await undo.getByRole("button", { name: "Rückgängig" }).click();
    await expect(contextImage).toBeVisible();

    await workbench.getByRole("button", { name: "Aufgabe", exact: true }).click();
    await expect(textEditor).toContainText("Dieser Entwurf bleibt beim Wechsel erhalten.");
    await answerFormat.getByText("Datei hochladen", { exact: true }).click();
    await expect(learner.page.getByText("beleg.pdf")).toBeVisible();

    await learner.page.getByRole("button", { name: "← Zum Lernpfad" }).click();
    await learner.page.getByRole("button", { name: "Zurück zur Aufgabe" }).click();
    await expect(learner.page).toHaveURL(
      new RegExp(`\\?module=${seeded.graphModuleId}&task=${seeded.taskId}$`)
    );
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
