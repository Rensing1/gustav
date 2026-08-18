import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { apiHeaders, expectApiOk } from "./support/api";
import { login } from "./support/auth";
import { emailDomain, webBase } from "./support/e2e-env";
import { ensureTeacherUser, useTemporaryRealmSmtp } from "./support/keycloak";
import { startSmtpCapture } from "./support/smtp-capture";

const password = "Passw0rd!e2e";

test("@feature-acceptance a new learner registers from the fullscreen QR link and joins the course", async ({ browser }) => {
  test.setTimeout(120_000);
  const unique = Date.now();
  const teacherEmail = `e2e_invite_teacher_${unique}@${emailDomain}`;
  const learnerEmail = `e2e_invite_learner_${unique}@${emailDomain}`;
  const courseTitle = `E2E QR-Klasse ${unique}`;
  await ensureTeacherUser(teacherEmail, password);

  const smtp = await startSmtpCapture();
  const restoreSmtp = await useTemporaryRealmSmtp({
    host: smtp.host,
    port: String(smtp.port),
    from: `noreply@${emailDomain}`,
    fromDisplayName: "GUSTAV-Lernplattform",
    auth: "false",
    starttls: "false",
    ssl: "false"
  });
  let teacherContext: BrowserContext | null = null;
  let learnerContext: BrowserContext | null = null;

  try {
    teacherContext = await browser.newContext({ baseURL: webBase });
    const teacher = await teacherContext.newPage();
    await login(teacher, teacherEmail, password);
    const createCourse = await teacher.request.post(`${webBase}/api/teaching/courses`, {
      headers: apiHeaders("/teaching/courses"),
      data: {
        title: courseTitle,
        subject: "Informatik",
        grade_level: "9",
        school_year_start: 2026
      }
    });
    await expectApiOk(createCourse, 201);
    const courseId = (await createCourse.json()).id as string;

    await teacher.goto(`/teaching/courses/${courseId}`);
    await teacher.getByRole("button", { name: "Mitglieder verwalten" }).click();
    await teacher.getByRole("link", { name: "Klasse einladen" }).click();
    const inviteDrawer = teacher.getByRole("dialog", { name: "Klasse einladen" });
    await inviteDrawer.getByRole("button", { name: "Klassenlink erstellen" }).click();
    await expect(teacher).toHaveURL(new RegExp(`/teaching/courses/${courseId}\\?invite=1$`));
    const inviteUrl = await teacher.getByRole("textbox", { name: "Klassenlink" }).inputValue();
    expect(inviteUrl).toContain("/invite#v1.");
    const drawerLayout = await inviteDrawer.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth
    }));
    expect(drawerLayout.scrollWidth).toBeLessThanOrEqual(drawerLayout.clientWidth + 1);
    await expect(inviteDrawer.getByRole("button", { name: "Im Vollbild anzeigen" })).toBeVisible();
    await expect(inviteDrawer.getByRole("textbox", { name: /Schul-E-Mail-Adressen/ })).toBeVisible();
    await expect(inviteDrawer.getByRole("button", { name: "Einladungen senden" })).toBeVisible();

    // Headless browsers do not consistently expose native fullscreen. Force the
    // documented denial path and verify the equal page-filling presentation.
    await teacher.evaluate(() => {
      Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
        configurable: true,
        value: () => Promise.reject(new Error("e2e_fullscreen_denied"))
      });
    });
    await teacher.getByRole("button", { name: "Im Vollbild anzeigen" }).click();
    const fullscreen = teacher.getByRole("dialog", { name: "QR-Code im Vollbild" });
    await expect(fullscreen).toHaveClass(/course-invite-fullscreen--fallback/);
    await expect(fullscreen.locator("canvas")).toBeVisible();
    await teacher.keyboard.press("Escape");
    await expect(fullscreen).toBeHidden();

    learnerContext = await browser.newContext({ baseURL: webBase });
    const learner = await learnerContext.newPage();
    const invitePageResponse = await learner.goto(inviteUrl);
    expect(invitePageResponse?.headers()["cache-control"]).toBe("private, no-store");
    expect(invitePageResponse?.headers()["referrer-policy"]).toBe("no-referrer");
    await expect(learner.getByRole("heading", { name: courseTitle })).toBeVisible();
    await learner.getByRole("button", { name: "Registrieren und beitreten" }).click();
    await learner.getByLabel("Schul-E-Mail").fill(learnerEmail);
    await learner.getByRole("button", { name: "Registrieren" }).click();

    await expect(learner).toHaveURL(/https:\/\/id\.localhost\/realms\/gustav\/protocol\/openid-connect\/registrations/);
    await expect(learner.getByRole("heading", { name: /Registrieren|Register/i })).toBeVisible();
    await expect(learner.locator("#kc-register-form")).toBeVisible();
    await expect(learner.locator("#kc-form-login")).toHaveCount(0);
    await learner.locator("#display_name").fill("E2E QR Lernender");
    await learner.locator("#email").fill(learnerEmail);
    await learner.locator("#password").fill(password);
    await learner.locator("#password-confirm").fill(password);
    await learner.locator("#kc-register-form button[type=submit]").click();

    const verificationUrl = await smtp.verificationUrl(learnerEmail);
    await learner.goto(verificationUrl);
    const backToApplication = learner.getByRole("link", {
      name: /Zurück zur Anwendung|Back to Application|Weiter zu GUSTAV/i
    });
    if (await backToApplication.isVisible().catch(() => false)) {
      await backToApplication.click();
    }
    await expect(learner).toHaveURL(new RegExp(`/learning/courses/${courseId}$`), {
      timeout: 30_000
    });

    await teacher.goto(`/teaching/courses/${courseId}`);
    await teacher.getByRole("button", { name: "Mitglieder verwalten" }).click();
    await expect(teacher.getByRole("dialog", { name: "Mitglieder verwalten" })).toContainText(
      learnerEmail.split("@", 1)[0]
    );
  } finally {
    await learnerContext?.close().catch(() => undefined);
    await teacherContext?.close().catch(() => undefined);
    await restoreSmtp().catch(() => undefined);
    await smtp.close().catch(() => undefined);
  }
});
