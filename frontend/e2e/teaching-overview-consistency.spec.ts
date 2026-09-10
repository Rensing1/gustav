import { currentUserSub, login } from "./support/auth";
import { apiHeaders, expectApiOk } from "./support/api";
import { newBrowserContext } from "./support/browser-context";
import { expectDesignContrast } from "./support/design-contrast";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test, type Page, type TestInfo } from "./support/feature-test";
import { ensureLearnerUserProfile, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse } from "./support/seed-data";
import { prepareCompletedFeedbackDraft } from "./support/submission-finalization-fixture";

async function pictures(page: Page, info: TestInfo, name: string) {
  for (const theme of ["light", "dark"]) {
    const toggle = page.getByRole("button", { name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true });
    if (await toggle.count()) await toggle.click();
    for (const width of [1440, 1024, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
      // Measure settled theme/hover colors, not an intermediate CSS transition.
      await expect(async () => expectDesignContrast(page.locator("main h2, main h3, main .workspace-note, main .workspace-link-action, .live-task-strip__item, .workspace-tab"))).toPass({ timeout: 2000 });
      for (const panel of await page.locator(".workspace-panel--flat, .live-panel, .live-table-panel").all()) {
        await expect(panel).toHaveCSS("box-shadow", "none");
        await expect(panel).toHaveCSS("border-top-left-radius", "0px");
      }
      for (const action of await page.locator(".live-task-strip__item").all()) {
        expect((await action.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      }
      for (const tab of await page.getByRole("tab").all()) {
        await tab.hover();
        await tab.focus();
        await page.keyboard.press("Tab");
        await page.keyboard.press("Shift+Tab");
        await expect(tab).toBeFocused();
        await expect(tab).not.toHaveCSS("outline-style", "none");
        await expect(async () => expectDesignContrast(tab)).toPass({ timeout: 2000 });
      }
      // Focusing a detail tab scrolls the document. Reset only the camera for
      // full-page evidence so the sticky header is captured at the page top.
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: info.outputPath(`${name}-${width}-${theme}.png`), fullPage: true, animations: "disabled" });
    }
  }
}

test("@feature-acceptance teacher follows diagnostics to live with 24 learners and long labels", async ({ browser }, info) => {
  test.setTimeout(240_000);
  const teacherEmail = e2eEmail("teacher"), learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUserProfile(learnerEmail, e2ePassword, { firstName: "Lernende 01", lastName: "Beispiel-Doppelname für die Lesbarkeitsprüfung" });
  const tc = await newBrowserContext(browser), lc = await newBrowserContext(browser);
  tc.setDefaultTimeout(15_000); lc.setDefaultTimeout(15_000);
  const teacher = await tc.newPage(), learner = await lc.newPage();
  try {
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const seeded = await seedLearnerNavigationCourse(teacher, learner, "Digitale Systeme und demokratische Grundrechte mit sehr ausführlicher Bezeichnung");
    const learnerSub = await currentUserSub(learner);
    await teacher.goto("/diagnostics");
    await expect(teacher.getByRole("combobox", { name: "Kurs", exact: true })).toBeVisible();
    await teacher.getByRole("combobox", { name: "Kurs", exact: true }).selectOption(seeded.courseId);
    await expect(teacher.getByRole("link", { name: "Kursmatrix öffnen", exact: true })).toBeVisible();
    await pictures(teacher, info, "entry");

    const subjects = [learnerSub];
    for (let number = 2; number <= 24; number++) {
      const sub = await ensureLearnerUserProfile(e2eEmail(`learner-${number}`), e2ePassword, {
        firstName: `Lernende ${String(number).padStart(2, "0")}`, lastName: "Beispiel-Doppelname für die Lesbarkeitsprüfung"
      });
      subjects.push(sub);
      await expectApiOk(await teacher.request.post(`${webBase}/api/teaching/courses/${seeded.courseId}/members`, {
        headers: apiHeaders(), data: { student_sub: sub }
      }), 201);
    }
    await teacher.getByRole("link", { name: "Kursmatrix öffnen", exact: true }).click();
    await expect(teacher.locator("main")).not.toContainText("Drilldowns");
    const matrix = teacher.getByRole("region", { name: "Kursmatrix" });
    await expect(matrix.locator("tbody tr")).toHaveCount(24);
    await matrix.locator("tbody tr").last().scrollIntoViewIfNeeded();
    await expect(matrix.locator("tbody tr").last()).toBeVisible();
    await pictures(teacher, info, "matrix");
    await matrix.focus();
    await teacher.keyboard.press("ArrowRight");
    await expect.poll(() => matrix.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);
    await matrix.evaluate((node) => { node.scrollLeft = 0; });
    await matrix.locator(`a[href="/diagnostics/learners/${learnerSub}"]`).click();
    await expect(teacher.locator("body")).toContainText("Aufgaben mit Abgabe");
    await expect(teacher.locator("main")).not.toContainText("Drilldowns");
    await pictures(teacher, info, "profile");
    const liveLink = teacher.locator(`a[href*="unit_id=${seeded.unitId}"]`);
    const target = new URL((await liveLink.getAttribute("href"))!, webBase);
    expect(target.pathname).toBe("/live");
    expect(target.searchParams.get("course_id")).toBe(seeded.courseId);
    expect(target.searchParams.get("student_sub")).toBe(learnerSub);
    await liveLink.click();
    const details = teacher.getByRole("complementary", { name: "Schülerdetail" });
    await expect(details).toContainText("Keine Abgabe");
    await expect(teacher.getByRole("region", { name: "Klassenübersicht" }).locator("tbody tr")).toHaveCount(24);
    const lastRow = teacher.getByRole("region", { name: "Klassenübersicht" }).locator("tbody tr").last();
    await lastRow.scrollIntoViewIfNeeded();
    await expect(lastRow).toBeVisible();
    await lastRow.getByRole("link").first().click();
    await expect(details).toContainText("Keine Abgabe");
    await teacher.goto(target.toString());
    await expect(teacher.getByRole("navigation", { name: "Aufgaben der Lerneinheit" })).toContainText("Grundlagen");
    await expect(teacher.getByRole("navigation", { name: "Aufgaben der Lerneinheit" })).toContainText("Quellen");
    await pictures(teacher, info, "live-empty");
    const liveTable = teacher.getByRole("region", { name: "Klassenübersicht" });
    await liveTable.focus();
    await teacher.keyboard.press("ArrowRight");
    await expect.poll(() => liveTable.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);
    await liveTable.evaluate((node) => { node.scrollLeft = 0; });

    // Only the external feedback result is a fixture; finalization and the
    // teacher's persisted read-back use the real authenticated application.
    await prepareCompletedFeedbackDraft({ courseId: seeded.courseId, taskId: seeded.taskId, learnerSub, textBody: "Beide Materialien zeigen unterschiedliche Perspektiven auf digitale Grundrechte." });
    await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}&task=${seeded.taskId}&panel=result`);
    await learner.getByRole("button", { name: "Endgültig abgeben" }).click();
    await expect(learner.locator(".learning-task-feedback-status").getByRole("status")).toContainText("Aufgabe abgegeben");
    await teacher.reload();
    await teacher.getByRole("navigation", { name: "Aufgaben der Lerneinheit" }).getByRole("link", { name: /^Grundlagen · Aufgabe 1:/ }).click();
    await expect(details).toContainText("Beide Materialien zeigen unterschiedliche Perspektiven");
    await pictures(teacher, info, "live-submission");
    await teacher.getByRole("tab", { name: "Rückmeldung", exact: true }).click();
    await expect(teacher.getByRole("tabpanel", { name: "Rückmeldung" })).toContainText("Die Fassung wurde geprüft");
    await pictures(teacher, info, "live-feedback");
    await teacher.getByRole("tab", { name: "Auswertung", exact: true }).click();
    await expect(teacher.getByRole("tabpanel", { name: "Auswertung" })).toBeVisible();
    await pictures(teacher, info, "live-evaluation");

    await teacher.goto(`/teaching/courses/${seeded.courseId}/members`);
    await expect(teacher.locator(".workspace-list > a")).toHaveCount(24);
    for (const sub of subjects) await expect(teacher.locator("main")).not.toContainText(sub);
    await expect(teacher.locator("main")).not.toContainText("SvelteKit");
    await pictures(teacher, info, "members");
    // These BFF endpoints require server-side bearer transport, not browser
    // cookies. Check the real learner UI guard; API role denial has DB coverage.
    expect(await currentUserSub(learner)).toBe(learnerSub);
    await learner.goto(`/diagnostics/courses/${seeded.courseId}`);
    await expect(learner).toHaveURL(/\/learning$/);
    await learner.goto(`/diagnostics/learners/${learnerSub}`);
    await expect(learner).toHaveURL(/\/learning$/);
    expect(await currentUserSub(learner)).toBe(learnerSub);
  } finally {
    await lc.close(); await tc.close();
  }
});
