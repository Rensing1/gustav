import { setAppTheme } from "./support/app-navigation";
import { apiHeaders, expectApiOk } from "./support/api";
import { currentUserSub, login } from "./support/auth";
import { newBrowserContext } from "./support/browser-context";
import { e2eEmail, e2ePassword, webBase } from "./support/e2e-env";
import { expect, test, type Page, type Browser, type TestInfo } from "./support/feature-test";
import { ensureLearnerUser, ensureTeacherUser } from "./support/keycloak";
import { expectNoViewportOverflow } from "./support/layout-sanity";
import { createFileMaterial } from "./support/seed-data";
import { expectDesignContrast } from "./support/design-contrast";

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

async function camera(page: Page) {
  return page.locator(".svelte-flow__viewport").evaluate((element) => {
    const matrix = new DOMMatrix(getComputedStyle(element).transform);
    return [matrix.a, matrix.e, matrix.f].map((value) => Math.round(value * 100) / 100);
  });
}

/** Inspect painted curves as well as the abstract orthogonal layout. */
async function expectClearPaintedPaths(page: Page) {
  await expect.poll(() => page.locator(".svelte-flow").evaluate((root) => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const context = canvas.getContext("2d")!;
    const luminance = () => {
      const [r, g, b] = [...context.getImageData(0, 0, 1, 1).data].slice(0, 3)
        .map((value) => { value /= 255; return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4; });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const obstacles = Array.from(root.querySelectorAll(".teacher-flow-unit-node, .teacher-flow-phase-band__label"))
      .map((element) => element.getBoundingClientRect());
    for (const path of root.querySelectorAll<SVGPathElement>(".svelte-flow__edge-path")) {
      const style = getComputedStyle(path);
      context.globalAlpha = 1;
      context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--color-bg-base");
      context.fillRect(0, 0, 1, 1);
      const background = luminance();
      context.globalAlpha = Number(style.opacity);
      context.fillStyle = style.stroke;
      context.fillRect(0, 0, 1, 1);
      const foreground = luminance();
      const ratio = (Math.max(background, foreground) + 0.05) / (Math.min(background, foreground) + 0.05);
      if (ratio < 3) return `path contrast below 3:1 (${ratio})`;
      const matrix = path.getScreenCTM();
      if (!matrix) return "unmeasured path";
      const length = path.getTotalLength();
      for (let distance = 0; distance <= length; distance += 6) {
        const local = path.getPointAtLength(distance);
        const point = new DOMPoint(local.x, local.y).matrixTransform(matrix);
        if (obstacles.some((box) => point.x > box.left + 3 && point.x < box.right - 3
          && point.y > box.top + 3 && point.y < box.bottom - 3)) return "path crosses a card or label";
      }
    }
    return null;
  })).toBeNull();
}

