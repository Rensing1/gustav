import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { expect, test } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

test("@feature-acceptance keeps a touch resize that starts on the visible task divider grip", async ({ browser }) => {
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);

  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser, {
    hasTouch: true,
    viewport: { width: 1024, height: 768 }
  });
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const { courseId, unitId } = await seedLearnerNavigationCourse(teacher, learner, "Spaltentrenner");

    await learner.goto(`/learning/courses/${courseId}/units/${unitId}`);
    await learner.getByRole("button", { name: /Grundlagen/ }).click();
    await learner.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const workbench = learner.getByRole("region", { name: "Aufgabe bearbeiten" });
    const contextPane = workbench.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const separator = workbench.getByRole("separator", { name: "Spaltenbreite anpassen" });
    const grip = separator.locator(".learner-task-split-divider__grip");
    await expect(grip).toBeVisible();

    const width = () => contextPane.evaluate((pane) => pane.getBoundingClientRect().width);
    const initialWidth = await width();
    const start = await grip.evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      const x = Math.round(bounds.x + bounds.width / 2);
      const y = Math.round(bounds.y + bounds.height / 2);
      if (document.elementFromPoint(x, y) !== element) {
        throw new Error("Touch must start on the visible divider grip");
      }
      return { x, y };
    });

    const touch = await learnerContext.newCDPSession(learner);
    await touch.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [start] });
    for (const distance of [10, 25, 60, 85]) {
      await touch.send("Input.dispatchTouchEvent", {
        type: "touchMove",
        touchPoints: [{ x: start.x + distance, y: start.y }]
      });
    }
    await touch.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });

    await expect.poll(width).toBeGreaterThan(initialWidth + 50);
    const resizedWidth = await width();
    await learner.reload();
    await expect.poll(async () => Math.abs((await width()) - resizedWidth)).toBeLessThan(1);
  } finally {
    await learnerContext.close();
    await teacherContext.close();
  }
});
