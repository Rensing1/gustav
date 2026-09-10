import { login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { expect, test, type Browser, type Page } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedLearnerNavigationCourse, seedLearnerPracticeCourse } from "./support/seed-data";
import { contrastRatio, expectNoViewportOverflow } from "./support/layout-sanity";

async function toggleTheme(page: Page, theme: "light" | "dark"): Promise<void> {
  await page.getByRole("button", {
    name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true
  }).click();
  await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", theme);
}

async function verifyDraftSurvivesThemeChanges(browser: Browser): Promise<void> {
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
}

test("@feature-acceptance catalogs practice profile and creation dialogs share accessible controls", async ({ browser }, testInfo) => {
  test.setTimeout(180_000);
  await test.step("Both roles keep the learner draft across theme and viewport changes", () => verifyDraftSurvivesThemeChanges(browser));
  const teacherEmail = e2eEmail("controls-teacher");
  const learnerEmail = e2eEmail("controls-learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser);
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    await seedLearnerPracticeCourse(teacher, learner, "Design-Bedienelemente");
    for (const theme of ["light", "dark"] as const) {
      for (const width of [1440, 1024, 390, 320]) {
        await teacher.setViewportSize({ width, height: 900 });
        await learner.setViewportSize({ width, height: 900 });
        for (const route of ["/teaching/courses", "/teaching/units"]) {
          await teacher.goto(route);
          const themeButton = teacher.getByRole("button", { name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true });
          if (await themeButton.count()) await themeButton.click();
          await expect(teacher.locator(".app-shell")).toHaveAttribute("data-theme", theme);
          const search = teacher.getByRole("textbox", { name: "Suche", exact: true }).or(teacher.getByRole("searchbox", { name: "Suche", exact: true }));
          expect((await search.boundingBox())!.height).toBeGreaterThanOrEqual(44);
          await search.fill("Kein passender Eintrag");
          if (route.endsWith("courses")) await teacher.getByRole("button", { name: "Filtern", exact: true }).click();
          await expect(teacher.getByText(route.endsWith("courses") ? "Keine aktiven Kurse für diese Auswahl." : "Noch keine passenden Lerneinheiten gefunden.", { exact: true })).toBeVisible();
          await search.fill("Design-Bedienelemente");
          if (route.endsWith("courses")) await teacher.getByRole("button", { name: "Filtern", exact: true }).click();
          await expect(teacher.getByRole("link", { name: /Design-Bedienelemente/ }).first()).toBeVisible();
          await teacher.screenshot({ path: testInfo.outputPath(`${route.endsWith("courses") ? "course" : "unit"}-catalog-${theme}-${width}.png`), fullPage: true });
          const trigger = teacher.getByRole("button", { name: route.endsWith("courses") ? "Neuer Kurs" : "Neue Lerneinheit", exact: true });
          await trigger.click();
          const dialog = teacher.getByRole("dialog");
          await expect(dialog).toBeVisible();
          await expect.poll(() => dialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);
          await expect(dialog.locator('button[type="submit"]')).toHaveClass(/workspace-link-action--primary/);
          await dialog.getByRole("textbox", { name: "Titel", exact: true }).fill("Unveröffentlichter Entwurf");
          const lastAction = dialog.getByRole("button").last();
          await lastAction.focus();
          await teacher.keyboard.press("Tab");
          await expect.poll(() => dialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);
          await teacher.keyboard.press("Shift+Tab");
          await expect(lastAction).toBeFocused();
          for (const field of await dialog.locator('input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"]), button').all()) {
            expect((await field.boundingBox())!.height).toBeGreaterThanOrEqual(44);
          }
          for (const radio of await dialog.getByRole("radio").all()) {
            expect((await radio.boundingBox())!.width).toBeLessThan(30);
          }
          await expectNoViewportOverflow(teacher);
          await teacher.screenshot({ path: testInfo.outputPath(`${route.endsWith("courses") ? "course" : "unit"}-dialog-${theme}-${width}.png`) });
          await teacher.keyboard.press("Escape");
          await expect(dialog).toHaveCount(0);
          await expect(trigger).toBeFocused();
          if (route.endsWith("units")) {
            const row = teacher.locator(".teacher-units-catalog-row").first();
            await expect(row.getByRole("link", { name: "Löschen", exact: true })).toBeHidden();
            await row.locator("summary").filter({ hasText: "Weitere Aktionen" }).click();
            await row.getByRole("link", { name: "Löschen", exact: true }).click();
            const confirmation = teacher.getByRole("dialog", { name: "Endgültig löschen" });
            await expect(confirmation).toBeVisible();
            await confirmation.getByRole("link", { name: "Abbrechen", exact: true }).click();
            await expect(confirmation).toHaveCount(0);
          }
        }
        await learner.goto("/learning/practice");
        const learnerTheme = learner.getByRole("button", { name: theme === "dark" ? "Dark Mode aktivieren" : "Light Mode aktivieren", exact: true });
        if (await learnerTheme.count()) await learnerTheme.click();
        const stack = learner.locator(".practice-stack-card").first();
        if (!(await stack.getByRole("checkbox").isChecked())) await stack.click();
        await expect(stack.getByRole("checkbox")).toBeChecked();
        const start = learner.getByRole("button", { name: "1 Aufgabe starten", exact: true });
        await expect(start).toBeEnabled();
        await start.hover();
        await start.focus();
        const palette = await start.evaluate((node) => {
          const css = getComputedStyle(node);
          return { font: css.fontFamily, radius: css.borderRadius, fg: css.color, bg: css.backgroundColor, height: node.getBoundingClientRect().height };
        });
        expect(palette.font).toContain("monospace");
        expect(palette.radius).toBe("0px");
        expect(palette.height).toBeGreaterThanOrEqual(44);
        expect(contrastRatio(palette.fg, palette.bg)).toBeGreaterThanOrEqual(4.5);
        await expectNoViewportOverflow(learner);
        await learner.evaluate(() => scrollTo(0, 0));
        await learner.screenshot({ path: testInfo.outputPath(`practice-controls-${theme}-${width}.png`), fullPage: true });
        await teacher.goto("/profile");
        expect((await teacher.getByRole("textbox", { name: "Anzeigename", exact: true }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
        await expectNoViewportOverflow(teacher);
      }
    }
  } finally {
    await Promise.allSettled([learnerContext.close(), teacherContext.close()]);
  }
});
