declare global {
  namespace App {
    interface LayoutData {
      bootstrap: {
        user?: {
          sub: string;
          name: string;
          role: string;
        } | null;
        start_target?: string | null;
      } | null;
    }
  }
}

export {};

