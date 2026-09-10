import { expect, test } from "./support/feature-test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { apiHeaders, expectApiOk } from "./support/api";

import { login } from "./support/auth";
import { e2eEmail, e2ePassword } from "./support/e2e-env";
import { ensureTeacherUser } from "./support/keycloak";
import { createFileMaterial, seedTeacherModuleEditorVisualUnit } from "./support/seed-data";


test("@feature-acceptance teacher selects mixed materials and downloads a multi-page student PDF", async ({ page }, info) => {
  test.setTimeout(150_000);
  const title = `Druckfassung ${Date.now()}`;
  const email = e2eEmail("teacher");
  await ensureTeacherUser(email, e2ePassword);
  await login(page, email, e2ePassword);
  const seeded = await seedTeacherModuleEditorVisualUnit(page, title);
  const root = resolve(process.cwd(), ".."), python = resolve(root, ".venv/bin/python");
  const targets: string[] = [];
  for (const moduleId of seeded.moduleIds) {
    const response = await page.request.get(`/api/teaching/units/${seeded.unitId}/modules/${moduleId}/content-target`);
    await expectApiOk(response);
    targets.push((await response.json()).section_id);
  }
  for (const [sectionId, materialTitle, body] of [
    [targets[0], "Ausführliches Lesematerial", Array.from({ length: 28 }, (_, index) => `Absatz ${index + 1}: Ein digitales System erfasst Eingaben, verarbeitet sie nach klaren Regeln und stellt Ergebnisse dar. Ein nachvollziehbarer Test verwendet unterschiedliche Werte und prüft auch die Grenzen. Dateiendungen wie \`.sb3\`, \`.hex\` und \`.fls\` gehören zum Material.`).join("\n\n")],
    [targets[1], "Programme entwickeln", "ENTWICKLUNGSSTART: Beschreibe Eingabe, Verarbeitung und Ausgabe eines selbst gewählten Systems."],
  ]) {
    await expectApiOk(await page.request.post(`/api/teaching/units/${seeded.unitId}/sections/${sectionId}/materials`, {
      headers: apiHeaders(), data: { title: materialTitle, body_md: body }
    }), 201);
  }
  await createFileMaterial(page, seeded.unitId, targets[0], {
    filename: "gustav-illustration.png", mimeType: "image/png", title: "GUSTAV-Illustration",
    altText: "GUSTAV mit Zauberhut", bytes: readFileSync(resolve(root, "frontend/static/gustav-logo.png"))
  });
  const sourcePdf = execFileSync(python, ["-c", "import sys\nfrom backend.teaching.printouts_pdf import _weasyprint_pdf\nsys.stdout.buffer.write(_weasyprint_pdf(sys.stdin.read()))"], {
    cwd: root, input: readFileSync(resolve(root, "frontend/e2e/fixtures/print-source.html"))
  });
  await createFileMaterial(page, seeded.unitId, targets[1], {
    filename: "quellenblatt.pdf", mimeType: "application/pdf", title: "Quellenblatt", bytes: sourcePdf
  });

  await page.goto(`/teaching/units/${seeded.unitId}`);
  await page.getByRole("link", { name: "Druckfassung erstellen" }).click();
  await expect(page.getByRole("heading", { name: "Druckfassung erstellen" })).toBeVisible();
  await expect(page.getByText("0 von 6 Inhalten ausgewählt")).toBeVisible();

  await page.getByRole("checkbox", { name: "Argumentationshilfe" }).check();
  await expect(page.getByText("1 von 6 Inhalten ausgewählt")).toBeVisible();
  await page.getByRole("checkbox", { name: "Alle Inhalte auswählen" }).check();
  await expect(page.getByText("6 von 6 Inhalten ausgewählt")).toBeVisible();

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
  await download.saveAs(info.outputPath("mixed-materials.pdf"));
  const inspected = JSON.parse(execFileSync(python, ["-c", [
    "import io,json,sys",
    "from pypdf import PdfReader",
    "pages=PdfReader(io.BytesIO(sys.stdin.buffer.read())).pages",
    "print(json.dumps({'texts':[p.extract_text() for p in pages], 'landscape':any(float(p.mediabox.width)>float(p.mediabox.height) for p in pages), 'images':sum(len(p.images) for p in pages)}))"
  ].join("\n")], { cwd: root, input: pdf }).toString());
  expect(inspected.texts.length).toBeGreaterThanOrEqual(5);
  expect(inspected.texts[0]).toContain("Absatz 1:");
  expect(inspected.landscape).toBe(true);
  expect(inspected.images).toBeGreaterThan(0);
  expect(inspected.texts.join("\n")).toContain("QUERFORMAT-NACHWEIS");
  expect(inspected.texts.join("\n")).toContain(".sb3");
  const nextSection = inspected.texts.find((text: string) => text.includes("Zielmodul"));
  expect(nextSection).toContain("ENTWICKLUNGSSTART");
  for (const [index, text] of inspected.texts.entries()) expect(text).toContain(`Seite ${index + 1} / ${inspected.texts.length}`);
});
