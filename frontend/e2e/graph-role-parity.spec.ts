import { apiHeaders, expectApiOk } from "./support/api";
import { currentUserSub, login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test, type Page } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";

async function create(page: Page, url: string, data: Record<string, unknown>) {
  const response = await page.request.post(`${webBase}${url}`, { headers: apiHeaders(), data });
  await expectApiOk(response, 201);
  return response.json();
}

/** Compare graph coordinates, not the role-specific camera or page chrome. */
async function geometry(page: Page) {
  return page.locator(".svelte-flow").evaluate((root) => ({
    nodes: Array.from(root.querySelectorAll<HTMLElement>(".svelte-flow__node")).map((node) => {
      const card = node.querySelector<HTMLElement>(".teacher-flow-unit-node");
      const transform = new DOMMatrix(getComputedStyle(node).transform);
      return {
        id: node.dataset.id,
        x: transform.m41, y: transform.m42,
        width: node.offsetWidth, height: node.offsetHeight,
        cardWidth: card?.offsetWidth, cardHeight: card?.offsetHeight,
        padding: card ? getComputedStyle(card).padding : null
      };
    }).sort((a, b) => (a.id ?? "").localeCompare(b.id ?? "")),
    edges: Array.from(root.querySelectorAll(".svelte-flow__edge")).map((edge) => ({
      id: edge.getAttribute("data-id"), path: edge.querySelector(".svelte-flow__edge-path")?.getAttribute("d")
    })).sort((a, b) => (a.id ?? "").localeCompare(b.id ?? ""))
  }));
}

