import { execFileSync } from "node:child_process";
import { apiHeaders, expectApiOk } from "./support/api";
import { currentUserSub, login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { expect, test } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { seedSimulationMaterialCourse } from "./support/seed-data";
import { completeQueuedFeedbackDeterministically, holdProviderWorker, releaseProviderWorker } from "./support/submission-finalization-fixture";

test("@feature-acceptance shows device-specific Filius evidence after upload and reload", async ({ browser }) => {
  test.setTimeout(150_000);
  const teacherEmail = e2eEmail("teacher"), learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacher = await newBrowserContext(browser), learner = await newBrowserContext(browser);
  try {
    const author = await teacher.newPage(), page = await learner.newPage();
    await login(author, teacherEmail, e2ePassword);
    await login(page, learnerEmail, e2ePassword);
    const unit = await seedSimulationMaterialCourse(author, page, "Lokales Netzwerk");
    const response = await author.request.post(`/api/teaching/units/${unit.unitId}/sections/${unit.sectionId}/tasks`, {
      headers: apiHeaders(), data: { instruction_md: "Lade das Filius-Netz hoch.", criteria: ["Browser auf beiden Clients"], filius: {} }
    });
    await expectApiOk(response, 201);
    const taskId = (await response.json()).id;
    await page.goto(`/learning/courses/${unit.courseId}/units/${unit.unitId}`);
    await page.getByRole("button", { name: /beginnen/i }).first().click();
    const archive = execFileSync(".venv/bin/python", ["-c", [
      "from pathlib import Path",
      "import sys",
      "from backend.tests.utils.filius import fls_with_config",
      'config = Path("backend/tests/fixtures/filius/synthetic-dns-web/configuration.xml")',
      "sys.stdout.buffer.write(fls_with_config(config.read_bytes()))"
    ].join("\n")], { cwd: ".." });
    await page.getByLabel("Datei auswählen").setInputFiles({ name: "netz.fls", mimeType: "application/x.filius.fls", buffer: archive });
    await holdProviderWorker();
    try {
      await page.getByRole("button", { name: /Rückmeldung einholen/ }).click();
      await completeQueuedFeedbackDeterministically({ courseId: unit.courseId, taskId, learnerSub: await currentUserSub(page) });
      await page.getByRole("button", { name: "Abgeben", exact: true }).click();
    } finally {
      await releaseProviderWorker();
    }
    await expect(page.getByRole("region", { name: "Aufgabe abgeschlossen" })).toBeVisible();
    await page.goto(`/learning/courses/${unit.courseId}/units/${unit.unitId}`);
    await page.reload();
    await page.getByRole("button", { name: "Abgabe ansehen" }).click();
    const evidence = page.locator(".filius-evidence");
    for (const node of ["n2", "n3"]) {
      await expect(evidence.locator("li").filter({ hasText: new RegExp(`^id: "app[^"]+"; node: "${node}"; class: "filius\\.software\\.www\\.WebBrowser"`) })).toHaveCount(1);
    }
    await expect(evidence.locator("li").getByText('path: "/Plan &copy; [A] ``B``.txt"')).toBeVisible();
    await expect(evidence).toContainText("schulweb.test. A 3600 192.168.0.10");
  } finally {
    await learner.close();
    await teacher.close();
  }
});