test("@feature-acceptance shared graph keeps horizontal paths, wrapping, role permissions and editor state", async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const teacherEmail = e2eEmail("teacher");
  const learnerEmail = e2eEmail("learner");
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser, { hasTouch: true });
  try {
    const teacher = await teacherContext.newPage();
    const learner = await learnerContext.newPage();
    const touch = await learnerContext.newCDPSession(learner);
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
    for (const [index, title] of ["Start", "Beobachten", "Vergleichen – digitale Systeme und ihre miteinander verbundenen Bausteine", "Zusammenführen", "Transfer", "Üben"].entries()) {
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
    const imageBytes = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR42mNkYPj/n4GBgYGJAQoAHgQCAQ1BDQAAAABJRU5ErkJggg==", "base64");
    const visibleFile = await createFileMaterial(teacher, unit.id, sectionId, {
      filename: "graphbild.png", mimeType: "image/png", title: "Graphbild", bytes: imageBytes
    });
    const lockedTarget = await teacher.request.get(`${webBase}${base}/modules/${modules[3].id}/content-target`);
    await expectApiOk(lockedTarget);
    const lockedFile = await createFileMaterial(teacher, unit.id, (await lockedTarget.json()).section_id, {
      filename: "gesperrtes-graphbild.png", mimeType: "image/png", title: "Gesperrtes Graphbild", bytes: imageBytes
    });
    const course = await create(teacher, "/api/teaching/courses", {
      title: `Graphkurs ${Date.now()}`, subject: "Testfach", grade_level: "Jahrgangsübergreifend",
      school_year_start: new Date().getFullYear()
    });
    await create(teacher, `/api/teaching/courses/${course.id}/modules`, { unit_id: unit.id });
    await create(teacher, `/api/teaching/courses/${course.id}/members`, { student_sub: await currentUserSub(learner) });

    const teacherUrl = `/teaching/units/${unit.id}?phase=${phases[0].id}`;
    const learnerUrl = `/learning/courses/${course.id}/units/${unit.id}`;
    await teacher.goto(teacherUrl);
    await learner.setViewportSize({ width: 390, height: 844 });
    await learner.goto(learnerUrl);
    await expect(teacher.locator(".svelte-flow__node")).toHaveCount(9);
    await expect(learner.locator(".svelte-flow__node")).toHaveCount(9);
    await expect.poll(async () => (await geometry(learner)).edges.length).toBe(7);
    await expect.poll(() => geometry(learner)).toEqual(await geometry(teacher));
    const branch = (await geometry(teacher)).nodes;
    const start = branch.find((node) => node.id === modules[0].id)!;
    for (const index of [1, 2]) expect(branch.find((node) => node.id === modules[index].id)!.x).toBeGreaterThan(start.x);
    await expectClearPaintedPaths(teacher);
    await expectClearPaintedPaths(learner);
    const startModule = learner.getByRole("button", { name: /Modul 01 Start/ });
    await expect(startModule).toBeInViewport({ ratio: 0.999 });
    for (const page of [teacher, learner]) {
      await expect.poll(() => page.locator(".svelte-flow__viewport").evaluate((element) =>
        new DOMMatrix(getComputedStyle(element).transform).a
      )).toBeGreaterThanOrEqual(0.819);
    }

    await expect(learner.getByRole("button", { name: /Zusammenführen/ })).toBeDisabled();
    await expect(learner.getByRole("button", { name: /Zusammenführen/ })).toContainText("Gesperrt");
    await expect(learner.getByRole("button", { name: /Zusammenführen/ })).toContainText("0/2 erfüllt");
    await expect(learner.getByRole("toolbar", { name: "Graphwerkzeuge" })).toHaveCount(0);
    await expect(learner.locator(".svelte-flow__controls-interactive")).toHaveCount(0);
    await expect(learner.locator('.svelte-flow__handle:not([aria-hidden="true"])')).toHaveCount(0);
    const forbidden = await learner.request.get(`${webBase}${base}/modules/${modules[0].id}/content-target`);
    expect(forbidden.status()).toBe(403);
    const lockedContent = await learner.request.get(`${webBase}/api/learning/courses/${course.id}/units/${unit.id}/modules/${modules[3].id}`);
    expect(lockedContent.status()).toBe(404);
    const fileUrl = (id: string) => `${webBase}/api/learning/courses/${course.id}/materials/${id}/file?disposition=inline`;
    expect((await learner.request.get(fileUrl(lockedFile))).status()).toBe(404);

    for (const [label, viewport] of [
      ["desktop", { width: 1440, height: 900 }],
      ["tablet", { width: 1024, height: 768 }],
      ["portrait", { width: 768, height: 1024 }],
      ["mobile", { width: 390, height: 844 }],
      ["narrow", { width: 320, height: 844 }]
    ] as const) {
      for (const theme of ["light", "dark"]) {
        for (const [role, page] of [["teacher", teacher], ["learner", learner]] as const) {
          await page.setViewportSize(viewport);
          // Keep the learner's touch profile explicit across cross-role browser captures.
          if (role === "learner") await touch.send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 2 });
          await setAppTheme(page, theme);
          await page.evaluate(() => window.scrollTo(0, 0));
          await expect(page.getByRole("button", { name: "Vergrößern", exact: true })).toBeVisible();
          await expect(page.getByRole("button", { name: "Verkleinern", exact: true })).toBeVisible();
          const controls = page.locator(".svelte-flow__controls");
          // Long mobile command/context bars may precede the graph. Ordinary
          // page scrolling brings the canvas into view; its tools must then fit.
          await page.locator(".teacher-flow-shell").evaluate((shell) => shell.scrollIntoView({ block: "start" }));
          await expect.poll(() => controls.evaluate((node) => {
            const shell = node.closest(".teacher-flow-shell")!;
            const box = node.getBoundingClientRect();
            return box.bottom <= innerHeight ? null : JSON.stringify({ bottom: box.bottom, viewport: innerHeight, top: shell.getBoundingClientRect().top, height: shell.getBoundingClientRect().height, available: getComputedStyle(shell).getPropertyValue("--graph-available-height") });
          }), { message: `${role} ${label} controls remain on screen` }).toBeNull();
          if (role === "learner") {
            const attribution = (await page.locator(".svelte-flow__attribution").boundingBox())!;
            const tools = (await controls.boundingBox())!;
            expect(attribution.x + attribution.width <= tools.x || tools.x + tools.width <= attribution.x
              || attribution.y + attribution.height <= tools.y || tools.y + tools.height <= attribution.y,
            "Graph attribution must not sit behind the controls").toBe(true);
          }
          for (const button of await controls.getByRole("button").all()) {
            if (viewport.width <= 640 || role === "learner") {
              const box = (await button.boundingBox())!;
              expect(box.width, `${role} ${label} ${theme} touch target`).toBeGreaterThanOrEqual(44);
              expect(box.height).toBeGreaterThanOrEqual(44);
            }
            if (await button.isDisabled()) continue;
            await button.hover();
            await button.focus();
            await page.keyboard.press("Tab");
            await page.keyboard.press("Shift+Tab");
            await expect(button).toBeFocused();
            await expect(button).not.toHaveCSS("outline-style", "none");
            await expectDesignContrast(button);
          }
          await expectDesignContrast(page.locator(".teacher-flow-unit-node--learner-locked strong, .teacher-flow-unit-node--learner-locked small"), true);
          await page.getByRole("button", { name: "Auswahl fokussieren", exact: true }).last().click();
          await expect.poll(() => page.locator(".svelte-flow__viewport").evaluate((element) => new DOMMatrix(getComputedStyle(element).transform).a)).toBeGreaterThanOrEqual(0.819);
          if (role === "learner" && viewport.width <= 1024) {
            await expect(startModule).toBeInViewport({ ratio: 0.999 });
          }
          await page.locator(".teacher-flow-shell").screenshot({ path: testInfo.outputPath(`${role}-${label}-${theme}-focus.png`), animations: "disabled" });
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
    // Both roles keep the graph mounted across responsive breakpoints.
    for (const page of [teacher, learner]) await page.setViewportSize({ width: 1440, height: 900 });
    await expect(learner.locator(".svelte-flow__node")).toHaveCount(9);
    await expect.poll(() => geometry(learner)).toEqual(await geometry(teacher));
    // Orientation changes deliberately refocus the selected phase with an animation.
    for (const page of [teacher, learner]) {
      if (page === teacher) await expect.poll(async () => (await camera(page))[0]).toBeGreaterThanOrEqual(0.819);
      await expect.poll(() => page.locator(".svelte-flow__viewport").evaluate(async (element) => {
        const before = getComputedStyle(element).transform;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        return getComputedStyle(element).transform === before;
      })).toBe(true);
    }
    await learner.setViewportSize({ width: 390, height: 844 });
    await learner.getByRole("button", { name: "Auswahl fokussieren", exact: true }).click();
    await expect(startModule).toBeInViewport({ ratio: 0.999 });
    await expect.poll(() => learner.locator(".svelte-flow__viewport").evaluate(async (element) => {
      const before = getComputedStyle(element).transform;
      await new Promise(resolve => setTimeout(resolve, 250));
      return getComputedStyle(element).transform === before;
    })).toBe(true);
    // Native touch input exercises the existing pan/pinch implementation on Chromium.
    await touch.send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 2 });
    const canvas = (await learner.locator(".svelte-flow").boundingBox())!;
    const x = Math.round(canvas.x + canvas.width / 2), y = Math.round(canvas.y + 80);
    const beforePan = await camera(learner);
    await touch.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y, id: 0 }] });
    for (let step = 1; step <= 5; step++) {
      await touch.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: x + step * 8, y, id: 0 }] });
    }
    await touch.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await expect.poll(async () => (await camera(learner))[1]).toBeGreaterThan(beforePan[1] + 20);
    const beforePinch = await camera(learner);
    await touch.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: x - 30, y, id: 0 }, { x: x + 30, y, id: 1 }] });
    for (let step = 1; step <= 5; step++) {
      const spread = 30 + step * 4;
      await touch.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: x - spread, y, id: 0 }, { x: x + spread, y, id: 1 }] });
    }
    await touch.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await expect.poll(async () => (await camera(learner))[0]).toBeGreaterThan(beforePinch[0]);
    await touch.detach();
    await learner.getByRole("button", { name: "Auswahl fokussieren", exact: true }).click();
    await expect(startModule).toBeInViewport({ ratio: 0.999 });
    await expect.poll(() => learner.locator(".svelte-flow__viewport").evaluate(async (element) => {
      const before = getComputedStyle(element).transform;
      await new Promise(resolve => setTimeout(resolve, 250));
      return getComputedStyle(element).transform === before;
    })).toBe(true);
    const focusedZoom = (await camera(learner))[0];
    await learner.getByRole("button", { name: "Verkleinern", exact: true }).tap();
    await expect.poll(async () => (await camera(learner))[0]).toBeLessThan(focusedZoom);
    const teacherCamera = await camera(teacher), learnerCamera = await camera(learner);
    // A width change without an orientation change must preserve the user's camera.
    await learner.setViewportSize({ width: 400, height: 844 });
    await expect.poll(() => camera(learner)).toEqual(learnerCamera);
    await teacher.reload();
    await learner.reload();
    await expect(teacher.locator(".svelte-flow__node")).toHaveCount(9);
    await expect(learner.locator(".svelte-flow__node")).toHaveCount(9);
    await expect.poll(() => geometry(learner)).toEqual(await geometry(teacher));
    await expect.poll(() => camera(teacher)).toEqual(teacherCamera);
    await expect.poll(() => camera(learner)).toEqual(learnerCamera);
    await startModule.tap();
    await expect(learner).toHaveURL(new RegExp(`module=${modules[0].id}`));
    await expect(learner.getByRole("button", { name: "Aufgabe 1 beginnen" })).toBeVisible();
    await expect(learner.locator("body")).not.toContainText("Privater Graph-Testkontext");
    const imageToggle = learner.getByRole("button", { name: "Graphbild", exact: true }).and(learner.locator("[aria-expanded]"));
    if (await imageToggle.getAttribute("aria-expanded") === "false") await imageToggle.click();
    const preview = learner.getByRole("img", { name: "Materialvorschau", exact: true });
    await expect(preview).toBeVisible();
    await expect.poll(() => preview.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
    const imageResponse = await learner.request.get(fileUrl(visibleFile));
    await expectApiOk(imageResponse);
    expect(await imageResponse.body()).toEqual(imageBytes);
    await learner.goBack();
    await expect(learner.getByRole("button", { name: "Gesamtansicht", exact: true })).toBeVisible();
    await expect.poll(() => camera(learner)).toEqual(learnerCamera);
    const removeMember = await teacher.request.delete(`${webBase}/api/teaching/courses/${course.id}/members/${await currentUserSub(learner)}`, { headers: apiHeaders() });
    await expectApiOk(removeMember, 204);
    expect((await learner.request.get(fileUrl(visibleFile))).status()).toBe(404);
    expect((await learner.request.get(`${webBase}/api/learning/courses/${course.id}/units/${unit.id}/modules/${modules[0].id}`)).status()).toBe(404);
  } finally {
    await learnerContext.close();
    await teacherContext.close();
  }
  await verifyRowsAndDrops(browser, testInfo);
});