test("@feature-acceptance both roles share graph geometry and controls while learner permissions stay restricted", async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser);
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const unit = await create(teacher, "/api/teaching/units", { title: `Graphvergleich ${Date.now()}`, unit_type: "modular" });
    const base = `/api/teaching/units/${unit.id}`;
    const phasesResponse = await teacher.request.get(`${webBase}${base}/phases`);
    await expectApiOk(phasesResponse);
    const phases = await phasesResponse.json();
    phases.push(await create(teacher, `${base}/phases`, { title: "Transfer" }));
    phases.push(await create(teacher, `${base}/phases`, { title: "Ausblick" }));
    const modules = [];
    for (const [index, title] of ["Start", "Beobachten", "Vergleichen", "Zusammenführen", "Transfer", "Üben"].entries()) {
      modules.push(await create(teacher, `${base}/modules`, {
        title, phase_id: phases[index < 4 ? 0 : 1].id, module_kind: index === 5 ? "practice" : "learning"
      }));
    }
    for (const [from, to] of [[0, 1], [0, 2], [1, 3], [2, 3], [3, 4], [3, 5], [4, 5]]) {
      await create(teacher, `${base}/modules/edges`, { from_module_id: modules[from].id, to_module_id: modules[to].id });
    }
    const target = await teacher.request.get(`${webBase}${base}/modules/${modules[0].id}/content-target`);
    await expectApiOk(target);
    const sectionId = (await target.json()).section_id;
    await create(teacher, `${base}/sections/${sectionId}/materials`, { title: "Einstieg", body_md: "Ein gemeinsamer Lernpfad." });
    await create(teacher, `${base}/sections/${sectionId}/tasks`, { instruction_md: "Beschreibe den Lernpfad.", criteria: [], teacher_context_md: "Privater Graph-Testkontext" });
    const course = await create(teacher, "/api/teaching/courses", {
      title: `Graphkurs ${Date.now()}`, subject: "Testfach", grade_level: "Jahrgangsübergreifend",
      school_year_start: new Date().getFullYear()
    });
    await create(teacher, `/api/teaching/courses/${course.id}/modules`, { unit_id: unit.id });
    await create(teacher, `/api/teaching/courses/${course.id}/members`, { student_sub: await currentUserSub(learner) });

    const teacherUrl = `/teaching/units/${unit.id}?phase=${phases[0].id}`;
    const learnerUrl = `/learning/courses/${course.id}/units/${unit.id}`;
    await teacher.goto(teacherUrl);
    await learner.goto(learnerUrl);
    await expect(teacher.locator(".svelte-flow__node")).toHaveCount(9);
    await expect(learner.locator(".svelte-flow__node")).toHaveCount(9);
    await expect.poll(async () => (await geometry(learner)).edges.length).toBe(7);
    await expect.poll(() => geometry(learner)).toEqual(await geometry(teacher));
    for (const page of [teacher, learner]) {
      await expect.poll(() => page.locator(".svelte-flow__viewport").evaluate((element) =>
        new DOMMatrix(getComputedStyle(element).transform).a
      )).toBeCloseTo(0.82, 2);
    }

    await expect(learner.getByRole("button", { name: /Zusammenführen/ })).toBeDisabled();
    await expect(learner.getByRole("toolbar", { name: "Graphwerkzeuge" })).toHaveCount(0);
    await expect(learner.locator(".svelte-flow__controls-interactive")).toHaveCount(0);
    await expect(learner.locator('.svelte-flow__handle:not([aria-hidden="true"])')).toHaveCount(0);
    const forbidden = await learner.request.get(`${webBase}${base}/modules/${modules[0].id}/content-target`);
    expect(forbidden.status()).toBe(403);
    const lockedContent = await learner.request.get(`${webBase}/api/learning/courses/${course.id}/units/${unit.id}/modules/${modules[3].id}`);
    expect(lockedContent.status()).toBe(404);

    for (const [label, viewport] of [
      ["desktop", { width: 1440, height: 900 }],
      ["tablet", { width: 1024, height: 768 }],
      ["mobile", { width: 390, height: 844 }]
    ] as const) {
      for (const theme of ["light", "dark"]) {
        for (const [role, page] of [["teacher", teacher], ["learner", learner]] as const) {
          await page.setViewportSize(viewport);
          await page.evaluate((value) => document.documentElement.setAttribute("data-theme", value), theme);
          await expect(page.getByRole("button", { name: "Gesamtansicht", exact: true })).toBeVisible();
          await page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
          await expect.poll(() => page.locator(".svelte-flow").evaluate((root) => {
            const canvas = root.getBoundingClientRect();
            return Array.from(root.querySelectorAll(".svelte-flow__node")).every((node) => {
              const box = node.getBoundingClientRect();
              return box.left >= canvas.left - 1 && box.right <= canvas.right + 1
                && box.top >= canvas.top - 1 && box.bottom <= canvas.bottom + 1;
            });
          })).toBe(true);
          await expectNoViewportOverflow(page);
          // Clicking a bottom control can scroll the document. Capture from a
          // consistent page origin rather than comparing accidental scroll state.
          await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
          await page.screenshot({ path: testInfo.outputPath(`${role}-${label}-${theme}.png`), fullPage: true, animations: "disabled" });
        }
        await expect.poll(() => geometry(learner)).toEqual(await geometry(teacher));
      }
    }
    await teacher.reload();
    await learner.reload();
    await expect(teacher.locator(".svelte-flow__node")).toHaveCount(9);
    await expect(learner.locator(".svelte-flow__node")).toHaveCount(9);
    await expect.poll(() => geometry(learner)).toEqual(await geometry(teacher));
    await learner.getByRole("button", { name: /Modul 01 Start/ }).click();
    await expect(learner).toHaveURL(new RegExp(`module=${modules[0].id}`));
    await expect(learner.getByRole("button", { name: "Aufgabe 1 beginnen" })).toBeVisible();
    await expect(learner.locator("body")).not.toContainText("Privater Graph-Testkontext");
    await learner.goBack();
    await expect(learner.getByRole("button", { name: "Gesamtansicht", exact: true })).toBeVisible();
  } finally {
    await learnerContext.close();
    await teacherContext.close();
  }
});
