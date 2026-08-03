import { expect, test } from "@playwright/test";

import { login } from "./support/auth";
import { emailDomain } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { seedTeacherDialogAuthoringUnit } from "./support/seed-data";

test("@feature-acceptance saves and reloads every dialog authoring field", async ({ page }) => {
  const unique = Date.now();
  const email = `e2e_teacher_dialog_${unique}@${emailDomain}`;
  const password = "Passw0rd!e2e";
  await ensureTeacherUser(email, password);
  await login(page, email, password);

  const seeded = await seedTeacherDialogAuthoringUnit(page, `Dialog Authoring ${unique}`);
  const values = {
    instruction: `Dialoganweisung ${unique}`,
    criterion: `Begründetes Argument ${unique}`,
    teacherContext: `Interner Kontext ${unique}`,
    partnerName: `Dialogpartner ${unique}`,
    description: `Sichtbare Beschreibung ${unique}`,
    role: `Interne Rolle ${unique}`,
    learningGoal: `Lernziel ${unique}`,
    opening: `Eröffnungsfrage ${unique}`,
    closing: `Abschlussauftrag ${unique}`
  };

  await page.goto(`/teaching/units/${seeded.unitId}/nodes/${seeded.moduleId}`);
  await page.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();

  const createForm = page.getByTestId("teacher-node-editor-create-slot");
  await createForm.getByLabel("Aufgabentyp").selectOption("dialog");
  await createForm.getByLabel("Anweisung & Beschreibung").fill(values.instruction);
  await createForm.getByLabel("Kriterium 1", { exact: true }).fill(values.criterion);
  await createForm.getByLabel("Lehrkraft-Kontext").fill(values.teacherContext);
  await createForm.getByLabel("Name des KI-Partners").fill(values.partnerName);
  await createForm.getByLabel("Sichtbare Kurzbeschreibung").fill(values.description);
  await createForm.getByLabel("Interne Rolleninstruktion").fill(values.role);
  await createForm.getByLabel("Internes Lernziel").fill(values.learningGoal);
  await createForm.getByLabel("Eröffnungsnachricht").fill(values.opening);
  await createForm.getByLabel("Antwortmodus").selectOption("hybrid");
  await createForm.getByLabel("Max. Schülerantworten").fill("7");
  await createForm.getByLabel("Optionaler Abschlussauftrag").fill(values.closing);
  await createForm.getByRole("button", { name: /^Aufgabe hinzufügen$/i }).click();

  await expect(page.getByText("Aufgabe angelegt.")).toBeVisible();
  await expect(page.getByLabel("Name des KI-Partners")).toHaveValue(values.partnerName);
  await expect(page.getByLabel("Probeantwort eines Schülers")).toBeHidden();

  await page.reload();
  await page.getByRole("button", { name: new RegExp(values.instruction) }).click();

  await expect(page.getByLabel("Anweisung & Beschreibung")).toHaveValue(values.instruction);
  await expect(page.getByLabel("Kriterium 1", { exact: true })).toHaveValue(values.criterion);
  await expect(page.getByLabel("Lehrkraft-Kontext")).toHaveValue(values.teacherContext);
  await expect(page.getByLabel("Name des KI-Partners")).toHaveValue(values.partnerName);
  await expect(page.getByLabel("Sichtbare Kurzbeschreibung")).toHaveValue(values.description);
  await expect(page.getByLabel("Interne Rolleninstruktion")).toHaveValue(values.role);
  await expect(page.getByLabel("Internes Lernziel")).toHaveValue(values.learningGoal);
  await expect(page.getByLabel("Eröffnungsnachricht")).toHaveValue(values.opening);
  await expect(page.getByLabel("Antwortmodus")).toHaveValue("hybrid");
  await expect(page.getByLabel("Max. Schülerantworten")).toHaveValue("7");
  await expect(page.getByLabel("Optionaler Abschlussauftrag")).toHaveValue(values.closing);
  await expect(page.getByLabel("Probeantwort eines Schülers")).toBeHidden();

  await page.getByText("Gespeicherte Konfiguration testen").click();
  await expect(page.getByLabel("Probeantwort eines Schülers")).toBeVisible();
});
