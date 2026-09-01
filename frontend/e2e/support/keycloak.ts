import { expect, request, type APIRequestContext } from "@playwright/test";

import { adminClientId, adminClientSecret, adminPassword, adminRealm, adminUser, kcBase, realm } from "./e2e-env";
import {
  clearE2ESmtpRestore,
  registerE2ESmtpRestore,
  registerE2EUser
} from "./e2e-run-state";

type KeycloakUser = {
  id?: string;
};

type KeycloakRole = {
  id: string;
  name: string;
};

type LearnerProfile = {
  firstName: string;
  lastName: string;
  displayName?: string;
};

type RealmRepresentation = {
  smtpServer?: Record<string, string>;
  [key: string]: unknown;
};

function configuredRealmSmtp(): Record<string, string> {
  const configured: Record<string, string> = {
    host: process.env.KC_SMTP_HOST?.trim() || "smtp.school.example",
    port: process.env.KC_SMTP_PORT?.trim() || "587",
    from: process.env.KC_SMTP_FROM?.trim() || "noreply@school.example",
    fromDisplayName: process.env.KC_SMTP_FROM_NAME?.trim() || "GUSTAV-Lernplattform",
    auth: process.env.KC_SMTP_AUTH?.trim() || "true",
    starttls: process.env.KC_SMTP_STARTTLS?.trim() || "true",
    ssl: "false"
  };
  const user = process.env.KC_SMTP_USER?.trim();
  const password = process.env.KC_SMTP_PASSWORD?.trim();
  if (user) configured.user = user;
  if (password) configured.password = password;
  return configured;
}

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

async function ensureUserWithRole(
  email: string,
  password: string,
  roleName: "teacher" | "student",
  profile?: LearnerProfile
): Promise<string> {
  registerE2EUser({ email, role: roleName });
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
          firstName: profile?.firstName ?? "E2E",
          lastName: profile?.lastName ?? (roleName === "teacher" ? "Teacher" : "Learner"),
          attributes: profile?.displayName ? { display_name: [profile.displayName] } : undefined,
          enabled: true,
          emailVerified: true,
          requiredActions: []
        }
      });
      expect([201, 409], await create.text()).toContain(create.status());
      userId = await findUserId(kc, token, email);
    }
    expect(userId).toBeTruthy();
    registerE2EUser({ email, role: roleName, keycloak_id: userId as string });

    if (profile) {
      const update = await kc.put(`/admin/realms/${realm}/users/${userId}`, {
        headers: adminHeaders(token),
        data: {
          username: email,
          email,
          firstName: profile.firstName,
          lastName: profile.lastName,
          attributes: profile.displayName ? { display_name: [profile.displayName] } : {},
          enabled: true,
          emailVerified: true
        }
      });
      expect([200, 204]).toContain(update.status());
    }

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
    return userId as string;
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

export async function ensureLearnerUserProfile(
  email: string,
  password: string,
  profile: LearnerProfile
): Promise<string> {
  return ensureUserWithRole(email, password, "student", profile);
}

export async function useTemporaryRealmSmtp(
  smtpServer: Record<string, string>
): Promise<() => Promise<void>> {
  const kc = await keycloakAdminContext();
  let original: Record<string, string> | undefined;
  try {
    const token = await adminToken(kc);
    const currentResponse = await kc.get(`/admin/realms/${realm}`, {
      headers: adminHeaders(token)
    });
    expect(currentResponse.ok(), await currentResponse.text()).toBe(true);
    const current = await currentResponse.json() as RealmRepresentation;
    // A killed previous test may have left the capture server configured.
    // In that case restore the repository's real SMTP settings, not the stale test endpoint.
    original = current.smtpServer?.host === "gustav-frontend" || current.smtpServer?.port === "2526"
      ? configuredRealmSmtp()
      : current.smtpServer;
    registerE2ESmtpRestore(original ?? {});
    const update = await kc.put(`/admin/realms/${realm}`, {
      headers: adminHeaders(token),
      data: { ...current, smtpServer }
    });
    expect([200, 204]).toContain(update.status());
  } finally {
    await kc.dispose();
  }

  return async () => {
    const restoreContext = await keycloakAdminContext();
    try {
      const token = await adminToken(restoreContext);
      const currentResponse = await restoreContext.get(`/admin/realms/${realm}`, {
        headers: adminHeaders(token)
      });
      expect(currentResponse.ok(), await currentResponse.text()).toBe(true);
      const current = await currentResponse.json() as RealmRepresentation;
      const update = await restoreContext.put(`/admin/realms/${realm}`, {
        headers: adminHeaders(token),
        data: { ...current, smtpServer: original ?? {} }
      });
      expect([200, 204]).toContain(update.status());
      clearE2ESmtpRestore();
    } finally {
      await restoreContext.dispose();
    }
  };
}