async function verifyRowsAndDrops(browser: Browser, testInfo: TestInfo) {
  await ensureTeacherUser(e2eEmail("teacher"), e2ePassword);
  await ensureLearnerUser(e2eEmail("learner"), e2ePassword);
  const teacherContext = await newBrowserContext(browser);
  const learnerContext = await newBrowserContext(browser);
  try {
    const teacher = await teacherContext.newPage(), learner = await learnerContext.newPage();
    await login(teacher, e2eEmail("teacher"), e2ePassword);
    await login(learner, e2eEmail("learner"), e2ePassword);
    const unit = await create(teacher, "/api/teaching/units", { title: `Zeilenlayout ${Date.now()}`, unit_type: "modular" });
    const base = `/api/teaching/units/${unit.id}`;
    const phasesResponse = await teacher.request.get(`${webBase}${base}/phases`);
    await expectApiOk(phasesResponse);
    const firstPhase = (await phasesResponse.json())[0];
    const freePhase = await create(teacher, `${base}/phases`, { title: "Freie Auswahl" });
    const chain: { id: string }[] = [], free: { id: string }[] = [];
    for (let i = 0; i < 8; i++) chain.push(await create(teacher, `${base}/modules`, { title: `Schritt ${i + 1}`, phase_id: firstPhase.id }));
    for (let i = 1; i < chain.length; i++) await create(teacher, `${base}/modules/edges`, { from_module_id: chain[i - 1].id, to_module_id: chain[i].id });
    for (let i = 0; i < 5; i++) free.push(await create(teacher, `${base}/modules`, { title: `Freies Modul ${i + 1}`, phase_id: freePhase.id }));
    const targetResponse = await teacher.request.get(`${webBase}${base}/modules/${chain[0].id}/content-target`);
    await expectApiOk(targetResponse);
    await create(teacher, `${base}/sections/${(await targetResponse.json()).section_id}/materials`, { title: "Zeilenmaterial", body_md: "Dieser Inhalt stammt aus dem echten Modul." });
    const course = await create(teacher, "/api/teaching/courses", { title: `Zeilenkurs ${Date.now()}`, subject: "Testfach", grade_level: "Jahrgangsübergreifend", school_year_start: new Date().getFullYear() });
    await create(teacher, `/api/teaching/courses/${course.id}/modules`, { unit_id: unit.id });
    await create(teacher, `/api/teaching/courses/${course.id}/members`, { student_sub: await currentUserSub(learner) });
    await teacher.setViewportSize({ width: 1440, height: 900 });
    await teacher.goto(`/teaching/units/${unit.id}`);
    await learner.goto(`/learning/courses/${course.id}/units/${unit.id}`);
    for (const page of [teacher, learner]) await expect(page.locator(".svelte-flow__node")).toHaveCount(15);
    await expect.poll(() => geometry(learner)).toEqual(await geometry(teacher));
    const initial = await geometry(teacher);
    const cards = chain.map((module) => initial.nodes.find((node) => node.id === module.id)!);
    expect(new Set(cards.slice(0, 4).map((node) => node.y)).size).toBe(1);
    expect(new Set(cards.slice(4).map((node) => node.y)).size).toBe(1);
    expect(cards[1].x).toBeGreaterThan(cards[0].x);
    expect(cards[4].y).toBeGreaterThan(cards[0].y);
    expect(cards[4].x).toBeCloseTo(cards[0].x, 0);
    expect(initial.edges).toHaveLength(7);

    for (const width of [320, 390, 768, 1024, 1440]) {
      for (const theme of ["light", "dark"]) {
        for (const [role, page] of [["teacher", teacher], ["learner", learner]] as const) {
          await page.setViewportSize({ width, height: width === 768 ? 1024 : 900 });
          await setAppTheme(page, theme);
          await page.getByRole("button", { name: "Gesamtansicht", exact: true }).click();
          await expectClearPaintedPaths(page);
          await expectNoViewportOverflow(page);
          await page.locator(".teacher-flow-shell").screenshot({ path: testInfo.outputPath(`rows-${role}-${width}-${theme}.png`), animations: "disabled" });
        }
        await expect.poll(() => geometry(learner)).toEqual(await geometry(teacher));
      }
    }

    await teacher.setViewportSize({ width: 1440, height: 900 });
    await teacher.goto(`/teaching/units/${unit.id}?phase=${freePhase.id}`);
    const handle = (id: string) => teacher.locator(`.svelte-flow__node[data-id="${id}"] .teacher-flow-unit-node__drag-handle`);
    const storedIds = async (phaseId: string) => {
      const response = await teacher.request.get(`${webBase}${base}/modules/graph`);
      await expectApiOk(response);
      const graph = await response.json();
      return graph.modules.filter((module: { phase_id: string }) => module.phase_id === phaseId)
        .sort((a: { position_in_phase: number }, b: { position_in_phase: number }) => a.position_in_phase - b.position_in_phase)
        .map((module: { id: string }) => module.id);
    };
    const drag = async (from: string, dx: number, dy = 0) => {
      await handle(from).hover();
      const node = teacher.locator(`.svelte-flow__node[data-id="${from}"]`);
      // A navigation may still be restoring the camera. Read the pointer's
      // start position only after the target has stopped moving.
      await expect.poll(() => node.evaluate(async (element) => {
        const before = element.getBoundingClientRect();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const after = element.getBoundingClientRect();
        return Math.abs(before.x - after.x) + Math.abs(before.y - after.y);
      })).toBeLessThan(0.1);
      const box = (await handle(from).boundingBox())!;
      const initialBox = (await node.boundingBox())!;
      const x = box.x + box.width / 2, y = box.y + box.height / 2;
      const hit = await teacher.evaluate(({ x, y }) => {
        const element = document.elementFromPoint(x, y);
        return { handle: Boolean(element?.closest(".teacher-flow-unit-node__drag-handle")), tag: element?.tagName, classes: element?.getAttribute("class"), text: element?.textContent?.slice(0, 80) };
      }, { x, y });
      expect(hit.handle, JSON.stringify(hit)).toBe(true);
      await teacher.mouse.move(x, y);
      await teacher.mouse.down();
      await teacher.mouse.move(x + dx, y + dy, { steps: 10 });
      if (Math.abs(dx) > 12) await expect.poll(async () => Math.abs((await node.boundingBox())!.x - initialBox.x)).toBeGreaterThan(Math.abs(dx) / 2);
      await teacher.mouse.up();
    };
    await expect(handle(free[0].id)).toBeInViewport();
    await drag(free[0].id, 2, 1);
    expect(await storedIds(freePhase.id)).toEqual(free.map((module) => module.id));
    const a = (await teacher.locator(`.svelte-flow__node[data-id="${free[0].id}"]`).boundingBox())!;
    const b = (await teacher.locator(`.svelte-flow__node[data-id="${free[1].id}"]`).boundingBox())!;
    const [accepted] = await Promise.all([
      teacher.waitForResponse((response) => response.url().endsWith(`/graph/modules`) && response.request().method() === "POST"),
      drag(free[0].id, b.x - a.x + b.width * 0.65)
    ]);
    expect(accepted.ok()).toBe(true);
    await expect.poll(() => storedIds(freePhase.id)).toEqual([free[1].id, free[0].id, ...free.slice(2).map((module) => module.id)]);

    await teacher.goto(`/teaching/units/${unit.id}?phase=${firstPhase.id}`);
    await expect(handle(chain[0].id)).toBeInViewport();
    const first = (await teacher.locator(`.svelte-flow__node[data-id="${chain[0].id}"]`).boundingBox())!;
    const second = (await teacher.locator(`.svelte-flow__node[data-id="${chain[1].id}"]`).boundingBox())!;
    const [rejected] = await Promise.all([
      teacher.waitForResponse((response) => response.url().endsWith(`/graph/modules`) && response.request().method() === "POST"),
      drag(chain[0].id, second.x - first.x + second.width * 0.65)
    ]);
    expect(rejected.status()).toBe(400);
    await expect(teacher.getByText("Verschieben blockiert: Abhängigkeiten zuerst entfernen.", { exact: true })).toBeVisible();
    expect(await storedIds(firstPhase.id)).toEqual(chain.map((module) => module.id));
    await expect.poll(async () => (await geometry(teacher)).nodes.filter((node) => chain.some((m) => m.id === node.id)))
      .toEqual(initial.nodes.filter((node) => chain.some((m) => m.id === node.id)));
    await expectClearPaintedPaths(teacher);

    await learner.setViewportSize({ width: 390, height: 844 });
    await learner.getByRole("button", { name: "Auswahl fokussieren", exact: true }).click();
    await expect.poll(() => learner.locator(".svelte-flow__viewport").evaluate(async (element) => {
      const before = getComputedStyle(element).transform;
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return getComputedStyle(element).transform === before;
    })).toBe(true);
    const beforeOpen = await camera(learner);
    await learner.getByRole("button", { name: /Modul 01 Schritt 1/ }).click();
    await expect(learner.getByText("Dieser Inhalt stammt aus dem echten Modul.")).toBeVisible();
    await learner.goBack();
    await expect.poll(() => camera(learner)).toEqual(beforeOpen);
  } finally {
    await learnerContext.close();
    await teacherContext.close();
  }
}
