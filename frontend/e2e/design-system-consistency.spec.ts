import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { expect, test, type Page } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

async function toggleTheme(page: Page, theme: "light" | "dark"): Promise<void> {
  await page.getByRole("button", {
    name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true
  }).click();
  await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", theme);
}

test("@feature-acceptance shared design survives role, theme and viewport changes without losing a draft", async ({ browser }) => {
  test.setTimeout(120_000);
  const teacherEmail = e2eEmail("design-teacher");
  const learnerEmail = e2eEmail("design-learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser);
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const seeded = await seedLearnerNavigationCourse(teacher, learner, "Designkonsistenz");

    await teacher.goto("/ui-lab");
    const conversation = teacher.getByTestId("preview-dialog-conversation");
    await expect(conversation.locator(".dialog-message__bubble")).toHaveCount(3);
    await expect(conversation.locator(".dialog-progress")).toHaveCount(0);
    await toggleTheme(teacher, "dark");
    await toggleTheme(teacher, "light");

    await learner.goto(`/learning/courses/${seeded.courseId}`);
    await learner.getByRole("link", { name: seeded.unitTitle }).click();
    await learner.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const editor = learner.locator('.learning-markdown-editor__surface [contenteditable="true"]');
    const draft = "Mein Entwurf bleibt bei einem Darstellungswechsel erhalten.";
    await editor.fill(draft);
    for (const width of [1440, 1024, 390]) {
      await learner.setViewportSize({ width, height: 900 });
      await toggleTheme(learner, "dark");
      await expect(editor).toContainText(draft);
      await toggleTheme(learner, "light");
      await expect(editor).toContainText(draft);
      await expect(learner.getByRole("button", { name: "Rückmeldung einholen" })).toBeVisible();
    }
    await learner.reload();
    await expect(editor).toContainText(draft);
  } finally {
    await Promise.allSettled([learnerContext.close(), teacherContext.close()]);
  }
});
