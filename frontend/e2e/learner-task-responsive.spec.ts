import { expect, test, type Browser, type BrowserContext, type Locator, type Page } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { seedLearnerNavigationCourse } from "./support/seed-data";

const password = e2ePassword;

async function scrollSurfaceWithKeyboard(page: Page, surface: Locator, edge: "start" | "end"): Promise<void> {
  await surface.evaluate((element) => element.setAttribute("tabindex", "-1"));
  await surface.focus();
  await page.keyboard.press(edge === "end" ? "End" : "Home");
}

async function authenticatedPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ baseURL: webBase, hasTouch: true });
  return { context, page: await context.newPage() };
}

async function verifyIndependentWheelScrolling(browser: Browser, taskUrl: string, learnerEmail: string): Promise<void> {
  const context = await browser.newContext({ baseURL: webBase });
  const page = await context.newPage();
  try {
    await login(page, learnerEmail, password);
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto(taskUrl);
    const workbench = page.getByRole("region", { name: "Aufgabe bearbeiten" });
    const contextScroll = workbench.locator(".learner-task-context__scroll");
    const workScroll = workbench.locator(".learner-task-workbench__main");
    await page.addStyleTag({
      content: `
        .learner-task-context__scroll::after,
        .learner-task-workbench__main::after {
          content: "";
          display: block;
          height: 80rem;
        }
      `
    });
    await expect.poll(() => contextScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight)).toBeGreaterThan(500);
    await expect.poll(() => workScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight)).toBeGreaterThan(500);

    const contextBox = await contextScroll.boundingBox();
    const workBox = await workScroll.boundingBox();
    expect(contextBox).not.toBeNull();
    expect(workBox).not.toBeNull();
    if (!contextBox || !workBox) return;

    const interactionY = Math.min(contextBox.y + contextBox.height, workBox.y + workBox.height, 768) - 80;
    await page.mouse.move(contextBox.x + contextBox.width - 8, interactionY);
    await page.mouse.wheel(0, 500);
    await expect.poll(() => contextScroll.evaluate((surface) => surface.scrollTop)).toBeGreaterThan(0);
    expect(await workScroll.evaluate((surface) => surface.scrollTop)).toBe(0);

    const leftScrollTop = await contextScroll.evaluate((surface) => surface.scrollTop);
    await page.mouse.move(workBox.x + 8, interactionY);
    await page.mouse.wheel(0, 500);
    await expect.poll(() => workScroll.evaluate((surface) => surface.scrollTop)).toBeGreaterThan(0);
    expect(await contextScroll.evaluate((surface) => surface.scrollTop)).toBe(leftScrollTop);
  } finally {
    await context.close();
  }
}

