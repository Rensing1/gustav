import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, request, test, type APIRequestContext, type Page } from "@playwright/test";

function loadLocalEnvDefaults(): void {
  const envPathCandidates = [path.resolve(process.cwd(), ".env"), path.resolve(process.cwd(), "..", ".env")];
  const envPath = envPathCandidates.find((candidate) => existsSync(candidate));
  if (!envPath) {
    return;
  }

  const lines = readFileSync(envPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) {
      continue;
    }
    const [rawKey, ...rawValueParts] = trimmed.split("=");
    const key = rawKey.trim();
    if (process.env[key]) {
      continue;
    }
    const rawValue = rawValueParts.join("=").trim();
    process.env[key] = rawValue.replace(/^['"]|['"]$/g, "");
  }
}

loadLocalEnvDefaults();

const webBase = (process.env.WEB_BASE ?? "https://app.localhost").replace(/\/$/, "");
const kcBase = (process.env.KC_BASE ?? "https://id.localhost").replace(/\/$/, "");
const realm = process.env.KC_REALM ?? "gustav";
const adminUser = process.env.KEYCLOAK_ADMIN ?? "admin";
const adminPassword = process.env.KEYCLOAK_ADMIN_PASSWORD ?? "admin";
const emailDomain = deriveEmailDomain();

function deriveEmailDomain(): string {
  const explicit = process.env.E2E_EMAIL_DOMAIN?.trim();
  if (explicit) {
    return explicit.replace(/^@/, "");
  }

  const allowed = process.env.ALLOWED_REGISTRATION_DOMAINS?.split(",")
    .map((entry) => entry.trim().replace(/^@/, ""))
    .find(Boolean);
  return allowed ?? "example.com";
}

type KeycloakUser = {
  id?: string;
};

type KeycloakRole = {
  id: string;
  name: string;
};

async function keycloakAdminContext(): Promise<APIRequestContext> {
  return request.newContext({
    baseURL: kcBase,
    ignoreHTTPSErrors: true
  });
}

async function adminToken(kc: APIRequestContext): Promise<string> {
  const response = await kc.post("/realms/master/protocol/openid-connect/token", {
    form: {
      grant_type: "password",
      client_id: "admin-cli",
      username: adminUser,
      password: adminPassword
    }
  });
  expect(response.ok(), await response.text()).toBe(true);
  const payload = await response.json();
  return payload.access_token;
}

function adminHeaders(token: string) {
  return {
    authorization: `Bearer ${token}`,
    "content-type": "application/json"
  };
}

async function findUserId(kc: APIRequestContext, token: string, email: string): Promise<string | null> {
  const response = await kc.get(`/admin/realms/${realm}/users`, {
    headers: adminHeaders(token),
    params: { email, exact: "true" }
  });
  expect(response.ok(), await response.text()).toBe(true);
  const users = (await response.json()) as KeycloakUser[];
  return users[0]?.id ?? null;
}

async function ensureTeacherUser(email: string, password: string): Promise<void> {
  const kc = await keycloakAdminContext();
  try {
    const token = await adminToken(kc);
    let userId = await findUserId(kc, token, email);
    if (!userId) {
      const create = await kc.post(`/admin/realms/${realm}/users`, {
        headers: adminHeaders(token),
        data: {
          username: email,
          email,
          firstName: "E2E",
          lastName: "Teacher",
          enabled: true,
          emailVerified: true,
          requiredActions: []
        }
      });
      expect([201, 409], await create.text()).toContain(create.status());
      userId = await findUserId(kc, token, email);
    }
    expect(userId).toBeTruthy();

    const passwordResponse = await kc.put(`/admin/realms/${realm}/users/${userId}/reset-password`, {
      headers: adminHeaders(token),
      data: { type: "password", value: password, temporary: false }
    });
    expect([200, 204]).toContain(passwordResponse.status());

    const roleResponse = await kc.get(`/admin/realms/${realm}/roles/teacher`, {
      headers: adminHeaders(token)
    });
    expect(roleResponse.ok(), await roleResponse.text()).toBe(true);
    const role = (await roleResponse.json()) as KeycloakRole;
    const assignRole = await kc.post(`/admin/realms/${realm}/users/${userId}/role-mappings/realm`, {
      headers: adminHeaders(token),
      data: [role]
    });
    expect([200, 204]).toContain(assignRole.status());
  } finally {
    await kc.dispose();
  }
}

async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/auth/login");
  await page.locator('input[name="username"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"], input[type="submit"]').first().click();
  await expect
    .poll(async () => {
      const response = await page.request.get(`${webBase}/api/me`);
      return response.status();
    }, { timeout: 30_000 })
    .toBe(200);
}

