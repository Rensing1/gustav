import { expect, test, type Page } from "./support/feature-test";
import { newBrowserContext } from "./support/browser-context";
import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const editor = (page: Page) => page.locator('.learning-markdown-editor__surface [contenteditable="true"]');
const saved = (page: Page) => page.getByText("Entwurf gespeichert – noch nicht abgegeben", { exact: true });

test("@feature-acceptance private drafts survive a fresh login, last writer wins and offline edits recover", async ({ browser }, info) => {
  test.setTimeout(180_000);
  const teacherEmail = e2eEmail("teacher"), learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacher = await newBrowserContext(browser, { baseURL: webBase });
  const first = await newBrowserContext(browser, { baseURL: webBase });
  const second = await newBrowserContext(browser, { baseURL: webBase });
  try {
    const teacherPage = await teacher.newPage(), a = await first.newPage();
    await login(teacherPage, teacherEmail, e2ePassword);
    await login(a, learnerEmail, e2ePassword);
    const seeded = await seedLearnerNavigationCourse(teacherPage, a, "Persönliche Aufgabenentwürfe");
    await a.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await a.getByRole("button", { name: /Grundlagen/ }).click();
    await a.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    await expect(editor(a)).toBeVisible();
    await editor(a).fill("Grüße aus dem ersten Browser. Meine unfertige Antwort.");
    await expect(saved(a)).toBeVisible();
    const taskUrl = a.url();
    const api = `/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/draft`;
    const b = await second.newPage();
    // A separate context has no sessionStorage or authentication cookies to reuse.
    await login(b, learnerEmail, e2ePassword);
    await b.goto(taskUrl);
    await expect(editor(b)).toContainText("Grüße aus dem ersten Browser");
    await editor(b).fill("Auf dem zweiten Gerät weitergeschrieben.");
    await expect(saved(b)).toBeVisible();
    await a.reload();
    await expect(editor(a)).toContainText("Auf dem zweiten Gerät weitergeschrieben.");
    await editor(a).fill("Der zuletzt gespeicherte Text gewinnt.");
    await expect(saved(a)).toBeVisible();
    await b.reload();
    await expect(editor(b)).toContainText("Der zuletzt gespeicherte Text gewinnt.");
    // Some realms grant teachers the student role too; neither role grants access to another learner.
    expect([403, 404]).toContain((await teacherPage.request.get(api)).status());
    expect(await (await a.request.get(api.replace('/draft', '/submissions'))).json()).toEqual([]);

    // Fail only draft writes: real UI, authentication and DB remain in use.
    await a.route(`**${api}`, route => route.request().method() === "PUT" ? route.abort("internetdisconnected") : route.continue());
    await editor(a).fill("Diesen Text trotz Netzausfall behalten.");
    await expect(a.getByText(/Noch nicht auf dem Server gespeichert/)).toBeVisible();
    a.once("dialog", dialog => dialog.dismiss());
    await a.locator('.context-header__back').click();
    await expect(editor(a)).toContainText("Diesen Text trotz Netzausfall behalten.");
    await expect(a).toHaveURL(taskUrl);
    await a.unroute(`**${api}`);
    await a.evaluate(() => window.dispatchEvent(new Event("online")));
    await expect(saved(a)).toBeVisible();
    await b.reload();
    await expect(editor(b)).toContainText("Diesen Text trotz Netzausfall behalten.");
    await editor(b).fill("");
    await expect(saved(b)).toBeVisible();
    await b.reload();
    await expect(editor(b)).toHaveText("");
    await b.screenshot({ path: info.outputPath("draft-saved-empty.png"), fullPage: true });
  } finally { await second.close(); await first.close(); await teacher.close(); }
});
