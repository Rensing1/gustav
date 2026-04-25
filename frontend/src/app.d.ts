import type { SessionBootstrap } from "$lib/types/session-bootstrap";

declare global {
  namespace App {
    interface LayoutData {
      bootstrap: SessionBootstrap | null;
      appSessionActive: boolean;
    }
  }
}

export {};
