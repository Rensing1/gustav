import type { SessionBootstrapUser } from "$lib/types/session-bootstrap";

export type AppProfileView = {
  user: SessionBootstrapUser;
  display_name: string;
  email: string;
  first_name: string;
  last_name: string;
  name_locked_until: string | null;
  name_can_edit: boolean;
  password_change_href: string;
};

export type AppProfileCliToken = {
  id: string;
  label: string;
  scopes: string[];
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};
