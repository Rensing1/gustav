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