test("@feature-detail keeps the learner task desk split on landscape iPads", async ({ browser, browserName }) => {
  const unique = Date.now();
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, password);
  await ensureLearnerUser(learnerEmail, password);

  const teacher = await authenticatedPage(browser);
  const learner = await authenticatedPage(browser);
  try {
    await login(teacher.page, teacherEmail, password);
    await login(learner.page, learnerEmail, password);
    const seeded = await seedLearnerNavigationCourse(teacher.page, learner.page, `Responsive Aufgabe ${unique}`);

    await learner.page.setViewportSize({ width: 1024, height: 768 });
    await learner.page.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}`);
    await learner.page.getByRole("button", { name: /Grundlagen/ }).click();
    const taskRow = learner.page.locator(".learning-task-row").first();
    await expect(taskRow.getByText("Weitere Angaben in der Aufgabe")).toBeVisible();
    await learner.page.getByRole("button", { name: "Aufgabe 1 beginnen" }).click();
    const taskUrl = learner.page.url();

    const workbench = learner.page.getByRole("region", { name: "Aufgabe bearbeiten" });
    const context = workbench.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const task = workbench.getByRole("main", { name: "Bearbeitung" });
    const separator = workbench.getByRole("separator", { name: "Spaltenbreite anpassen" });
    const switcher = workbench.getByRole("navigation", { name: "Arbeitsbereich wählen" });
    const compactStatement = workbench.getByRole("region", { name: "Vollständige Aufgabenstellung" });

    await expect(context).toBeVisible();
    await expect(task).toBeVisible();
    await expect(separator).toBeVisible();
    await expect(switcher).toBeHidden();
    await expect(compactStatement).toBeHidden();
    await expect(context.getByText("Begründe abschließend, welche Position dich überzeugt.")).toBeVisible();
    const landscapeTracks = await workbench.locator(".learner-task-workbench__desk").evaluate(
      (desk) => getComputedStyle(desk).gridTemplateColumns.split(" ").length
    );
    expect(landscapeTracks).toBe(3);
    await expectNoViewportOverflow(learner.page);

    const deskBox = await workbench.locator(".learner-task-workbench__desk").boundingBox();
    const separatorBox = await separator.boundingBox();
    expect(deskBox).not.toBeNull();
    expect(separatorBox).not.toBeNull();
    if (deskBox && separatorBox) {
      await learner.page.mouse.move(separatorBox.x + separatorBox.width / 2, separatorBox.y + 80);
      await learner.page.mouse.down();
      await learner.page.mouse.move(deskBox.x + deskBox.width * 0.6, separatorBox.y + 80);
      await learner.page.mouse.up();
    }
    await expect(separator).toHaveAttribute("aria-valuenow", "60");

    await learner.page.reload();
    const restoredWorkbench = learner.page.getByRole("region", { name: "Aufgabe bearbeiten" });
    const restoredSeparator = restoredWorkbench.getByRole("separator", { name: "Spaltenbreite anpassen" });
    await expect(restoredSeparator).toBeVisible();
    await expect(restoredSeparator).toHaveAttribute("aria-valuenow", "60");

    await learner.page.addStyleTag({
      content: `
        .learner-task-context__scroll::after,
        .learner-task-workbench__main::after {
          content: "";
          display: block;
          height: 80rem;
        }
      `
    });
    const contextScroll = workbench.locator(".learner-task-context__scroll");
    const workScroll = workbench.locator(".learner-task-workbench__main");
    await expect.poll(() => contextScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight)).toBeGreaterThan(500);
    await expect.poll(() => workScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight)).toBeGreaterThan(500);

    const contextScrollBox = await contextScroll.boundingBox();
    const workScrollBox = await workScroll.boundingBox();
    expect(contextScrollBox).not.toBeNull();
    expect(workScrollBox).not.toBeNull();
    if (contextScrollBox && workScrollBox) {
      const viewportHeight = await learner.page.evaluate(() => window.innerHeight);
      const interactionY = Math.max(
        Math.max(contextScrollBox.y, workScrollBox.y) + 60,
        Math.min(contextScrollBox.y + contextScrollBox.height, workScrollBox.y + workScrollBox.height, viewportHeight) - 80
      );
      const leftInteractionX = contextScrollBox.x + contextScrollBox.width - 8;
      const rightInteractionX = workScrollBox.x + 8;
      const targets = await learner.page.evaluate(
        ({ leftX, rightX, y }) => ({
          left: document.elementFromPoint(leftX, y)?.closest(".learner-task-context__scroll") !== null,
          right: document.elementFromPoint(rightX, y)?.closest(".learner-task-workbench__main") !== null
        }),
        { leftX: leftInteractionX, rightX: rightInteractionX, y: interactionY }
      );
      expect(targets).toEqual({ left: true, right: true });

      const verticalTouchGesture = await restoredSeparator.evaluate((separator) => {
        const bounds = separator.getBoundingClientRect();
        const init = {
          bubbles: true,
          cancelable: true,
          pointerId: 23,
          pointerType: "touch",
          clientX: bounds.x + bounds.width / 2
        };
        const downAllowed = separator.dispatchEvent(new PointerEvent("pointerdown", { ...init, clientY: bounds.y + 80 }));
        const moveAllowed = separator.dispatchEvent(new PointerEvent("pointermove", { ...init, clientY: bounds.y + 120 }));
        separator.dispatchEvent(new PointerEvent("pointerup", { ...init, clientY: bounds.y + 120 }));
        return { downAllowed, moveAllowed };
      });
      expect(verticalTouchGesture).toEqual({ downAllowed: true, moveAllowed: true });
      await expect(restoredSeparator).toHaveAttribute("aria-valuenow", "60");
    }

    await scrollSurfaceWithKeyboard(learner.page, contextScroll, "end");
    await expect.poll(() => contextScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight - surface.scrollTop)).toBeLessThan(2);
    expect(await workScroll.evaluate((surface) => surface.scrollTop)).toBe(0);

    const contextBottom = await contextScroll.evaluate((surface) => surface.scrollTop);
    await scrollSurfaceWithKeyboard(learner.page, workScroll, "end");
    await expect.poll(() => workScroll.evaluate((surface) => surface.scrollHeight - surface.clientHeight - surface.scrollTop)).toBeLessThan(2);
    expect(await contextScroll.evaluate((surface) => surface.scrollTop)).toBe(contextBottom);

    await scrollSurfaceWithKeyboard(learner.page, contextScroll, "start");
    await expect.poll(() => contextScroll.evaluate((surface) => surface.scrollTop)).toBe(0);

    if (browserName === "chromium") {
      await verifyIndependentWheelScrolling(browser, taskUrl, learnerEmail);
    }

    await learner.page.setViewportSize({ width: 1180, height: 820 });
    await expect(context).toBeVisible();
    await expect(task).toBeVisible();
    await expect(switcher).toBeHidden();
    const largeLandscapeTracks = await restoredWorkbench.locator(".learner-task-workbench__desk").evaluate(
      (desk) => getComputedStyle(desk).gridTemplateColumns.split(" ").length
    );
    expect(largeLandscapeTracks).toBe(3);
    await expectNoViewportOverflow(learner.page);

    await learner.page.setViewportSize({ width: 820, height: 1180 });
    await expect(context).toBeHidden();
    await expect(task).toBeVisible();
    await expect(restoredSeparator).toBeHidden();
    await expect(switcher).toBeVisible();
    await expect(compactStatement).toBeVisible();
    await expect(compactStatement.getByText("Begründe abschließend, welche Position dich überzeugt.")).toBeVisible();
    const portraitColumns = await workbench.locator(".learner-task-workbench__desk").evaluate(
      (desk) => getComputedStyle(desk).gridTemplateColumns.split(" ").length
    );
    expect(portraitColumns).toBe(1);
    await expectNoViewportOverflow(learner.page);

    await learner.page.setViewportSize({ width: 390, height: 844 });
    await expect(compactStatement).toBeVisible();
    await expect(compactStatement.getByText("Begründe abschließend, welche Position dich überzeugt.")).toBeVisible();
    await expectNoViewportOverflow(learner.page);
  } finally {
    await learner.context.close();
    await teacher.context.close();
  }
});
