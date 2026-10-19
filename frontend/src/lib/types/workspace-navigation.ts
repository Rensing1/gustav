// Shared reactive URL for workspaces that manage their own browser history.
export const workspaceNavigationKey = Symbol("workspace-navigation");
export type WorkspaceNavigation = { href: string | null };
