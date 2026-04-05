import type { ThemePreference } from "$lib/types/theme";

export function syncDocumentTheme(doc: Document, theme: ThemePreference): void {
  doc.documentElement.dataset.theme = theme;
  doc.documentElement.style.colorScheme = theme;
}
