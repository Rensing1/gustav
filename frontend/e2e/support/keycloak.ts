import { expect, request, type APIRequestContext } from "@playwright/test";

import { adminClientId, adminClientSecret, adminPassword, adminRealm, adminUser, kcBase, realm } from "./e2e-env";

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
  if (adminClientSecret) {
    const response = await kc.post(`/realms/${adminRealm}/protocol/openid-connect/token`, {
      form: {
        grant_type: "client_credentials",
        client_id: adminClientId,
        client_secret: adminClientSecret
      }
    });
    if (response.ok()) {
      const payload = await response.json();
      return payload.access_token;
    }
  }

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

async function ensureUserWithRole(email: string, password: string, roleName: "teacher" | "student"): Promise<void> {
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
          lastName: roleName === "teacher" ? "Teacher" : "Learner",
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

    const roleResponse = await kc.get(`/admin/realms/${realm}/roles/${roleName}`, {
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

export async function ensureTeacherUser(email: string, password: string): Promise<void> {
  await ensureUserWithRole(email, password, "teacher");
}

export async function ensureLearnerUser(email: string, password: string): Promise<void> {
  await ensureUserWithRole(email, password, "student");
}
