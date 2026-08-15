import type { SessionBootstrap } from "$lib/types/session-bootstrap";
import type { WorkspaceLayout } from "$lib/types/workspace-layout";

declare global {
  namespace App {
    interface LayoutData {
      bootstrap: SessionBootstrap | null;
      appSessionActive: boolean;
      workspaceLayout: WorkspaceLayout;
    }

    interface PageData {
      workspaceLayout?: WorkspaceLayout;
    }
  }
}

export {};
