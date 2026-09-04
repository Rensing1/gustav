import { expect, test } from "./support/feature-test";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherModuleEditorVisualUnit } from "./support/seed-data";


test("@feature-acceptance teacher selects unit content and downloads a transient student PDF", async ({ page }) => {
  test.setTimeout(90_000);
  const title = `Druckfassung ${Date.now()}`;
  const email = e2eEmail("teacher");
  await ensureTeacherUser(email, e2ePassword);
  await login(page, email, e2ePassword);
  const seeded = await seedTeacherModuleEditorVisualUnit(page, title);

  await page.goto(`/teaching/units/${seeded.unitId}`);
  await page.getByRole("link", { name: "Druckfassung erstellen" }).click();
  await expect(page.getByRole("heading", { name: "Druckfassung erstellen" })).toBeVisible();
  await expect(page.getByText("0 von 2 Inhalten ausgewählt")).toBeVisible();

  await page.getByRole("checkbox", { name: "Argumentationshilfe" }).check();
  await expect(page.getByText("1 von 2 Inhalten ausgewählt")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "PDF herunterladen" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^gustav-druckfassung-[0-9]+-druckfassung\.pdf$/);
  const stream = await download.createReadStream();
  expect(stream).not.toBeNull();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const pdf = Buffer.concat(chunks);
  expect(pdf.subarray(0, 4).toString("ascii")).toBe("%PDF");
  expect(pdf.length).toBeGreaterThan(1_000);
});
