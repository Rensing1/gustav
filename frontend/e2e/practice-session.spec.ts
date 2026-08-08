import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerPracticeCourse } from "./support/seed-data";

const password = "Passw0rd!e2e";

async function pageFor(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, ignoreHTTPSErrors: true });
  return { context, page: await context.newPage() };
}

test("@feature-acceptance teacher authors and learner completes a native practice cycle", async ({ browser }) => {
  test.setTimeout(120_000);
  const unique = Date.now();
  const teacherEmail = `practice_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `practice_learner_${unique}@${emailDomain}`;
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);
  const teacher = await pageFor(browser);
  const learner = await pageFor(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerPracticeCourse(teacher.page, learner.page, `Practice ${unique}`);

    await learner.page.goto(
      `/learning/practice?course_id=${seeded.courseId}&practice_module_id=${seeded.practiceModuleId}`
    );
    if (await learner.page.getByText("Übungssitzungen sind derzeit nicht freigeschaltet.").isVisible()) {
      test.skip(true, "Practice sessions are intentionally disabled in this deployment.");
    }
    await expect(learner.page.getByRole("heading", { name: "Üben" })).toBeVisible();
    await learner.page.getByRole("button", { name: "Übung starten" }).click();
    await expect(learner.page.getByText("Erkläre, warum ein Test zuerst rot sein soll.")).toBeVisible();
    await learner.page.getByLabel("Deine Antwort").fill(
      "Der rote Test zeigt, dass die neue Funktion wirklich fehlt und der Test nicht nur zufällig grün ist."
    );
    await learner.page.getByRole("button", { name: "Antwort zur Auswertung senden" }).click();
    await expect(learner.page.getByText("Die Rückmeldung wird vorbereitet.")).toBeVisible();
    await expect(learner.page.getByRole("button", { name: "Musterlösung anzeigen" })).toBeVisible({ timeout: 60_000 });
    await learner.page.getByRole("button", { name: "Musterlösung anzeigen" }).click();
    await expect(learner.page.getByText(/Ein zunächst roter Test beweist/)).toBeVisible();
    await learner.page.getByRole("button", { name: "Weiter" }).click();
    await expect(learner.page.getByRole("button", { name: "Antwort zur Auswertung senden" })).toBeVisible();
    await learner.page.getByRole("button", { name: "Sitzung beenden" }).click();
    await expect(learner.page.getByText(/Übungsstapel auswählen|keine offenen Übungsstapel/)).toBeVisible();
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