async function seedModularUnit(page: Page, title: string): Promise<string> {
  const apiHeaders = {
    origin: webBase,
    referer: `${webBase}/teaching/units`,
    "content-type": "application/json"
  };
  const unitResponse = await page.request.post(`${webBase}/api/teaching/units`, {
    headers: apiHeaders,
    data: { title, unit_type: "modular" }
  });
  expect(unitResponse.status(), await unitResponse.text()).toBe(201);
  const unit = await unitResponse.json();
  const unitId = unit.id as string;

  const phasesResponse = await page.request.get(`${webBase}/api/teaching/units/${unitId}/phases`);
  expect(phasesResponse.ok(), await phasesResponse.text()).toBe(true);
  const phases = await phasesResponse.json();
  const phaseId = phases[0]?.id as string | undefined;
  expect(phaseId).toBeTruthy();

  for (const moduleTitle of ["Startmodul", "Zielmodul"]) {
    const moduleResponse = await page.request.post(`${webBase}/api/teaching/units/${unitId}/modules`, {
      headers: apiHeaders,
      data: { title: moduleTitle, phase_id: phaseId }
    });
    expect(moduleResponse.status(), await moduleResponse.text()).toBe(201);
  }

  return unitId;
}

async function viewportTransform(page: Page): Promise<string> {
  return page.locator(".svelte-flow__viewport").evaluate((element) => getComputedStyle(element).transform);
}

async function dragPane(page: Page): Promise<void> {
  const pane = page.locator(".svelte-flow__pane").first();
  const point = await pane.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const xSteps = [0.15, 0.3, 0.5, 0.7, 0.85];
    const ySteps = [0.18, 0.32, 0.5, 0.68, 0.82];
    for (const yStep of ySteps) {
      for (const xStep of xSteps) {
        const x = box.left + box.width * xStep;
        const y = box.top + box.height * yStep;
        const top = document.elementFromPoint(x, y);
        if (
          top?.closest(".svelte-flow__pane")
          && !top.closest(".svelte-flow__node")
          && !top.closest(".svelte-flow__edge")
          && !top.closest(".svelte-flow__controls")
        ) {
          return { x, y };
        }
      }
    }
    return null;
  });
  expect(point).toBeTruthy();
  const startX = point!.x;
  const startY = point!.y;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + 90, startY + 45, { steps: 8 });
  await page.mouse.up();
}

test("module create and delete update the graph without a hard reload", async ({ page }) => {
  const unique = Date.now();
  const email = `e2e_teacher_graph_${unique}@${emailDomain}`;
  const password = "Passw0rd!e2e";
  await ensureTeacherUser(email, password);
  await login(page, email, password);

  const unitId = await seedModularUnit(page, `E2E Graph ${unique}`);
  const moduleTitle = `E2E Modul ${Date.now()}`;

  await page.goto(`/teaching/units/${unitId}`);
  await expect(page.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeVisible();
  const beforeInitialPan = await viewportTransform(page);
  await dragPane(page);
  await expect.poll(() => viewportTransform(page)).not.toBe(beforeInitialPan);
  await page.getByRole("button", { name: "Fit View" }).click();

  await page.getByRole("button", { name: "Modul hinzufügen" }).click();
  await expect(page.getByRole("dialog", { name: "Modul hinzufügen" })).toBeVisible();

  await page.getByRole("button", { name: "Anlegen" }).click();
  await expect(page.getByText("Bitte gib Titel und Phase für das Modul an.")).toBeVisible();

  await page.getByLabel("Titel").fill(moduleTitle);

  const phaseSelect = page.getByLabel("Phase");
  if (!(await phaseSelect.inputValue())) {
    const firstPhaseValue = await phaseSelect.locator("option").nth(1).getAttribute("value");
    expect(firstPhaseValue).toBeTruthy();
    await phaseSelect.selectOption(firstPhaseValue!);
  }

  await page.getByRole("button", { name: "Anlegen" }).click();
  await expect(page.getByText("Modul angelegt.")).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Modul hinzufügen" })).toHaveCount(0);
  await expect(page.getByText(moduleTitle, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Modul hinzufügen" }).click();
  await expect(page.getByRole("dialog", { name: "Modul hinzufügen" })).toBeVisible();
  await expect(page.getByText("Bitte gib Titel und Phase für das Modul an.")).toHaveCount(0);
  await page.getByRole("button", { name: "Schließen" }).click();
  await expect(page.getByRole("dialog", { name: "Modul hinzufügen" })).toHaveCount(0);

  const beforePan = await viewportTransform(page);
  await dragPane(page);
  await expect.poll(() => viewportTransform(page)).not.toBe(beforePan);

  const createdModule = page.locator(".teacher-flow-node--module").filter({ hasText: moduleTitle }).first();
  await createdModule.click();
  await expect(createdModule.getByRole("button", { name: "Eigenschaften" })).toBeVisible();
  await createdModule.getByRole("button", { name: "Eigenschaften" }).click();
  await expect(createdModule.getByRole("button", { name: "Modul löschen" })).toBeVisible();
  await createdModule.getByRole("button", { name: "Modul löschen" }).click();
  await expect(page.getByText("Modul gelöscht.")).toBeVisible();
  await expect(page.getByText(moduleTitle, { exact: true })).toHaveCount(0);

  const remainingModule = page.locator(".teacher-flow-node--module").first();
  if (await remainingModule.count()) {
    await remainingModule.click();
    await expect(page.getByRole("button", { name: "Eigenschaften" })).toBeVisible();
  }
});
